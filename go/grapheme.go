package merkmal

import (
	"math"
	"sort"
	"strings"
	"unicode"

	"golang.org/x/text/unicode/norm"
)

// ipaEquivalences are bidirectional canonical pairs: folded to the lookup form
// on input and mapped back to the preferred IPA glyph on output.
var ipaEquivalences = map[rune]rune{
	'ɡ': 'g', // U+0261 → U+0067
}

// ipaInputFolds are one-directional (NOT reversed on output): assorted
// apostrophes fold to the IPA modifier-letter apostrophe ʼ (U+02BC) used for
// ejectives. Reversing them would turn canonical ʼ into a typographic quote.
var ipaInputFolds = map[rune]rune{
	'\'': 'ʼ', // U+0027 APOSTROPHE → U+02BC MODIFIER LETTER APOSTROPHE
	'’':  'ʼ', // U+2019 RIGHT SINGLE QUOTATION MARK → U+02BC
}

var ipaInputMap map[rune]rune
var ipaReverse map[rune]rune

func init() {
	ipaInputMap = make(map[rune]rune, len(ipaEquivalences)+len(ipaInputFolds))
	for k, v := range ipaEquivalences {
		ipaInputMap[k] = v
	}
	for k, v := range ipaInputFolds {
		ipaInputMap[k] = v
	}
	ipaReverse = make(map[rune]rune, len(ipaEquivalences))
	for k, v := range ipaEquivalences {
		ipaReverse[v] = k
	}
}

const tieBar = '͡'
const tieBarStr = "͡"

// ligatureExpansions maps deprecated single-codepoint affricate ligatures to
// their digraph form. asciiToIPA maps the ASCII colon (a common length-mark
// substitute) to the IPA length mark. Both are one-directional (not reversed
// on output). stressMarksCutset holds the suprasegmental stress marks stripped
// on input — they carry no segmental features.
var ligatureExpansions = map[rune]string{
	'ʣ': "dz", 'ʤ': "dʒ", 'ʥ': "dʑ",
	'ʦ': "ts", 'ʧ': "tʃ", 'ʨ': "tɕ",
}
var asciiToIPA = map[rune]rune{
	':': 'ː',
}

const stressMarksCutset = "ˈˌ"

// resolveSlash resolves CLTS source/BIPA slash notation, keeping the
// post-slash value. CLTS writes "source/bipa" to record a literature grapheme
// before the slash and the BIPA value tools consume after it. Returns the
// substring after the last slash when present and non-empty, else unchanged.
func resolveSlash(grapheme string) string {
	if idx := strings.LastIndex(grapheme, "/"); idx >= 0 {
		if post := grapheme[idx+1:]; post != "" {
			return post
		}
	}
	return grapheme
}

// NormalizeInputGrapheme normalizes a lookup grapheme to its canonical BIPA
// segmental form: resolves CLTS slash notation (a/b → b), strips leading
// suprasegmental stress marks, applies NFD, expands deprecated affricate
// ligatures (ʤ → dʒ …), maps ASCII colon to the IPA length mark, and applies
// the reversible IPA equivalences (ɡ → g …).
func NormalizeInputGrapheme(grapheme string) string {
	grapheme = resolveSlash(grapheme)
	grapheme = strings.TrimLeft(grapheme, stressMarksCutset)
	nfd := norm.NFD.String(grapheme)
	var b strings.Builder
	b.Grow(len(nfd))
	for _, r := range nfd {
		if exp, ok := ligatureExpansions[r]; ok {
			b.WriteString(exp)
		} else if mapped, ok := asciiToIPA[r]; ok {
			b.WriteRune(mapped)
		} else if mapped, ok := ipaInputMap[r]; ok {
			b.WriteRune(mapped)
		} else {
			b.WriteRune(r)
		}
	}
	return b.String()
}

var postalveolarFricatives = map[rune]bool{'ʃ': true, 'ʒ': true}
var affricateStops = map[rune]bool{'t': true, 'd': true}

// NormalizeSequences returns candidate BIPA-style normalizations in
// priority order. Handles tie-bar stripping and postalveolar affricate
// retraction (tʃ → t̠ʃ, dʒ → d̠ʒ). Returns nil if no normalizations apply.
func NormalizeSequences(grapheme string) []string {
	var candidates []string
	withoutTie := strings.ReplaceAll(grapheme, tieBarStr, "")
	if withoutTie != grapheme {
		candidates = append(candidates, withoutTie)
	}
	base := withoutTie
	if withoutTie == grapheme {
		base = grapheme
	}
	retracted := insertAffricateRetraction(base)
	if retracted != base {
		candidates = append(candidates, retracted)
	}
	return candidates
}

