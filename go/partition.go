package merkmal

import (
	"sort"
	"strconv"
	"strings"
)

var partitionLevels = []string{"prosody", "coarse", "medium", "fine"}

var roleToTypeName = map[string]string{
	"C": "consonant",
	"R": "consonant",
	"G": "consonant",
	"V": "vowel",
	"T": "tone",
	"S": "suprasegmental",
	"X": "unclassified",
}

var typeCode = map[string]string{
	"consonant":      "C",
	"vowel":          "V",
	"tone":           "T",
	"suprasegmental": "S",
	"unclassified":   "X",
}

// ── Role derivation ────────────────────────────────────────────────

var roleRFeatures = map[string]bool{
	"nasal": true, "lateral": true, "trill": true,
	"tap": true, "flap": true, "sonorant": true,
}

var roleCFeatures = map[string]bool{
	"stop": true, "plosive": true, "fricative": true,
	"affricate": true, "implosive": true, "click": true,
}

var roleGFeatures = map[string]bool{
	"approximant": true, "semi-vowel": true,
}

var roleRStates = map[string]bool{
	"nasal=+": true, "lateral=+": true, "trill=+": true,
	"tap=+": true, "sonorant=+": true,
}

var roleGStates = map[string]bool{"approximant=+": true}

var toneLetters = map[rune]bool{
	'˥': true, '˦': true, '˧': true, '˨': true, '˩': true,
}

var chaoSuperscripts = map[rune]bool{
	'⁰': true, '¹': true, '²': true, '³': true, '⁴': true, '⁵': true,
}

var standaloneSupraseg = map[string]bool{
	"ˈ": true, "ˌ": true, "ː": true, "ˑ": true,
}

func roleFromPlainFeatures(feats map[string]bool) string {
	if feats["vowel"] {
		return "V"
	}
	if feats["consonant"] {
		for f := range roleRFeatures {
			if feats[f] {
				return "R"
			}
		}
		for f := range roleGFeatures {
			if feats[f] {
				return "G"
			}
		}
		for f := range roleCFeatures {
			if feats[f] {
				return "C"
			}
		}
		return ""
	}
	return ""
}

func roleFromValuedFeatures(feats map[string]bool) string {
	if feats["syllabic=+"] {
		return "V"
	}
	if feats["consonantal=+"] || feats["consonant=+"] {
		for s := range roleRStates {
			if feats[s] {
				return "R"
			}
		}
		if feats["approximant=+"] {
			return "G"
		}
		return "C"
	}
	if feats["sonorant=+"] && feats["approximant=+"] {
		return "G"
	}
	return ""
}

func isToneToken(grapheme string) bool {
	if grapheme == "" {
		return false
	}
	for _, ch := range grapheme {
		if toneLetters[ch] || chaoSuperscripts[ch] || (ch >= '0' && ch <= '9') {
			continue
		}
		return false
	}
	return true
}

// DeriveRole returns the prosodic role for a grapheme.
func DeriveRole(grapheme string, sys System) Role {
	feats, ok := sys.GraphemeToFeatures(grapheme)
	if ok && feats != nil {
		if r := roleFromPlainFeatures(feats); r != "" {
			return Role(r[0])
		}
		if r := roleFromValuedFeatures(feats); r != "" {
			return Role(r[0])
		}
	}
	if isToneToken(grapheme) {
		return RoleT
	}
	if standaloneSupraseg[grapheme] {
		return RoleS
	}
	return RoleUnknown
}

// ── Signature computation ──────────────────────────────────────────

type signature struct {
	typeName  string
	slotNames []string
	values    []string
	valued    bool
}

func (s *signature) classFull() string {
	if s.typeName == "unclassified" {
		return "unclassified"
	}
	parts := []string{s.typeName}
	if s.valued {
		for i, name := range s.slotNames {
			v := s.values[i]
			if v == "" {
				parts = append(parts, name+"=?")
			} else {
				parts = append(parts, name+"="+v)
			}
		}
	} else {
		for _, v := range s.values {
			if v == "" {
				parts = append(parts, "?")
			} else {
				parts = append(parts, v)
			}
		}
	}
	return strings.Join(parts, "|")
}

