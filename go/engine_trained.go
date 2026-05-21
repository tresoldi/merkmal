package merkmal

import (
	"encoding/json"
	"io/fs"
	"math"
	"sort"
	"strings"
	"golang.org/x/text/unicode/norm"
)

// TrainedEngine implements System for trained models (classfeat).
type TrainedEngine struct {
	config   *ModelConfig
	geometry *Geometry

	featureNames    []string
	geometryMap     map[string]string
	soundClasses    map[string]map[string]bool
	classNames      []string
	ipaToClass      map[string]string
	classPrototypes map[string]map[string]float64
	alpha           float64

	dimensionWeights map[string]float64
	classCosts       map[string]float64
	nodeInvDepths    map[string]float64
}

// NewTrainedEngine creates a trained engine from config, geometry, and model fs.
func NewTrainedEngine(fsys fs.FS, config *ModelConfig, geom *Geometry) (*TrainedEngine, error) {
	e := &TrainedEngine{
		config:   config,
		geometry: geom,
	}

	var rawModel struct {
		FeatureNames    []string                       `json:"feature_names"`
		GeometryMap     map[string]string              `json:"geometry_map"`
		SoundClasses    map[string][]string            `json:"sound_classes"`
		ClassPrototypes map[string]map[string]float64  `json:"class_prototypes"`
		Alpha           float64                        `json:"alpha"`
	}
	if err := json.Unmarshal(config.RawJSON, &rawModel); err != nil {
		return nil, err
	}

	e.featureNames = rawModel.FeatureNames
	e.geometryMap = rawModel.GeometryMap
	if e.geometryMap == nil {
		e.geometryMap = map[string]string{}
	}
	e.alpha = rawModel.Alpha

	e.soundClasses = make(map[string]map[string]bool, len(rawModel.SoundClasses))
	for cls, members := range rawModel.SoundClasses {
		set := make(map[string]bool, len(members))
		for _, m := range members {
			set[m] = true
		}
		e.soundClasses[cls] = set
	}
	e.classNames = make([]string, 0, len(e.soundClasses))
	for cls := range e.soundClasses {
		e.classNames = append(e.classNames, cls)
	}
	sort.Strings(e.classNames)

	e.ipaToClass = make(map[string]string)
	for cls, members := range rawModel.SoundClasses {
		for _, seg := range members {
			e.ipaToClass[seg] = cls
		}
	}

	e.classPrototypes = rawModel.ClassPrototypes
	if e.classPrototypes == nil {
		e.classPrototypes = map[string]map[string]float64{}
	}

	var weights struct {
		DimensionWeights map[string]float64 `json:"dimension_weights"`
		ClassCosts       map[string]float64 `json:"class_costs"`
	}
	if data, err := fs.ReadFile(fsys, "weights.json"); err == nil {
		_ = json.Unmarshal(data, &weights)
	}
	e.dimensionWeights = weights.DimensionWeights
	if e.dimensionWeights == nil {
		e.dimensionWeights = make(map[string]float64)
		for _, n := range e.featureNames {
			e.dimensionWeights[n] = 1.0
		}
	}
	e.classCosts = weights.ClassCosts
	if e.classCosts == nil {
		e.classCosts = map[string]float64{}
	}

	e.buildNodeInvDepths()
	return e, nil
}

func (e *TrainedEngine) buildNodeInvDepths() {
	allDepths := map[string]int{}
	walkAllNodeDepths(e.geometry.Tree, 1, allDepths)

	e.nodeInvDepths = make(map[string]float64, len(e.featureNames))
	total := 0.0
	for _, featName := range e.featureNames {
		nodeName := e.geometryMap[featName]
		depth := allDepths[nodeName]
		if depth == 0 {
			depth = 3
		}
		e.nodeInvDepths[featName] = 1.0 / float64(depth)
		total += e.nodeInvDepths[featName]
	}
	if total > 0 {
		for featName := range e.nodeInvDepths {
			e.nodeInvDepths[featName] /= total
		}
	}
}

// ── IPA preprocessing and classification ────────────────────────────

var legacyMap = map[string]string{
	"ʧ": "t͡ʃ", "ʨ": "t͡ɕ", "ʦ": "t͡s", "ʣ": "d͡z",
	"ʤ": "d͡ʒ", "ʥ": "d͡ʑ",
	"ȵ": "ɲ", "ǝ": "ə", "ʍ": "w", "ȶ": "t", "ł": "ɫ",
}

var siniticVowels = map[string]string{"ɿ": "ɨ", "ʅ": "ɨ"}