func insertAffricateRetraction(text string) string {
	runes := []rune(text)
	var insertions []int
	i := 0
	for i < len(runes)-1 {
		if affricateStops[runes[i]] && postalveolarFricatives[runes[i+1]] {
			insertions = append(insertions, i+1)
			i += 2
		} else {
			i++
		}
	}
	if len(insertions) == 0 {
		return text
	}
	result := make([]rune, 0, len(runes)+len(insertions))
	ins := 0
	for j, r := range runes {
		if ins < len(insertions) && j == insertions[ins] {
			result = append(result, 0x0320)
			ins++
		}
		result = append(result, r)
	}
	return string(result)
}

// NormalizeOutputGrapheme maps canonical forms back to preferred IPA glyphs.
func NormalizeOutputGrapheme(grapheme string) string {
	var b strings.Builder
	b.Grow(len(grapheme))
	for _, r := range grapheme {
		if mapped, ok := ipaReverse[r]; ok {
			b.WriteRune(mapped)
		} else {
			b.WriteRune(r)
		}
	}
	return b.String()
}

// Normalize returns the canonical NFC IPA form of a grapheme, suitable for
// storage: resolves CLTS slash notation, strips stress, expands ligatures and
// ASCII colon, maps equivalences back to preferred IPA glyphs (g → ɡ), and
// recomposes to NFC. Returns "" for input that normalizes away entirely (e.g.
// a bare stress mark).
func Normalize(grapheme string) string {
	return norm.NFC.String(NormalizeOutputGrapheme(NormalizeInputGrapheme(grapheme)))
}

// ── Tone / combining / modifier tables ──────────────────────────────

var chaoSuperscriptDigits = map[rune]int{
	'⁰': 0, '¹': 1, '²': 2, '³': 3, '⁴': 4, '⁵': 5,
}

var isChaoDigit = func() map[rune]bool {
	m := make(map[rune]bool, len(chaoSuperscriptDigits))
	for r := range chaoSuperscriptDigits {
		m[r] = true
	}
	return m
}()

type toneLevels struct{ onset, mid, offset int }

var toneMarkToLevels = map[rune]toneLevels{
	0x030B: {5, 5, 5},
	0x0301: {4, 4, 4},
	0x0304: {3, 3, 3},
	0x0300: {2, 2, 2},
	0x030F: {1, 1, 1},
	0x0302: {4, 3, 2},
	0x030C: {2, 3, 4},
}

var levelToOnsetFeatures = map[int][]string{
	5: {"tone-onset-upper", "tone-onset-raised"},
	4: {"tone-onset-upper", "tone-onset-lowered"},
	3: nil,
	2: {"tone-onset-lower", "tone-onset-raised"},
	1: {"tone-onset-lower", "tone-onset-lowered"},
}

var levelToMidFeatures = map[int][]string{
	5: {"tone-mid-upper", "tone-mid-raised"},
	4: {"tone-mid-upper", "tone-mid-lowered"},
	3: nil,
	2: {"tone-mid-lower", "tone-mid-raised"},
	1: {"tone-mid-lower", "tone-mid-lowered"},
}

var levelToOffsetFeatures = map[int][]string{
	5: {"tone-offset-upper", "tone-offset-raised"},
	4: {"tone-offset-upper", "tone-offset-lowered"},
	3: nil,
	2: {"tone-offset-lower", "tone-offset-raised"},
	1: {"tone-offset-lower", "tone-offset-lowered"},
}

// ToneFeaturesForLevels returns tone features for given Chao onset/mid/offset levels.
func ToneFeaturesForLevels(onset, mid, offset int) map[string]bool {
	result := map[string]bool{}
	for _, f := range levelToOnsetFeatures[onset] {
		result[f] = true
	}
	for _, f := range levelToMidFeatures[mid] {
		result[f] = true
	}
	for _, f := range levelToOffsetFeatures[offset] {
		result[f] = true
	}
	return result
}

