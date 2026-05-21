package merkmal

import (
	"math"
	"sort"
	"strings"
)

// CategoricalEngine implements System for categorical feature models
// (descriptive, broad, distinctive).
type CategoricalEngine struct {
	config   *ModelConfig
	geometry *Geometry

	graphemeTable    map[string]map[string]bool
	reverseTable     map[string]string
	classTable       map[string]map[string]bool
	dimensionWeights map[string]float64
}

// NewCategoricalEngine creates a categorical engine from config and geometry.
func NewCategoricalEngine(config *ModelConfig, geom *Geometry) *CategoricalEngine {
	e := &CategoricalEngine{
		config:   config,
		geometry: geom,
	}
	e.buildTables()
	return e
}

func (e *CategoricalEngine) buildTables() {
	filterCategories := e.config.FeatureExtraction == "filtered"

	e.graphemeTable = make(map[string]map[string]bool)
	for _, row := range e.config.InventoryRows {
		if len(row) < 2 {
			continue
		}
		grapheme, soundName := row[0], row[1]
		features := ParseSoundName(soundName, e.config.FeatureCategories, filterCategories)
		if len(features) > 0 {
			e.graphemeTable[NormalizeInputGrapheme(grapheme)] = features
		}
	}

	e.reverseTable = make(map[string]string)
	for grapheme, features := range e.graphemeTable {
		key := featureSetKey(features)
		if _, exists := e.reverseTable[key]; !exists {
			e.reverseTable[key] = NormalizeOutputGrapheme(grapheme)
		}
	}

	e.classTable = make(map[string]map[string]bool)
	for className, classDef := range e.config.ClassesData {
		if classDef.Features == "" {
			continue
		}
		features := make(map[string]bool)
		for _, v := range strings.Split(classDef.Features, ",") {
			v = strings.TrimSpace(v)
			if v != "" {
				features[v] = true
			}
		}
		if len(features) > 0 {
			e.classTable[className] = features
		}
	}

	e.dimensionWeights = make(map[string]float64)
	for _, dim := range e.config.ScalarDimensions {
		depth := e.geometry.NodeDepth(dim.GeometryNode)
		e.dimensionWeights[dim.Name] = 1.0 / float64(depth)
	}
}

// ParseSoundName parses an IPA sound name into a feature set.
func ParseSoundName(name string, featureCategories map[string]string, filterCategories bool) map[string]bool {
	features := map[string]bool{}
	for _, word := range strings.Fields(name) {
		value := strings.ToLower(strings.TrimSpace(word))
		value = strings.ReplaceAll(value, "_", "-")
		if value == "" {
			continue
		}
		if !filterCategories {
			features[value] = true
			continue
		}
		if _, exists := featureCategories[value]; exists {
			features[value] = true
		}
	}
	return features
}

// ── System interface ────────────────────────────────────────────────

func (e *CategoricalEngine) Name() string              { return e.config.Name }
func (e *CategoricalEngine) RepresentationKind() string { return "categorical" }

func (e *CategoricalEngine) ListGraphemes() []string {
	result := make([]string, 0, len(e.graphemeTable))
	for g := range e.graphemeTable {
		result = append(result, NormalizeOutputGrapheme(g))
	}
	sort.Strings(result)
	return result
}

func (e *CategoricalEngine) GraphemeToFeatures(grapheme string) (map[string]bool, bool) {
	normalized := NormalizeInputGrapheme(grapheme)

	if result, ok := e.graphemeTable[normalized]; ok {
		return EnrichClickFeatures(result), true
	}

	if result := e.resolveTieBar(normalized); result != nil {
		return EnrichClickFeatures(result), true
	}

	base, added := DecomposeGrapheme(normalized)
	if base != normalized {
		baseFeatures, ok := e.graphemeTable[base]
		if !ok {
			baseFeatures = e.resolveTieBar(base)
			ok = baseFeatures != nil
		}
		if ok {
			return EnrichClickFeatures(mergeSets(baseFeatures, added)), true
		}
	}

	if result := e.resolvePolyphthong(base); result != nil {
		return EnrichClickFeatures(mergeSets(result, added)), true
	}

	return nil, false
}

