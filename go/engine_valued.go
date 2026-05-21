package merkmal

import (
	"encoding/json"
	"sort"
	"strings"
)

// ValuedEngine implements System for valued-feature models (phoible, pbase-*).
type ValuedEngine struct {
	config   *ModelConfig
	geometry *Geometry

	featureNames     []string
	table            map[string]map[string]FeatureState
	geometryMap      map[string]string
	dimensionWeights map[string]float64
}

// NewValuedEngine creates a valued engine from config and geometry.
func NewValuedEngine(config *ModelConfig, geom *Geometry) (*ValuedEngine, error) {
	e := &ValuedEngine{
		config:   config,
		geometry: geom,
	}

	e.featureNames = make([]string, len(config.InventoryHeader)-1)
	copy(e.featureNames, config.InventoryHeader[1:])

	var rawModel struct {
		GeometryMap map[string]string `json:"geometry_map"`
	}
	if err := json.Unmarshal(config.RawJSON, &rawModel); err != nil {
		return nil, err
	}
	e.geometryMap = rawModel.GeometryMap
	if e.geometryMap == nil {
		e.geometryMap = map[string]string{}
	}

	e.buildTable()
	e.buildDimensionWeights()
	return e, nil
}

func (e *ValuedEngine) buildTable() {
	e.table = make(map[string]map[string]FeatureState)
	for _, row := range e.config.InventoryRows {
		if len(row) == 0 {
			continue
		}
		grapheme := NormalizeInputGrapheme(row[0])
		values := make(map[string]FeatureState, len(e.featureNames))
		for i, feat := range e.featureNames {
			rawVal := "."
			if i+1 < len(row) {
				rawVal = strings.TrimSpace(strings.Trim(row[i+1], "\""))
			}
			values[feat] = parseFeatureState(rawVal)
		}
		existing, ok := e.table[grapheme]
		if !ok {
			e.table[grapheme] = values
		} else {
			for key := range existing {
				if existing[key] != values[key] {
					existing[key] = StateDot
				}
			}
		}
	}
}

func parseFeatureState(s string) FeatureState {
	switch s {
	case "+":
		return StatePositive
	case "-":
		return StateNegative
	case "n":
		return StateN
	case ".":
		return StateDot
	case "o":
		return StateO
	case "x":
		return StateX
	default:
		return StateDot
	}
}

func (e *ValuedEngine) buildDimensionWeights() {
	e.dimensionWeights = make(map[string]float64, len(e.geometryMap))
	for featName, nodeName := range e.geometryMap {
		depth := e.geometry.NodeDepth(nodeName)
		e.dimensionWeights[featName] = 1.0 / float64(depth)
	}
}

func quantizeStates(values map[string]FeatureState) map[string]float64 {
	result := make(map[string]float64)
	for name, state := range values {
		switch state {
		case StatePositive:
			result[name] = 1.0
		case StateNegative:
			result[name] = -1.0
		case StateDot:
			// omit — treated as not applicable
		default:
			result[name] = 0.0
		}
	}
	return result
}

// ── System interface ────────────────────────────────────────────────

func (e *ValuedEngine) Name() string              { return e.config.Name }
func (e *ValuedEngine) RepresentationKind() string { return "valued" }

func (e *ValuedEngine) ListGraphemes() []string {
	result := make([]string, 0, len(e.table))
	for g := range e.table {
		result = append(result, g)
	}
	sort.Strings(result)
	return result
}

func (e *ValuedEngine) GraphemeToFeatures(grapheme string) (map[string]bool, bool) {
	normalized := NormalizeInputGrapheme(grapheme)
	values, ok := e.table[normalized]
	if !ok {
		for _, candidate := range NormalizeSequences(normalized) {
			values, ok = e.table[candidate]
			if ok {
				break
			}
		}
	}
	if !ok {
		return nil, false
	}
	result := make(map[string]bool, len(values))
	for name, state := range values {
		result[name+"="+string(state)] = true
	}
	return result, true
}

func (e *ValuedEngine) FeatureDistance(a, b string) float64 {
	if a == b {
		return 0.0
	}
	return 1.0
}

func (e *ValuedEngine) SegmentDistance(a, b string, opts ...DistanceOption) float64 {
	normalizedA := NormalizeInputGrapheme(a)
	normalizedB := NormalizeInputGrapheme(b)
	valsA, okA := e.table[normalizedA]
	if !okA {
		for _, c := range NormalizeSequences(normalizedA) {
			valsA, okA = e.table[c]
			if okA {
				break
			}
		}
	}
	valsB, okB := e.table[normalizedB]
	if !okB {
		for _, c := range NormalizeSequences(normalizedB) {
			valsB, okB = e.table[c]
			if okB {
				break
			}
		}
	}
	if !okA || !okB {
		return 1.0
	}
	qA := quantizeStates(valsA)
	qB := quantizeStates(valsB)
	cfg := applyOpts(opts)
	resolved := e.geometry.resolveWeights(cfg)
	return ValuedGeometryDistance(e.geometry.Tree, qA, qB, e.geometryMap, e.dimensionWeights, resolved)
}

func (e *ValuedEngine) SoundDistance(featsA, featsB map[string]bool, opts ...DistanceOption) float64 {
	return 0.0
}

func (e *ValuedEngine) IsClass(grapheme string) bool {
	return false
}

func (e *ValuedEngine) ClassFeatures(grapheme string) (map[string]bool, bool) {
	return nil, false
}