var combiningToFeature = map[rune]string{
	0x0325: "devoiced",
	0x030A: "devoiced",
	0x032C: "revoiced",
	0x0330: "creaky",
	0x0324: "breathy",
	0x0303: "nasalized",
	0x0329: "syllabic",
	0x030D: "syllabic",
	0x032F: "non-syllabic",
	0x032A: "dental",
	0x031F: "advanced",
	0x0320: "retracted",
	0x0318: "advanced-tongue-root",
	0x0319: "retracted-tongue-root",
	0x033A: "apical",
	0x033B: "laminal",
	0x033C: "linguolabial",
	0x031D: "raised",
	0x031E: "lowered",
	0x0308: "centralized",
	0x033D: "mid-centralized",
	0x031C: "less-rounded",
	0x0339: "more-rounded",
	0x0306: "ultra-short",
	0x031A: "unreleased",
	0x0348: "strong",
}

var suffixModifierToFeature = map[rune]string{
	0x02D0: "long",
	0x02D1: "mid-long",
	0x02B0: "aspirated",
	0x02B1: "breathy",
	0x02B2: "palatalized",
	0x02B7: "labialized",
	0x02E0: "velarized",
	0x02E4: "pharyngealized",
	0x02C0: "glottalized",
	0x02BC: "ejective",
	0x1DA3: "labio-palatalized",
	0x207F: "with-nasal-release",
	0x02DE: "rhotacized",
	0x02E1: "with-lateral-release",
}

var prefixModifierToFeature = map[rune]string{
	0x02B0: "pre-aspirated",
	0x02C0: "pre-glottalized",
	0x207F: "pre-nasalized",
	0x02B7: "pre-labialized",
	0x02B2: "pre-palatalized",
}

func isMark(r rune) bool {
	return unicode.Is(unicode.Mn, r) || unicode.Is(unicode.Mc, r) || unicode.Is(unicode.Me, r)
}

func isLmOrSk(r rune) bool {
	return unicode.Is(unicode.Lm, r) || unicode.Is(unicode.Sk, r)
}

// ParseChaoDigits parses Chao superscript digit sequences into onset/mid/offset.
func ParseChaoDigits(text string) (onset, mid, offset int, ok bool) {
	var digits []int
	for _, r := range text {
		if d, found := chaoSuperscriptDigits[r]; found {
			digits = append(digits, d)
		}
	}
	if len(digits) == 0 {
		return 0, 0, 0, false
	}
	allZero := true
	for _, d := range digits {
		if d != 0 {
			allZero = false
			break
		}
	}
	if allZero {
		return 0, 0, 0, false
	}
	o := digits[0]
	off := digits[len(digits)-1]
	if o == 0 {
		o = off
	}
	if off == 0 {
		off = o
	}
	if len(digits) == 1 {
		return o, o, o, true
	}
	if len(digits) == 2 {
		m := int(math.Round(float64(o+off) / 2.0))
		return o, m, off, true
	}
	m := digits[1]
	if m == 0 {
		m = int(math.Round(float64(o+off) / 2.0))
	}
	return o, m, off, true
}

// DecomposeGrapheme extracts base characters and modifier features from a grapheme.
func DecomposeGrapheme(grapheme string) (base string, features map[string]bool) {
	runes := []rune(grapheme)
	features = map[string]bool{}

	prefixEnd := 0
	for i, r := range runes {
		if isLmOrSk(r) {
			if feat, ok := prefixModifierToFeature[r]; ok {
				features[feat] = true
				prefixEnd = i + 1
				continue
			}
		}
		break
	}

	remainder := runes[prefixEnd:]

	tailStart := len(remainder)
	for k := len(remainder) - 1; k >= 0; k-- {
		if isChaoDigit[remainder[k]] {
			tailStart = k
		} else {
			break
		}
	}

	var baseChars []rune
	var chaoChars []rune

	for idx, r := range remainder {
		if idx >= tailStart {
			chaoChars = append(chaoChars, r)
			continue
		}
		if levels, ok := toneMarkToLevels[r]; ok {
			for f := range ToneFeaturesForLevels(levels.onset, levels.mid, levels.offset) {
				features[f] = true
			}
		} else if isMark(r) {
			if feat, ok := combiningToFeature[r]; ok {
				features[feat] = true
			} else {
				baseChars = append(baseChars, r)
			}
		} else if isLmOrSk(r) {
			if feat, ok := suffixModifierToFeature[r]; ok {
				features[feat] = true
			} else {
				baseChars = append(baseChars, r)
			}
		} else {
			baseChars = append(baseChars, r)
		}
	}

	if len(chaoChars) > 0 {
		o, m, off, ok := ParseChaoDigits(string(chaoChars))
		if ok {
			for f := range ToneFeaturesForLevels(o, m, off) {
				features[f] = true
			}
		}
	}

	return string(baseChars), features
}