var modifierAdjustments = map[rune]map[string]float64{
	'ʰ': {"aspirated": 1.0},
	'ʱ': {"aspirated": 1.0, "voice": 1.0},
	'ʼ': {"glottalized": 1.0},
	'ˀ': {"glottalized": 1.0},
	'̃':  {"nasal": 1.0},
	'ⁿ': {"nasal": 1.0},
	'̥':  {"voice": -1.0},
	'̬':  {"voice": 1.0},
	'ˠ': {"dorsal": 1.0},
	'ʷ': {"labial": 1.0, "round": 1.0},
	'ʲ': {"dorsal": 1.0, "high": 1.0},
	'ˤ': {},
	'ː': {},
}

var stripPrefixes = map[rune]bool{'ˈ': true, 'ˌ': true, 'ˀ': true}
var prenasalPrefixes = []string{"ⁿ", "ᵐ", "ᵑ"}

const preaspPrefix = "ʰ"
const vowelChars = "aeiouɑɛɔəɨɪʊʉæøœɒɤɯɜɐʌɵɞɶʏ"

var chaoValueMap = map[byte]float64{
	'5': 1.0, '4': 0.5, '3': 0.0, '2': -0.5, '1': -1.0,
}

var supToDigit = map[rune]byte{
	'⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5',
}

func (e *TrainedEngine) preprocess(grapheme string) string {
	normalized := NormalizeInputGrapheme(grapheme)
	if normalized == "" {
		return ""
	}
	if idx := strings.LastIndex(normalized, "/"); idx >= 0 {
		normalized = normalized[idx+1:]
		if normalized == "" {
			return ""
		}
	}
	for old, repl := range legacyMap {
		normalized = strings.ReplaceAll(normalized, old, repl)
	}
	for old, repl := range siniticVowels {
		normalized = strings.ReplaceAll(normalized, old, repl)
	}
	runes := []rune(normalized)
	for len(runes) > 0 && stripPrefixes[runes[0]] {
		runes = runes[1:]
	}
	normalized = string(runes)
	for _, prefix := range prenasalPrefixes {
		if strings.HasPrefix(normalized, prefix) {
			normalized = normalized[len(prefix):]
			break
		}
	}
	if strings.HasPrefix(normalized, preaspPrefix) && len([]rune(normalized)) > 1 {
		rest := normalized[len(preaspPrefix):]
		if rest != "" && !strings.ContainsRune(vowelChars, []rune(rest)[0]) {
			normalized = rest
		}
	}
	if normalized == "" {
		return ""
	}
	return normalized
}

var voicedBases = map[string]bool{
	"b": true, "d": true, "ɖ": true, "g": true, "ɡ": true,
	"ɢ": true, "ɟ": true, "ɓ": true, "ɗ": true, "ɠ": true, "ʛ": true,
	"d͡z": true, "d͡ʒ": true, "d͡ʑ": true, "d͡ʐ": true,
	"z": true, "ʒ": true, "ʐ": true, "ʑ": true, "ʝ": true,
	"β": true, "v": true, "ð": true, "ɣ": true, "ʁ": true,
	"ɦ": true, "ʕ": true, "ɮ": true,
}

var voicelessBases = map[string]bool{
	"p": true, "t": true, "ʈ": true, "k": true, "q": true, "c": true,
	"t͡s": true, "t͡ʃ": true, "t͡ɕ": true, "t͡ʂ": true,
	"s": true, "ʃ": true, "ʂ": true, "ɕ": true, "ç": true,
	"ɸ": true, "f": true, "θ": true, "x": true, "χ": true,
	"h": true, "ʔ": true, "ħ": true, "ɬ": true,
}

var implosiveBases = map[string]bool{
	"ɓ": true, "ɗ": true, "ɠ": true, "ʛ": true, "ʄ": true,
}

var vowelClasses = map[string]bool{
	"I": true, "Ic": true, "E": true, "A": true, "Ab": true, "V": true, "O": true,
}

