package merkmal

import (
	"encoding/json"
	"fmt"
	"io/fs"
	"sort"
	"strconv"
	"strings"
)

// toneLevels holds Chao onset/mid/offset levels for a tone diacritic.
type toneLevels struct{ onset, mid, offset int }

// modifierEffect is the valued-feature change a modifier applies.
type modifierEffect struct {
	alternatives []string
	state        FeatureState
}

// DiacriticTable bundles the diacritic/modifier/tone → feature mappings
// and the decomposition logic that uses them. The feature *names* a
// modifier produces are part of a feature system's vocabulary, so the
// table is data-drivable: see LoadDiacritics. DefaultDiacritics is the
// built-in IPA/CLTS set.
type DiacriticTable struct {
	Name          string
	Combining     map[rune]string
	Suffix        map[rune]string
	Prefix        map[rune]string
	ToneMarks     map[rune]toneLevels
	ToneOnset     map[int][]string
	ToneMid       map[int][]string
	ToneOffset    map[int][]string
	ValuedEffects map[string]modifierEffect

	featureToModifier map[string]rune
}

func (d *DiacriticTable) reverseMap() map[string]rune {
	if d.featureToModifier != nil {
		return d.featureToModifier
	}
	result := make(map[string]rune)
	for cp, feat := range d.Combining {
		if _, exists := result[feat]; !exists {
			result[feat] = cp
		}
	}
	for cp, feat := range d.Suffix {
		result[feat] = cp
	}
	d.featureToModifier = result
	return result
}

// ToneFeaturesForLevels returns tone features for Chao onset/mid/offset levels.
func (d *DiacriticTable) ToneFeaturesForLevels(onset, mid, offset int) map[string]bool {
	result := map[string]bool{}
	for _, f := range d.ToneOnset[onset] {
		result[f] = true
	}
	for _, f := range d.ToneMid[mid] {
		result[f] = true
	}
	for _, f := range d.ToneOffset[offset] {
		result[f] = true
	}
	return result
}