func (e *CategoricalEngine) resolveTieBar(grapheme string) map[string]bool {
	for _, tie := range []string{"͡", "͜"} {
		idx := strings.Index(grapheme, tie)
		if idx < 0 {
			continue
		}
		a := grapheme[:idx]
		b := grapheme[idx+len(tie):]
		featsA, okA := e.graphemeTable[a]
		featsB, okB := e.graphemeTable[b]
		if okA && okB {
			return mergeSets(featsA, featsB)
		}
	}
	return nil
}

func (e *CategoricalEngine) resolvePolyphthong(grapheme string) map[string]bool {
	runes := []rune(grapheme)
	if len(runes) < 2 {
		return nil
	}
	var segments []map[string]bool
	i := 0
	for i < len(runes) {
		matched := false
		for end := len(runes); end > i; end-- {
			candidate := string(runes[i:end])
			if feats, ok := e.graphemeTable[candidate]; ok {
				segments = append(segments, feats)
				i = end
				matched = true
				break
			}
		}
		if !matched {
			return nil
		}
	}
	if len(segments) < 2 {
		return nil
	}
	for _, seg := range segments {
		if !seg["vowel"] {
			return nil
		}
	}
	return mergeSets(segments...)
}

func (e *CategoricalEngine) FeatureDistance(a, b string) float64 {
	return float64(e.geometry.FeatureDistance(a, b))
}

func (e *CategoricalEngine) SegmentDistance(a, b string, opts ...DistanceOption) float64 {
	featsA, okA := e.GraphemeToFeatures(a)
	featsB, okB := e.GraphemeToFeatures(b)
	if !okA || !okB {
		return 1.0
	}
	return e.SoundDistance(featsA, featsB, opts...)
}

func (e *CategoricalEngine) SoundDistance(featsA, featsB map[string]bool, opts ...DistanceOption) float64 {
	if len(e.config.ScalarDimensions) > 0 {
		return e.scalarSoundDistance(featsA, featsB, opts...)
	}
	return e.geometry.SoundDistance(featsA, featsB, opts...)
}

func (e *CategoricalEngine) IsClass(grapheme string) bool {
	_, ok := e.classTable[grapheme]
	return ok
}

func (e *CategoricalEngine) ClassFeatures(grapheme string) (map[string]bool, bool) {
	feats, ok := e.classTable[grapheme]
	return feats, ok
}

// ── Scalar dimension overlay (distinctive) ──────────────────────────

func (e *CategoricalEngine) featuresToScalar(features map[string]bool) map[string]float64 {
	result := map[string]float64{}
	for _, dim := range e.config.ScalarDimensions {
		found := false
		for _, pos := range dim.Positive {
			if features[pos] {
				result[dim.Name] = 1.0
				found = true
				break
			}
		}
		if found {
			continue
		}
		if len(dim.Negative) > 0 {
			for _, neg := range dim.Negative {
				if features[neg] {
					result[dim.Name] = -1.0
					break
				}
			}
		}
	}
	return result
}

func (e *CategoricalEngine) scalarSoundDistance(featsA, featsB map[string]bool, opts ...DistanceOption) float64 {
	if mapsEqual(featsA, featsB) {
		return 0.0
	}

	cfg := applyOpts(opts)
	resolved := e.geometry.resolveWeights(cfg)
	flat := resolved != nil && isFlat(resolved)
	var ancestorMap map[string][]string
	if resolved != nil && !flat {
		ancestorMap = buildAncestorMap(e.geometry.Tree, nil)
	}

	scalarsA := e.featuresToScalar(featsA)
	scalarsB := e.featuresToScalar(featsB)
	totalWeight := 0.0
	totalDiff := 0.0

	for _, dim := range e.config.ScalarDimensions {
		var weight float64
		if flat {
			weight = 1.0
		} else {
			nw := 1.0
			if resolved != nil {
				nw = resolveNodeWeight(dim.GeometryNode, resolved, ancestorMap)
			}
			weight = e.dimensionWeights[dim.Name] * nw
		}

		valueA := scalarsA[dim.Name]
		valueB := scalarsB[dim.Name]
		if valueA == 0.0 && valueB == 0.0 {
			continue
		}

		totalWeight += weight
		divisor := 2.0
		if len(dim.Negative) == 0 {
			divisor = 1.0
		}
		totalDiff += weight * math.Abs(valueA-valueB) / divisor
	}

	if totalWeight > 0 {
		return totalDiff / totalWeight
	}
	return 0.0
}