func (e *TrainedEngine) classifySegment(grapheme string) map[string]float64 {
	normalized := e.preprocess(grapheme)
	if normalized == "" {
		return nil
	}
	nfd := norm.NFD.String(normalized)
	runes := []rune(nfd)

	var base string
	var cls string
	var remainder []rune

	for _, tie := range []rune{'͡', '͜'} {
		for i, r := range runes {
			if r == tie {
				end := i + 2
				if end > len(runes) {
					end = len(runes)
				}
				candidate := string(runes[:end])
				if c, ok := e.ipaToClass[candidate]; ok {
					cls = c
					base = candidate
					remainder = runes[end:]
				}
				break
			}
		}
		if cls != "" {
			break
		}
	}

	if cls == "" && len(runes) > 0 {
		first := string(runes[0])
		if c, ok := e.ipaToClass[first]; ok {
			cls = c
			base = first
			remainder = runes[1:]
		}
	}

	if cls == "" {
		return nil
	}

	vector := make(map[string]float64, len(e.featureNames))
	if proto, ok := e.classPrototypes[cls]; ok {
		for k, v := range proto {
			vector[k] = v
		}
	}
	for _, name := range e.featureNames {
		if _, exists := vector[name]; !exists {
			vector[name] = 0.0
		}
	}

	if voicedBases[base] {
		vector["voice"] = 1.0
	} else if voicelessBases[base] {
		vector["voice"] = -1.0
	}

	if implosiveBases[base] {
		vector["glottalized"] = 1.0
	}

	if vowelClasses[cls] {
		refineVowel(base, vector)
	}

	for _, r := range remainder {
		if adj, ok := modifierAdjustments[r]; ok {
			for k, v := range adj {
				vector[k] = v
			}
		}
	}

	applyTone(normalized, vector)
	return vector
}

func (e *TrainedEngine) classifyToClass(grapheme string) string {
	normalized := e.preprocess(grapheme)
	if normalized == "" {
		return ""
	}
	nfd := norm.NFD.String(normalized)
	runes := []rune(nfd)

	for _, tie := range []rune{'͡', '͜'} {
		for i, r := range runes {
			if r == tie {
				end := i + 2
				if end > len(runes) {
					end = len(runes)
				}
				candidate := string(runes[:end])
				if c, ok := e.ipaToClass[candidate]; ok {
					return c
				}
				break
			}
		}
	}
	if len(runes) > 0 {
		first := string(runes[0])
		if c, ok := e.ipaToClass[first]; ok {
			return c
		}
	}
	return ""
}

var heightMap = map[rune]float64{
	'i': 1.0, 'ɪ': 0.7, 'ɨ': 1.0, 'ɯ': 1.0,
	'u': 1.0, 'ʊ': 0.7, 'ʉ': 1.0, 'y': 1.0, 'ʏ': 0.7,
	'e': 0.5, 'ø': 0.5, 'ɘ': 0.5, 'ɤ': 0.5, 'o': 0.5,
	'ə': 0.0, 'ɐ': -0.3,
	'ɛ': -0.5, 'æ': -0.7, 'ɜ': -0.5, 'ʌ': -0.5, 'ɔ': -0.5,
	'œ': -0.5, 'ɞ': -0.5, 'ɵ': 0.5,
	'a': -1.0, 'ɑ': -1.0, 'ɶ': -1.0, 'ɒ': -1.0,
}

var backMap = map[rune]float64{
	'i': -1.0, 'ɪ': -0.7, 'e': -1.0, 'ɛ': -1.0, 'æ': -1.0,
	'y': -1.0, 'ʏ': -0.7, 'ø': -1.0, 'œ': -1.0, 'ɶ': -1.0,
	'ɨ': 0.0, 'ʉ': 0.0, 'ɘ': 0.0, 'ə': 0.0, 'ɜ': 0.0,
	'ɐ': 0.0, 'ɵ': 0.0, 'ɞ': 0.0,
	'ɯ': 1.0, 'ɤ': 1.0, 'ʌ': 1.0,
	'u': 1.0, 'ʊ': 1.0, 'o': 1.0, 'ɔ': 1.0, 'ɑ': 1.0,
	'ɒ': 1.0, 'a': 0.0,
}

var roundMap = map[rune]float64{
	'y': 1.0, 'ʏ': 1.0, 'ø': 1.0, 'œ': 1.0, 'ɶ': 1.0,
	'ɵ': 1.0, 'ɞ': 1.0,
	'u': 1.0, 'ʊ': 1.0, 'ʉ': 1.0, 'o': 1.0, 'ɔ': 1.0, 'ɒ': 1.0,
}

var unroundSet = map[rune]bool{
	'i': true, 'ɪ': true, 'ɨ': true, 'ɯ': true, 'e': true,
	'ɛ': true, 'æ': true, 'ɘ': true, 'ɤ': true,
	'ə': true, 'ɐ': true, 'ɜ': true, 'ʌ': true, 'a': true, 'ɑ': true,
}