func (s *signature) tentativeCode() string {
	if s.typeName == "unclassified" {
		return "X"
	}
	prefix := typeCode[s.typeName]
	if len(s.values) == 0 {
		return prefix
	}
	var shorts []string
	for _, v := range s.values {
		if s.valued {
			shorts = append(shorts, valuedShort(v))
		} else {
			shorts = append(shorts, categoricalShort(v))
		}
	}
	return prefix + "." + strings.Join(shorts, "")
}

func valuedShort(value string) string {
	if value == "" {
		return "x"
	}
	mapping := map[byte]string{'+': "p", '-': "n", '0': "z"}
	if s, ok := mapping[value[0]]; ok {
		return s
	}
	return strings.ToLower(value[:1])
}

func categoricalShort(value string) string {
	if value == "" {
		return "x"
	}
	return strings.ToLower(value[:1])
}

// ── Feature projection ─────────────────────────────────────────────

func projectCategorical(
	features map[string]bool,
	slots []string,
	featureCategories map[string]string,
) []string {
	byCategory := make(map[string][]string, len(slots))
	for _, s := range slots {
		byCategory[s] = nil
	}
	for feat := range features {
		cat := featureCategories[feat]
		if _, ok := byCategory[cat]; ok {
			byCategory[cat] = append(byCategory[cat], feat)
		}
	}
	result := make([]string, len(slots))
	for i, s := range slots {
		vals := byCategory[s]
		sort.Strings(vals)
		result[i] = strings.Join(vals, "+")
	}
	return result
}

func projectValued(features map[string]bool, slots []string) []string {
	featMap := make(map[string]string)
	for feat := range features {
		name, state, found := strings.Cut(feat, "=")
		if found {
			featMap[name] = state
		}
	}
	result := make([]string, len(slots))
	for i, s := range slots {
		result[i] = featMap[s]
	}
	return result
}

func signatureFor(
	features map[string]bool,
	role, level string,
	partitionSlots map[string]map[string][]string,
	isCategorical bool,
	featureCategories map[string]string,
) *signature {
	typeName := roleToTypeName[role]
	if role == "X" {
		return &signature{typeName: typeName}
	}
	var roleKey string
	switch role {
	case "C", "R", "G":
		roleKey = "C"
	case "V":
		roleKey = "V"
	default:
		return &signature{typeName: typeName, valued: !isCategorical}
	}
	levelSpec := partitionSlots[level]
	if levelSpec == nil {
		levelSpec = map[string][]string{}
	}
	slots := levelSpec[roleKey]
	if isCategorical {
		values := projectCategorical(features, slots, featureCategories)
		return &signature{typeName: typeName, slotNames: slots, values: values}
	}
	values := projectValued(features, slots)
	return &signature{typeName: typeName, slotNames: slots, values: values, valued: true}
}

func assignCodes(classFulls []string, tentatives map[string]string) map[string]string {
	unique := make([]string, 0)
	seen := map[string]bool{}
	for _, f := range classFulls {
		if !seen[f] {
			unique = append(unique, f)
			seen[f] = true
		}
	}
	sort.Strings(unique)

	groups := map[string][]string{}
	for _, full := range unique {
		code := tentatives[full]
		groups[code] = append(groups[code], full)
	}

	result := map[string]string{}
	for code, fulls := range groups {
		if len(fulls) == 1 {
			result[fulls[0]] = code
		} else {
			for idx, full := range fulls {
				result[full] = code + "_" + strconv.Itoa(idx+1)
			}
		}
	}
	return result
}

// ── PartitionTable ─────────────────────────────────────────────────

// PartitionRow holds a single (grapheme, level) → (code, full) mapping.
type PartitionRow struct {
	Grapheme  string
	Level     string
	ClassCode string
	ClassFull string
}

// PartitionTable is a precomputed partition assignment for all graphemes and levels.
type PartitionTable struct {
	Rows        []PartitionRow
	ClassCounts map[string]int
	lookup      map[string]map[string]string // grapheme → level → code
}