// ComposeGrapheme reconstructs a grapheme from base + modifiers.
func ComposeGrapheme(base string, modifiers map[string]bool) string {
	ftm := buildFeatureToModifier()
	sorted := make([]string, 0, len(modifiers))
	for f := range modifiers {
		sorted = append(sorted, f)
	}
	sort.Strings(sorted)

	var b strings.Builder
	b.WriteString(base)
	for _, feat := range sorted {
		if ch, ok := ftm[feat]; ok {
			b.WriteRune(ch)
		}
	}
	return b.String()
}

func buildFeatureToModifier() map[string]rune {
	result := make(map[string]rune)
	for cp, feat := range combiningToFeature {
		if _, exists := result[feat]; !exists {
			result[feat] = cp
		}
	}
	for cp, feat := range suffixModifierToFeature {
		result[feat] = cp
	}
	return result
}

var nonPulmonicFeatures = map[string]bool{
	"click": true, "nasal-click": true, "implosive": true,
}

// EnrichClickFeatures adds non-pulmonic and velar features for clicks/implosives.
func EnrichClickFeatures(features map[string]bool) map[string]bool {
	hasNonPulmonic := false
	for f := range nonPulmonicFeatures {
		if features[f] {
			hasNonPulmonic = true
			break
		}
	}
	if !hasNonPulmonic {
		return features
	}
	result := make(map[string]bool, len(features)+2)
	for k := range features {
		result[k] = true
	}
	result["non-pulmonic"] = true
	if features["click"] || features["nasal-click"] {
		result["velar"] = true
	}
	return result
}

// ── Tone digit merging ──────────────────────────────────────────────

var vowelRunes = func() map[rune]bool {
	m := make(map[rune]bool)
	for _, r := range "aeiouyɛɔəɨʉɯɵœæɐɑʌɪʊɤøɘɜɞɒɶɿʅ" {
		m[r] = true
	}
	return m
}()

const syllabicCombining = '̩'

func isToneDigitString(s string) bool {
	if s == "" {
		return false
	}
	for _, r := range s {
		if !isChaoDigit[r] {
			return false
		}
	}
	return true
}

func isSyllabic(segment string) bool {
	for _, r := range segment {
		if r == syllabicCombining {
			return true
		}
	}
	for _, r := range segment {
		if !unicode.Is(unicode.Mn, r) && !unicode.Is(unicode.Mc, r) && !unicode.Is(unicode.Me, r) {
			if vowelRunes[unicode.ToLower(r)] {
				return true
			}
		}
	}
	return false
}

// MergeToneDigits merges Chao tone digit segments onto their syllabic nucleus.
// Tone groups that parse to all-zero are dropped; valid ones attach to the
// nearest preceding syllabic segment (not crossing "+" boundaries).
func MergeToneDigits(segments []string) []string {
	result := make([]string, len(segments))
	copy(result, segments)

	for i := len(result) - 1; i >= 0; i-- {
		if !isToneDigitString(result[i]) {
			continue
		}
		tone := result[i]
		_, _, _, ok := ParseChaoDigits(tone)
		// Remove the tone segment
		result = append(result[:i], result[i+1:]...)
		if !ok {
			continue
		}
		// Attach to nearest preceding syllabic
		for j := i - 1; j >= 0; j-- {
			if result[j] == "+" {
				break
			}
			if isSyllabic(result[j]) {
				result[j] = result[j] + tone
				break
			}
		}
	}
	return result
}

// ── Valued-feature modifier effects ─────────────────────────────────

type modifierEffect struct {
	alternatives []string
	state        FeatureState
}

