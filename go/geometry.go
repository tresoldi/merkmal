package merkmal

import (
	"encoding/json"
	"fmt"
	"io/fs"
	"math"
	"sort"
)

// FeatureNode is a leaf in the geometry tree: a binary phonological feature.
type FeatureNode struct {
	Name     string
	Positive string
	Negative string
}

func (f *FeatureNode) isPrivative() bool { return f.Negative == "" }

// GeometryNode is an internal node grouping features or sub-nodes.
type GeometryNode struct {
	Name     string
	Children []any // *GeometryNode or *FeatureNode
}

func (n *GeometryNode) findFeature(value string) *FeatureNode {
	for _, child := range n.Children {
		switch c := child.(type) {
		case *FeatureNode:
			if c.Name == value || c.Positive == value || c.Negative == value {
				return c
			}
		case *GeometryNode:
			if r := c.findFeature(value); r != nil {
				return r
			}
		}
	}
	return nil
}

func (n *GeometryNode) pathTo(value string) []string {
	for _, child := range n.Children {
		switch c := child.(type) {
		case *FeatureNode:
			if c.Name == value || c.Positive == value || c.Negative == value {
				return []string{n.Name, c.Name, value}
			}
		case *GeometryNode:
			if sub := c.pathTo(value); sub != nil {
				return append([]string{n.Name}, sub...)
			}
		}
	}
	return nil
}

// FeatureDistance returns the tree-path distance between two feature values.
func (n *GeometryNode) FeatureDistance(a, b string) int {
	if a == b {
		return 0
	}
	pathA := n.pathTo(a)
	pathB := n.pathTo(b)
	if pathA == nil || pathB == nil {
		return 999
	}
	common := 0
	for i := 0; i < len(pathA) && i < len(pathB); i++ {
		if pathA[i] == pathB[i] {
			common++
		} else {
			break
		}
	}
	return (len(pathA) - common) + (len(pathB) - common)
}

type leafInfo struct {
	leaf       *FeatureNode
	depth      float64
	parentName string
}

func iterLeaves(node *GeometryNode, depth int) []leafInfo {
	var result []leafInfo
	for _, child := range node.Children {
		switch c := child.(type) {
		case *FeatureNode:
			result = append(result, leafInfo{c, float64(depth), node.Name})
		case *GeometryNode:
			result = append(result, iterLeaves(c, depth+1)...)
		}
	}
	return result
}

func nodeDepth(root *GeometryNode, name string, depth int) int {
	if root.Name == name {
		return depth
	}
	for _, child := range root.Children {
		if g, ok := child.(*GeometryNode); ok {
			if d := nodeDepth(g, name, depth+1); d > 0 {
				return d
			}
		}
	}
	return 0
}

func buildAncestorMap(node *GeometryNode, ancestors []string) map[string][]string {
	result := map[string][]string{node.Name: append([]string{}, ancestors...)}
	for _, child := range node.Children {
		if g, ok := child.(*GeometryNode); ok {
			sub := buildAncestorMap(g, append(ancestors, node.Name))
			for k, v := range sub {
				result[k] = v
			}
		}
	}
	return result
}

func resolveNodeWeight(name string, weights map[string]float64, ancestors map[string][]string) float64 {
	w := 1.0
	if v, ok := weights[name]; ok {
		w = v
	}
	for _, anc := range ancestors[name] {
		if v, ok := weights[anc]; ok {
			w *= v
		}
	}
	return w
}

var flatSentinel = map[string]float64{"__flat__": 1.0}

func isFlat(w map[string]float64) bool {
	if len(w) != 1 {
		return false
	}
	_, ok := w["__flat__"]
	return ok
}