// Partition returns the class code for a grapheme at a given level.
func (pt *PartitionTable) Partition(level, grapheme string) string {
	if pt.lookup == nil {
		return ""
	}
	if levels, ok := pt.lookup[grapheme]; ok {
		return levels[level]
	}
	normalized := NormalizeOutputGrapheme(NormalizeInputGrapheme(grapheme))
	if levels, ok := pt.lookup[normalized]; ok {
		return levels[level]
	}
	return ""
}

// Levels returns the available partition levels.
func (pt *PartitionTable) Levels() []string {
	return append([]string{}, partitionLevels...)
}

// ClassCount returns the number of distinct class codes at a given level.
func (pt *PartitionTable) ClassCount(level string) int {
	if pt.ClassCounts == nil {
		return 0
	}
	return pt.ClassCounts[level]
}

// ComputePartitions builds a PartitionTable for all graphemes in a system.
func ComputePartitions(sys System, geom *Geometry) *PartitionTable {
	config := systemConfig(sys)
	if config == nil {
		return &PartitionTable{}
	}

	isCategorical := sys.RepresentationKind() == "categorical"
	graphemes := sys.ListGraphemes()

	roleOf := make(map[string]string, len(graphemes))
	featsOf := make(map[string]map[string]bool, len(graphemes))
	for _, g := range graphemes {
		roleOf[g] = DeriveRole(g, sys).String()
		feats, ok := sys.GraphemeToFeatures(g)
		if ok {
			featsOf[g] = feats
		}
	}

	allLevels := append([]string{}, partitionLevels...)

	type pairKey struct{ grapheme, level string }
	fullPerPair := make(map[pairKey]string)
	tentativePerLevel := make(map[string]map[string]string)
	for _, level := range allLevels {
		tentativePerLevel[level] = map[string]string{}
	}

	for _, g := range graphemes {
		role := roleOf[g]
		feats := featsOf[g]
		if feats == nil {
			feats = map[string]bool{}
		}

		fullPerPair[pairKey{g, "prosody"}] = role
		tentativePerLevel["prosody"][role] = role

		for _, level := range allLevels {
			if level == "prosody" {
				continue
			}
			sig := signatureFor(
				feats, role, level,
				config.Partitions, isCategorical, config.FeatureCategories,
			)
			full := sig.classFull()
			fullPerPair[pairKey{g, level}] = full
			tentativePerLevel[level][full] = sig.tentativeCode()
		}
	}

	fullToCodePerLevel := make(map[string]map[string]string)
	classCounts := make(map[string]int)
	for _, level := range allLevels {
		fulls := make([]string, len(graphemes))
		for i, g := range graphemes {
			fulls[i] = fullPerPair[pairKey{g, level}]
		}
		fullToCodePerLevel[level] = assignCodes(fulls, tentativePerLevel[level])
		unique := map[string]bool{}
		for _, f := range fulls {
			unique[f] = true
		}
		classCounts[level] = len(unique)
	}

	lookup := make(map[string]map[string]string)
	var rows []PartitionRow
	for _, g := range graphemes {
		if lookup[g] == nil {
			lookup[g] = make(map[string]string, len(allLevels))
		}
		for _, level := range allLevels {
			full := fullPerPair[pairKey{g, level}]
			code := fullToCodePerLevel[level][full]
			rows = append(rows, PartitionRow{g, level, code, full})
			lookup[g][level] = code
		}
	}
	sort.Slice(rows, func(i, j int) bool {
		if rows[i].Grapheme != rows[j].Grapheme {
			return rows[i].Grapheme < rows[j].Grapheme
		}
		return rows[i].Level < rows[j].Level
	})

	return &PartitionTable{
		Rows:        rows,
		ClassCounts: classCounts,
		lookup:      lookup,
	}
}

func systemConfig(sys System) *ModelConfig {
	switch s := sys.(type) {
	case *CategoricalEngine:
		return s.config
	case *ValuedEngine:
		return s.config
	case *TrainedEngine:
		return s.config
	default:
		return nil
	}
}

// Known returns true if the grapheme is in the system's inventory.
func Known(sys System, grapheme string) bool {
	_, ok := sys.GraphemeToFeatures(grapheme)
	return ok
}