func refineVowel(base string, vector map[string]float64) {
	if base == "" {
		return
	}
	runes := []rune(base)
	if len(runes) == 0 {
		return
	}
	r := runes[0]
	if v, ok := heightMap[r]; ok {
		vector["high"] = v
	}
	if v, ok := backMap[r]; ok {
		vector["back"] = v
	}
	if v, ok := roundMap[r]; ok {
		vector["round"] = v
	} else if unroundSet[r] {
		vector["round"] = -1.0
	}
}

func applyTone(grapheme string, vector map[string]float64) {
	runes := []rune(grapheme)
	var digits []byte
	for i := len(runes) - 1; i >= 0; i-- {
		if d, ok := supToDigit[runes[i]]; ok {
			digits = append(digits, d)
		} else {
			break
		}
	}
	if len(digits) == 0 {
		return
	}
	for i, j := 0, len(digits)-1; i < j; i, j = i+1, j-1 {
		digits[i], digits[j] = digits[j], digits[i]
	}

	onsetVal := chaoValueMap[digits[0]]
	vector["tone_onset"] = onsetVal
	if len(digits) == 1 {
		vector["tone_mid"] = onsetVal
		vector["tone_offset"] = onsetVal
	} else if len(digits) == 2 {
		offsetVal := chaoValueMap[digits[len(digits)-1]]
		vector["tone_mid"] = (onsetVal + offsetVal) / 2.0
		vector["tone_offset"] = offsetVal
	} else {
		vector["tone_mid"] = chaoValueMap[digits[1]]
		vector["tone_offset"] = chaoValueMap[digits[len(digits)-1]]
	}
}

func (e *TrainedEngine) featureDistance(va, vb map[string]float64) float64 {
	total := 0.0
	for _, featName := range e.featureNames {
		aVal := va[featName]
		bVal := vb[featName]
		if aVal == 0.0 && bVal == 0.0 {
			continue
		}
		diff := math.Abs(aVal - bVal)
		dw := e.dimensionWeights[featName]
		if dw == 0.0 {
			dw = 1.0
		}
		nid := e.nodeInvDepths[featName]
		if nid == 0.0 {
			nid = 1.0 / float64(len(e.featureNames))
		}
		total += diff * dw * nid
	}
	return total
}

func (e *TrainedEngine) graphemeCost(a, b string) float64 {
	va := e.classifySegment(a)
	vb := e.classifySegment(b)
	if va == nil || vb == nil {
		return 1.0
	}
	clsA := e.classifyToClass(a)
	clsB := e.classifyToClass(b)
	classCost := 1.0
	if clsA != "" && clsB != "" {
		lo, hi := clsA, clsB
		if lo > hi {
			lo, hi = hi, lo
		}
		key := lo + ":" + hi
		if c, ok := e.classCosts[key]; ok {
			classCost = c
		} else if clsA == clsB {
			classCost = 0.0
		}
	}
	featDist := e.featureDistance(va, vb)
	return e.alpha*classCost + (1.0-e.alpha)*featDist
}

// ── System interface ────────────────────────────────────────────────

func (e *TrainedEngine) Name() string              { return e.config.Name }
func (e *TrainedEngine) RepresentationKind() string { return "valued" }

func (e *TrainedEngine) ListGraphemes() []string {
	result := make([]string, 0, len(e.ipaToClass))
	for g := range e.ipaToClass {
		result = append(result, g)
	}
	sort.Strings(result)
	return result
}

func (e *TrainedEngine) GraphemeToFeatures(grapheme string) (map[string]bool, bool) {
	vector := e.classifySegment(grapheme)
	if vector == nil {
		return nil, false
	}
	result := make(map[string]bool, len(vector))
	for name, val := range vector {
		var state string
		if val > 0 {
			state = "+"
		} else if val < 0 {
			state = "-"
		} else {
			state = "."
		}
		result[name+"="+state] = true
	}
	return result, true
}

func (e *TrainedEngine) FeatureDistance(a, b string) float64 {
	if a == b {
		return 0.0
	}
	return 1.0
}

func (e *TrainedEngine) SegmentDistance(a, b string, opts ...DistanceOption) float64 {
	return e.graphemeCost(a, b)
}

func (e *TrainedEngine) SoundDistance(featsA, featsB map[string]bool, opts ...DistanceOption) float64 {
	return 0.0
}

func (e *TrainedEngine) IsClass(grapheme string) bool {
	return false
}

func (e *TrainedEngine) ClassFeatures(grapheme string) (map[string]bool, bool) {
	return nil, false
}