// SoundDistance computes geometry-weighted distance between two categorical
// feature sets, with optional node weighting.
func (n *GeometryNode) SoundDistance(featsA, featsB map[string]bool, ftn map[string]string, resolved map[string]float64) float64 {
	if mapsEqual(featsA, featsB) {
		return 0.0
	}

	flat := resolved != nil && isFlat(resolved)
	var ancestorMap map[string][]string
	if resolved != nil && !flat {
		ancestorMap = buildAncestorMap(n, nil)
	}

	totalWeight := 0.0
	totalDiff := 0.0

	leaves := iterLeaves(n, 1)
	for _, li := range leaves {
		var weight float64
		if flat {
			weight = 1.0
		} else if resolved != nil {
			nw := resolveNodeWeight(li.parentName, resolved, ancestorMap)
			weight = nw / li.depth
		} else {
			weight = 1.0 / li.depth
		}
		totalWeight += weight

		aPos := li.leaf.Positive != "" && featsA[li.leaf.Positive]
		aNeg := li.leaf.Negative != "" && featsA[li.leaf.Negative]
		bPos := li.leaf.Positive != "" && featsB[li.leaf.Positive]
		bNeg := li.leaf.Negative != "" && featsB[li.leaf.Negative]

		if !aPos && !aNeg && !bPos && !bNeg {
			totalWeight -= weight
			continue
		}

		aVal := 0.0
		if aPos {
			aVal = 1.0
		} else if aNeg {
			aVal = -1.0
		}
		bVal := 0.0
		if bPos {
			bVal = 1.0
		} else if bNeg {
			bVal = -1.0
		}
		divisor := 2.0
		if li.leaf.isPrivative() {
			divisor = 1.0
		}
		totalDiff += weight * math.Abs(aVal-bVal) / divisor
	}

	// Node-group features (non-leaf features mapped via feature_to_node).
	leafFeats := map[string]bool{}
	for _, li := range leaves {
		if li.leaf.Positive != "" {
			leafFeats[li.leaf.Positive] = true
		}
		if li.leaf.Negative != "" {
			leafFeats[li.leaf.Negative] = true
		}
	}

	type setPair struct{ a, b map[string]bool }
	nodeGroups := map[string]*setPair{}
	allFeats := sortedUnion(featsA, featsB)
	for _, feat := range allFeats {
		if leafFeats[feat] {
			continue
		}
		nodeName, ok := ftn[feat]
		if !ok {
			continue
		}
		sp, exists := nodeGroups[nodeName]
		if !exists {
			sp = &setPair{map[string]bool{}, map[string]bool{}}
			nodeGroups[nodeName] = sp
		}
		if featsA[feat] {
			sp.a[feat] = true
		}
		if featsB[feat] {
			sp.b[feat] = true
		}
	}

	for nodeName, sp := range nodeGroups {
		var weight float64
		if flat {
			weight = 1.0
		} else {
			depth := nodeDepth(n, nodeName, 1)
			if depth == 0 {
				depth = 2
			}
			if resolved != nil {
				nw := resolveNodeWeight(nodeName, resolved, ancestorMap)
				weight = nw / float64(depth)
			} else {
				weight = 1.0 / float64(depth)
			}
		}
		totalWeight += weight
		if !mapsEqual(sp.a, sp.b) {
			totalDiff += weight
		}
	}

	if totalWeight > 0 {
		return totalDiff / totalWeight
	}
	return 0.0
}

func mapsEqual(a, b map[string]bool) bool {
	if len(a) != len(b) {
		return false
	}
	for k := range a {
		if !b[k] {
			return false
		}
	}
	return true
}

func sortedUnion(a, b map[string]bool) []string {
	m := map[string]bool{}
	for k := range a {
		m[k] = true
	}
	for k := range b {
		m[k] = true
	}
	result := make([]string, 0, len(m))
	for k := range m {
		result = append(result, k)
	}
	sort.Strings(result)
	return result
}

// Geometry wraps a loaded geometry tree with metadata.
type Geometry struct {
	Tree          *GeometryNode
	FeatureToNode map[string]string
	WeightPresets map[string]map[string]float64
	GeomName      string
}

// FeatureDistance returns the tree-path distance between two feature values.
func (g *Geometry) FeatureDistance(a, b string) int {
	return g.Tree.FeatureDistance(a, b)
}

// SoundDistance returns the geometry-weighted distance between two feature sets.
func (g *Geometry) SoundDistance(featsA, featsB map[string]bool, opts ...DistanceOption) float64 {
	cfg := applyOpts(opts)
	resolved := g.resolveWeights(cfg)
	return g.Tree.SoundDistance(featsA, featsB, g.FeatureToNode, resolved)
}

// NodeDepth returns the depth of a named node in the tree.
func (g *Geometry) NodeDepth(name string) int {
	d := nodeDepth(g.Tree, name, 1)
	if d == 0 {
		return 2
	}
	return d
}

func (g *Geometry) resolveWeights(cfg distanceConfig) map[string]float64 {
	if cfg.nodeWeights != nil {
		return cfg.nodeWeights
	}
	if cfg.presetName == "" {
		return nil
	}
	if w, ok := g.WeightPresets[cfg.presetName]; ok {
		return w
	}
	return resolveBuiltinPreset(cfg.presetName)
}

// ResolveNodeWeights resolves a preset name or returns the dict as-is.
func ResolveNodeWeights(g *Geometry, presetName string) (map[string]float64, error) {
	if presetName == "" {
		return nil, nil
	}
	if w, ok := g.WeightPresets[presetName]; ok {
		return w, nil
	}
	w := resolveBuiltinPreset(presetName)
	if w == nil {
		return nil, fmt.Errorf("unknown node_weights preset: %q", presetName)
	}
	return w, nil
}

func resolveBuiltinPreset(name string) map[string]float64 {
	switch name {
	case "ignore-tone":
		return map[string]float64{"Tonal": 0.0}
	case "ignore-prosodic":
		return map[string]float64{"Prosodic": 0.0}
	case "segmental":
		return map[string]float64{"Tonal": 0.0, "Prosodic": 0.0}
	case "tone-heavy":
		return map[string]float64{"Tonal": 2.0}
	case "tone-only":
		return map[string]float64{
			"Laryngeal": 0.0, "Manner": 0.0, "Place": 0.0,
			"TongueRoot": 0.0, "Prosodic": 0.0,
		}
	case "flat":
		return flatSentinel
	}
	return nil
}