var modifierToValuedEffect = map[string]modifierEffect{
	"devoiced":              {[]string{"periodicGlottalSource", "voice", "voiced"}, StateNegative},
	"revoiced":              {[]string{"periodicGlottalSource", "voice", "voiced"}, StatePositive},
	"aspirated":             {[]string{"spreadGlottis", "spread"}, StatePositive},
	"breathy":               {[]string{"spreadGlottis", "spread"}, StatePositive},
	"creaky":                {[]string{"constrictedGlottis", "constr"}, StatePositive},
	"nasalized":             {[]string{"nasal"}, StatePositive},
	"long":                  {[]string{"long", "LONG"}, StatePositive},
	"dental":                {[]string{"distributed"}, StatePositive},
	"syllabic":              {[]string{"syllabic", "SYLLABIC"}, StatePositive},
	"non-syllabic":          {[]string{"syllabic", "SYLLABIC"}, StateNegative},
	"ejective":              {[]string{"raisedLarynxEjective", "constrictedGlottis", "constr"}, StatePositive},
	"glottalized":           {[]string{"constrictedGlottis", "constr"}, StatePositive},
	"palatalized":           {[]string{"high"}, StatePositive},
	"labialized":            {[]string{"round"}, StatePositive},
	"more-rounded":          {[]string{"round"}, StatePositive},
	"less-rounded":          {[]string{"round"}, StateNegative},
	"velarized":             {[]string{"dorsal"}, StatePositive},
	"pharyngealized":        {[]string{"retractedTongueRoot"}, StatePositive},
	"advanced-tongue-root":  {[]string{"advancedTongueRoot", "ATR"}, StatePositive},
	"retracted-tongue-root": {[]string{"retractedTongueRoot"}, StatePositive},
}

// ApplyModifierEffects applies modifier effects to a copy of base valued features.
func ApplyModifierEffects(baseValues map[string]FeatureState, modifiers map[string]bool, modelFeatures map[string]bool) map[string]FeatureState {
	result := make(map[string]FeatureState, len(baseValues))
	for k, v := range baseValues {
		result[k] = v
	}
	for modifier := range modifiers {
		effect, ok := modifierToValuedEffect[modifier]
		if !ok {
			continue
		}
		for _, featName := range effect.alternatives {
			if modelFeatures[featName] {
				result[featName] = effect.state
				break
			}
		}
	}
	return result
}

// ── IPA segmentation ────────────────────────────────────────────────

var tieBarSet = map[rune]bool{'͡': true, '͜': true}
var boundaryChars = map[rune]bool{'+': true, '.': true, '|': true, '‖': true}

// SegmentIPA segments an IPA string into individual phones.
// Chao tone digits are emitted as separate tokens; use MergeToneDigits
// to attach them to syllabic nuclei.
func SegmentIPA(ipa string) []string {
	nfd := norm.NFD.String(ipa)
	runes := []rune(nfd)
	var result []string
	var current []rune
	hasBase := false
	afterTie := false

	flush := func() {
		if len(current) > 0 {
			result = append(result, string(current))
			current = current[:0]
		}
		hasBase = false
		afterTie = false
	}

	i := 0
	for i < len(runes) {
		r := runes[i]

		if isChaoDigit[r] {
			flush()
			start := i
			for i < len(runes) && isChaoDigit[runes[i]] {
				i++
			}
			result = append(result, string(runes[start:i]))
			continue
		}

		if r == ' ' {
			flush()
			i++
			continue
		}

		if boundaryChars[r] {
			flush()
			result = append(result, string(r))
			i++
			continue
		}

		if tieBarSet[r] {
			current = append(current, r)
			afterTie = true
			i++
			continue
		}

		if isMark(r) {
			current = append(current, r)
			i++
			continue
		}

		if isLmOrSk(r) {
			_, isPre := prefixModifierToFeature[r]
			_, isSuf := suffixModifierToFeature[r]
			if hasBase || isPre || isSuf {
				current = append(current, r)
			} else {
				if hasBase && !afterTie {
					flush()
				}
				current = append(current, r)
				hasBase = true
				afterTie = false
			}
			i++
			continue
		}

		// Base letter
		if hasBase && !afterTie {
			flush()
		}
		current = append(current, r)
		hasBase = true
		afterTie = false
		i++
	}

	flush()
	return result
}

// ── Set helpers ─────────────────────────────────────────────────────

func mergeSets(sets ...map[string]bool) map[string]bool {
	size := 0
	for _, s := range sets {
		size += len(s)
	}
	result := make(map[string]bool, size)
	for _, s := range sets {
		for k := range s {
			result[k] = true
		}
	}
	return result
}

func featureSetKey(features map[string]bool) string {
	sorted := make([]string, 0, len(features))
	for f := range features {
		sorted = append(sorted, f)
	}
	sort.Strings(sorted)
	return strings.Join(sorted, "|")
}