// Decompose extracts base characters and modifier features from a grapheme.
func (d *DiacriticTable) Decompose(grapheme string) (base string, features map[string]bool) {
	runes := []rune(grapheme)
	features = map[string]bool{}

	prefixEnd := 0
	for i, r := range runes {
		if isLmOrSk(r) {
			if feat, ok := d.Prefix[r]; ok {
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
		if levels, ok := d.ToneMarks[r]; ok {
			for f := range d.ToneFeaturesForLevels(levels.onset, levels.mid, levels.offset) {
				features[f] = true
			}
		} else if isMark(r) {
			if feat, ok := d.Combining[r]; ok {
				features[feat] = true
			} else {
				baseChars = append(baseChars, r)
			}
		} else if isLmOrSk(r) {
			if feat, ok := d.Suffix[r]; ok {
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
			for f := range d.ToneFeaturesForLevels(o, m, off) {
				features[f] = true
			}
		}
	}

	return string(baseChars), features
}

// Compose reconstructs a grapheme from base + modifier features.
func (d *DiacriticTable) Compose(base string, modifiers map[string]bool) string {
	ftm := d.reverseMap()
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

// ApplyValuedEffects applies modifier effects to a copy of base valued features.
func (d *DiacriticTable) ApplyValuedEffects(baseValues map[string]FeatureState, modifiers, modelFeatures map[string]bool) map[string]FeatureState {
	result := make(map[string]FeatureState, len(baseValues))
	for k, v := range baseValues {
		result[k] = v
	}
	for modifier := range modifiers {
		effect, ok := d.ValuedEffects[modifier]
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

// ── Built-in IPA / CLTS default ─────────────────────────────────────────

const defaultDiacriticsName = "ipa-clts"

func levelFeatures(prefix string) map[int][]string {
	return map[int][]string{
		5: {"tone-" + prefix + "-upper", "tone-" + prefix + "-raised"},
		4: {"tone-" + prefix + "-upper", "tone-" + prefix + "-lowered"},
		3: nil,
		2: {"tone-" + prefix + "-lower", "tone-" + prefix + "-raised"},
		1: {"tone-" + prefix + "-lower", "tone-" + prefix + "-lowered"},
	}
}

// DefaultDiacritics is the built-in IPA/CLTS diacritic table.
var DefaultDiacritics = &DiacriticTable{
	Name: defaultDiacriticsName,
	Combining: map[rune]string{
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
	},
	Suffix: map[rune]string{
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
	},
	Prefix: map[rune]string{
		0x02B0: "pre-aspirated",
		0x02C0: "pre-glottalized",
		0x207F: "pre-nasalized",
		0x02B7: "pre-labialized",
		0x02B2: "pre-palatalized",
	},
	ToneMarks: map[rune]toneLevels{
		0x030B: {5, 5, 5},
		0x0301: {4, 4, 4},
		0x0304: {3, 3, 3},
		0x0300: {2, 2, 2},
		0x030F: {1, 1, 1},
		0x0302: {4, 3, 2},
		0x030C: {2, 3, 4},
	},
	ToneOnset:  levelFeatures("onset"),
	ToneMid:    levelFeatures("mid"),
	ToneOffset: levelFeatures("offset"),
	ValuedEffects: map[string]modifierEffect{
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
	},
}

// ── Loading from JSON ────────────────────────────────────────────────────

type jsonDiacritics struct {
	Name          string                         `json:"name"`
	Combining     map[string]string              `json:"combining"`
	Suffix        map[string]string              `json:"suffix"`
	Prefix        map[string]string              `json:"prefix"`
	ToneMarks     map[string][]int               `json:"tone_marks"`
	ToneLevels    map[string]map[string][]string `json:"tone_levels"`
	ValuedEffects map[string]jsonValuedEffect    `json:"valued_effects"`
}

type jsonValuedEffect struct {
	Features []string `json:"features"`
	State    string   `json:"state"`
}

func parseCPMap(raw map[string]string) (map[rune]string, error) {
	out := make(map[rune]string, len(raw))
	for k, v := range raw {
		cp, err := strconv.ParseInt(k, 16, 32)
		if err != nil {
			return nil, fmt.Errorf("invalid codepoint %q: %w", k, err)
		}
		out[rune(cp)] = v
	}
	return out, nil
}

func parseLevels(raw map[string][]string) map[int][]string {
	out := make(map[int][]string, len(raw))
	for k, v := range raw {
		n, err := strconv.Atoi(k)
		if err != nil {
			continue
		}
		out[n] = v
	}
	return out
}

// LoadDiacritics reads a diacritic table JSON file from an fs.FS.
func LoadDiacritics(fsys fs.FS, name string) (*DiacriticTable, error) {
	data, err := fs.ReadFile(fsys, name+".json")
	if err != nil {
		return nil, fmt.Errorf("diacritics not found: %s (%w)", name, err)
	}
	var raw jsonDiacritics
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("parsing diacritics %s: %w", name, err)
	}

	combining, err := parseCPMap(raw.Combining)
	if err != nil {
		return nil, err
	}
	suffix, err := parseCPMap(raw.Suffix)
	if err != nil {
		return nil, err
	}
	prefix, err := parseCPMap(raw.Prefix)
	if err != nil {
		return nil, err
	}

	toneMarks := make(map[rune]toneLevels, len(raw.ToneMarks))
	for k, v := range raw.ToneMarks {
		cp, err := strconv.ParseInt(k, 16, 32)
		if err != nil || len(v) != 3 {
			return nil, fmt.Errorf("invalid tone_mark %q", k)
		}
		toneMarks[rune(cp)] = toneLevels{v[0], v[1], v[2]}
	}

	effects := make(map[string]modifierEffect, len(raw.ValuedEffects))
	for mod, spec := range raw.ValuedEffects {
		state, err := parseStateSymbol(spec.State)
		if err != nil {
			return nil, fmt.Errorf("valued_effect %q: %w", mod, err)
		}
		effects[mod] = modifierEffect{alternatives: spec.Features, state: state}
	}

	d := &DiacriticTable{
		Name:          orDefault(raw.Name, name),
		Combining:     combining,
		Suffix:        suffix,
		Prefix:        prefix,
		ToneMarks:     toneMarks,
		ToneOnset:     parseLevels(raw.ToneLevels["onset"]),
		ToneMid:       parseLevels(raw.ToneLevels["mid"]),
		ToneOffset:    parseLevels(raw.ToneLevels["offset"]),
		ValuedEffects: effects,
	}
	return d, nil
}

func orDefault(s, fallback string) string {
	if s == "" {
		return fallback
	}
	return s
}

func parseStateSymbol(s string) (FeatureState, error) {
	switch s {
	case string(StatePositive):
		return StatePositive, nil
	case string(StateNegative):
		return StateNegative, nil
	default:
		// Allow word forms for readability.
		switch strings.ToLower(s) {
		case "positive", "+":
			return StatePositive, nil
		case "negative", "-":
			return StateNegative, nil
		}
		return "", fmt.Errorf("unknown feature state %q", s)
	}
}