// ValuedGeometryDistance computes geometry-weighted distance between two
// valued feature vectors (used by valued and trained engines).
func ValuedGeometryDistance(
	tree *GeometryNode,
	aValues, bValues map[string]float64,
	geometryMap map[string]string,
	dimensionWeights map[string]float64,
	resolved map[string]float64,
) float64 {
	if floatMapsEqual(aValues, bValues) {
		return 0.0
	}

	flat := resolved != nil && isFlat(resolved)
	var ancestorMap map[string][]string
	if resolved != nil && !flat {
		ancestorMap = buildAncestorMap(tree, nil)
	}

	totalWeight := 0.0
	totalDiff := 0.0

	allKeys := sortedFloatUnion(aValues, bValues)
	for _, key := range allKeys {
		valA, okA := aValues[key]
		valB, okB := bValues[key]
		if !okA || !okB {
			continue
		}
		if valA == 0.0 && valB == 0.0 {
			continue
		}
		nodeName, ok := geometryMap[key]
		if !ok {
			continue
		}

		var weight float64
		if flat {
			weight = 1.0
		} else {
			baseW := 0.5
			if w, exists := dimensionWeights[key]; exists {
				baseW = w
			}
			nw := 1.0
			if resolved != nil {
				nw = resolveNodeWeight(nodeName, resolved, ancestorMap)
			}
			weight = baseW * nw
		}
		totalWeight += weight
		totalDiff += weight * math.Abs(valA-valB) / 2.0
	}

	if totalWeight > 0 {
		return totalDiff / totalWeight
	}
	return 0.0
}

func floatMapsEqual(a, b map[string]float64) bool {
	if len(a) != len(b) {
		return false
	}
	for k, v := range a {
		if bv, ok := b[k]; !ok || v != bv {
			return false
		}
	}
	return true
}

func sortedFloatUnion(a, b map[string]float64) []string {
	m := make(map[string]bool, len(a)+len(b))
	for k := range a {
		m[k] = true
	}
	for k := range b {
		m[k] = true
	}
	result := make([]string, 0, len(m))
	for k := range m {
		result = append(result, k)
	}
	sort.Strings(result)
	return result
}

func walkAllNodeDepths(node any, depth int, result map[string]int) {
	switch n := node.(type) {
	case *GeometryNode:
		result[n.Name] = depth
		for _, child := range n.Children {
			walkAllNodeDepths(child, depth+1, result)
		}
	case *FeatureNode:
		result[n.Name] = depth
	}
}

// ── Loading from JSON ─────────────────────────────────────────────────

type jsonNode struct {
	Name     string     `json:"name"`
	Positive *string    `json:"positive,omitempty"`
	Negative *string    `json:"negative,omitempty"`
	Children []jsonNode `json:"children,omitempty"`
}

func nodeFromJSON(j jsonNode) any {
	if j.Positive != nil {
		neg := ""
		if j.Negative != nil {
			neg = *j.Negative
		}
		return &FeatureNode{Name: j.Name, Positive: *j.Positive, Negative: neg}
	}
	gn := &GeometryNode{Name: j.Name}
	for _, c := range j.Children {
		gn.Children = append(gn.Children, nodeFromJSON(c))
	}
	return gn
}

type jsonGeometry struct {
	Tree          jsonNode                       `json:"tree"`
	FeatureToNode map[string]string              `json:"feature_to_node"`
	WeightPresets map[string]json.RawMessage     `json:"weight_presets"`
}

// LoadGeometry reads a geometry JSON file from an fs.FS.
func LoadGeometry(fsys fs.FS, name string) (*Geometry, error) {
	path := name + ".json"
	data, err := fs.ReadFile(fsys, path)
	if err != nil {
		return nil, fmt.Errorf("geometry not found: %s (%w)", name, err)
	}

	var raw jsonGeometry
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("parsing geometry %s: %w", name, err)
	}

	tree, ok := nodeFromJSON(raw.Tree).(*GeometryNode)
	if !ok {
		return nil, fmt.Errorf("geometry %s: root is not a GeometryNode", name)
	}

	presets := map[string]map[string]float64{}
	for k, v := range raw.WeightPresets {
		var s string
		if json.Unmarshal(v, &s) == nil && s == "__flat__" {
			presets[k] = flatSentinel
			continue
		}
		var m map[string]float64
		if err := json.Unmarshal(v, &m); err == nil {
			presets[k] = m
		}
	}

	return &Geometry{
		Tree:          tree,
		FeatureToNode: raw.FeatureToNode,
		WeightPresets: presets,
		GeomName:      name,
	}, nil
}
