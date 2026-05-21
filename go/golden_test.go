package merkmal

import (
	"encoding/csv"
	"math"
	"os"
	"sort"
	"strconv"
	"strings"
	"testing"
)

const goldenDir = "../tests/golden"
const tolerance = 1e-8

func readGoldenTSV(t *testing.T, filename string) []map[string]string {
	t.Helper()
	path := goldenDir + "/" + filename
	f, err := os.Open(path)
	if err != nil {
		t.Fatalf("opening %s: %v", path, err)
	}
	defer f.Close()

	r := csv.NewReader(f)
	r.Comma = '\t'
	r.LazyQuotes = true
	records, err := r.ReadAll()
	if err != nil {
		t.Fatalf("reading %s: %v", path, err)
	}
	if len(records) < 2 {
		t.Fatalf("%s: expected header + rows", path)
	}
	header := records[0]
	var result []map[string]string
	for _, row := range records[1:] {
		m := make(map[string]string, len(header))
		for i, h := range header {
			if i < len(row) {
				m[h] = row[i]
			}
		}
		result = append(result, m)
	}
	return result
}

func loadTestGeometry(t *testing.T) *Geometry {
	t.Helper()
	geomFS := os.DirFS("../geometries")
	geom, err := LoadGeometry(geomFS, "clements-hume")
	if err != nil {
		t.Fatalf("loading geometry: %v", err)
	}
	return geom
}

func loadTestModel(t *testing.T, name string, geom *Geometry) System {
	t.Helper()
	modelFS := os.DirFS("../models/" + name)
	sys, err := LoadModel(modelFS, geom)
	if err != nil {
		t.Fatalf("loading model %s: %v", name, err)
	}
	return sys
}

// ── Geometry golden tests ───────────────────────────────────────────

func TestGeometryFeatureDistances(t *testing.T) {
	geom := loadTestGeometry(t)
	rows := readGoldenTSV(t, "geometry_distances.tsv")
	for _, row := range rows {
		expected, _ := strconv.Atoi(row["DISTANCE"])
		actual := geom.FeatureDistance(row["FEATURE_A"], row["FEATURE_B"])
		if actual != expected {
			t.Errorf("%s↔%s: expected %d, got %d",
				row["FEATURE_A"], row["FEATURE_B"], expected, actual)
		}
	}
}

func TestGeometrySoundDistances(t *testing.T) {
	geom := loadTestGeometry(t)
	sets := map[string]map[string]bool{
		"p-feats": {"consonant": true, "voiceless": true, "bilabial": true, "stop": true},
		"b-feats": {"consonant": true, "voiced": true, "bilabial": true, "stop": true},
		"t-feats": {"consonant": true, "voiceless": true, "alveolar": true, "stop": true},
		"k-feats": {"consonant": true, "voiceless": true, "velar": true, "stop": true},
		"s-feats": {"consonant": true, "voiceless": true, "alveolar": true, "fricative": true},
		"a-feats": {"vowel": true, "open": true, "front": true, "unrounded": true},
		"i-feats": {"vowel": true, "close": true, "front": true, "unrounded": true},
		"u-feats": {"vowel": true, "close": true, "back": true, "rounded": true},
	}
	rows := readGoldenTSV(t, "geometry_sound_distances.tsv")
	for _, row := range rows {
		expected, _ := strconv.ParseFloat(row["DISTANCE"], 64)
		actual := geom.SoundDistance(sets[row["SET_A"]], sets[row["SET_B"]])
		if math.Abs(actual-expected) > tolerance {
			t.Errorf("%s↔%s: expected %v, got %v",
				row["SET_A"], row["SET_B"], expected, actual)
		}
	}
}

func TestGeometryWeightedDistances(t *testing.T) {
	geom := loadTestGeometry(t)
	sets := map[string]map[string]bool{
		"p": {"consonant": true, "voiceless": true, "bilabial": true, "stop": true},
		"b": {"consonant": true, "voiced": true, "bilabial": true, "stop": true},
		"a": {"vowel": true, "open": true, "front": true, "unrounded": true},
	}
	rows := readGoldenTSV(t, "geometry_weighted_distances.tsv")
	for _, row := range rows {
		expected, _ := strconv.ParseFloat(row["DISTANCE"], 64)
		var opts []DistanceOption
		if row["PRESET"] != "None" {
			opts = append(opts, WithPreset(row["PRESET"]))
		}
		actual := geom.SoundDistance(sets[row["SET_A"]], sets[row["SET_B"]], opts...)
		if math.Abs(actual-expected) > tolerance {
			t.Errorf("preset=%s %s↔%s: expected %v, got %v",
				row["PRESET"], row["SET_A"], row["SET_B"], expected, actual)
		}
	}
}

// ── Categorical model golden tests ──────────────────────────────────

var categoricalModels = []string{"descriptive", "broad", "distinctive"}

func TestCategoricalFeatures(t *testing.T) {
	geom := loadTestGeometry(t)
	for _, modelName := range categoricalModels {
		t.Run(modelName, func(t *testing.T) {
			sys := loadTestModel(t, modelName, geom)
			rows := readGoldenTSV(t, modelName+"_features.tsv")
			for _, row := range rows {
				grapheme := row["GRAPHEME"]
				expectedFeats := strings.Split(row["FEATURES"], "|")
				expected := make(map[string]bool, len(expectedFeats))
				for _, f := range expectedFeats {
					expected[f] = true
				}
				actual, ok := sys.GraphemeToFeatures(grapheme)
				if !ok {
					t.Errorf("%s: %q not found", modelName, grapheme)
					continue
				}
				if !mapsEqual(actual, expected) {
					t.Errorf("%s %q: expected %v, got %v",
						modelName, grapheme,
						sortedKeys(expected), sortedKeys(actual))
				}
			}
		})
	}
}

func TestCategoricalDistances(t *testing.T) {
	geom := loadTestGeometry(t)
	for _, modelName := range categoricalModels {
		t.Run(modelName, func(t *testing.T) {
			sys := loadTestModel(t, modelName, geom)
			rows := readGoldenTSV(t, modelName+"_distances.tsv")
			for _, row := range rows {
				a, b := row["GRAPHEME_A"], row["GRAPHEME_B"]
				expected, _ := strconv.ParseFloat(row["DISTANCE"], 64)
				actual := sys.SegmentDistance(a, b)
				if math.Abs(actual-expected) > tolerance {
					t.Errorf("%s %q↔%q: expected %v, got %v",
						modelName, a, b, expected, actual)
				}
			}
		})
	}
}

// ── Valued model golden tests ────────────────────────────────────────

var valuedModels = []string{"phoible", "pbase-hc", "pbase-jfh", "pbase-spe", "pbase-uftc"}

func TestValuedFeatures(t *testing.T) {
	geom := loadTestGeometry(t)
	for _, modelName := range valuedModels {
		t.Run(modelName, func(t *testing.T) {
			sys := loadTestModel(t, modelName, geom)
			rows := readGoldenTSV(t, modelName+"_features.tsv")
			for _, row := range rows {
				grapheme := row["GRAPHEME"]
				expectedFeats := strings.Split(row["FEATURES"], "|")
				expected := make(map[string]bool, len(expectedFeats))
				for _, f := range expectedFeats {
					expected[f] = true
				}
				actual, ok := sys.GraphemeToFeatures(grapheme)
				if !ok {
					t.Errorf("%s: %q not found", modelName, grapheme)
					continue
				}
				if !mapsEqual(actual, expected) {
					t.Errorf("%s %q:\n  expected %v\n  got      %v",
						modelName, grapheme,
						sortedKeys(expected), sortedKeys(actual))
				}
			}
		})
	}
}

func TestValuedDistances(t *testing.T) {
	geom := loadTestGeometry(t)
	for _, modelName := range valuedModels {
		t.Run(modelName, func(t *testing.T) {
			sys := loadTestModel(t, modelName, geom)
			rows := readGoldenTSV(t, modelName+"_distances.tsv")
			for _, row := range rows {
				a, b := row["GRAPHEME_A"], row["GRAPHEME_B"]
				expected, _ := strconv.ParseFloat(row["DISTANCE"], 64)
				actual := sys.SegmentDistance(a, b)
				if math.Abs(actual-expected) > tolerance {
					t.Errorf("%s %q↔%q: expected %v, got %v",
						modelName, a, b, expected, actual)
				}
			}
		})
	}
}

// ── Trained model golden tests ──────────────────────────────────────

func TestTrainedFeatures(t *testing.T) {
	geom := loadTestGeometry(t)
	sys := loadTestModel(t, "classfeat", geom)
	rows := readGoldenTSV(t, "classfeat_features.tsv")
	for _, row := range rows {
		grapheme := row["GRAPHEME"]
		expectedFeats := strings.Split(row["FEATURES"], "|")
		expected := make(map[string]bool, len(expectedFeats))
		for _, f := range expectedFeats {
			expected[f] = true
		}
		actual, ok := sys.GraphemeToFeatures(grapheme)
		if !ok {
			t.Errorf("classfeat: %q not found", grapheme)
			continue
		}
		if !mapsEqual(actual, expected) {
			t.Errorf("classfeat %q:\n  expected %v\n  got      %v",
				grapheme, sortedKeys(expected), sortedKeys(actual))
		}
	}
}

func TestTrainedDistances(t *testing.T) {
	geom := loadTestGeometry(t)
	sys := loadTestModel(t, "classfeat", geom)
	rows := readGoldenTSV(t, "classfeat_distances.tsv")
	for _, row := range rows {
		a, b := row["GRAPHEME_A"], row["GRAPHEME_B"]
		expected, _ := strconv.ParseFloat(row["DISTANCE"], 64)
		actual := sys.SegmentDistance(a, b)
		if math.Abs(actual-expected) > tolerance {
			t.Errorf("classfeat %q↔%q: expected %v, got %v",
				a, b, expected, actual)
		}
	}
}

// ── Partition golden tests ──────────────────────────────────────────

func TestPartitionsCategorical(t *testing.T) {
	geom := loadTestGeometry(t)
	sys := loadTestModel(t, "descriptive", geom)
	pt := ComputePartitions(sys, geom)
	rows := readGoldenTSV(t, "descriptive_partitions.tsv")
	for _, row := range rows {
		grapheme := row["GRAPHEME"]
		level := row["LEVEL"]
		expectedCode := row["CLASS_CODE"]
		actual := pt.Partition(level, grapheme)
		if actual != expectedCode {
			t.Errorf("descriptive partition %q@%s: expected %q, got %q",
				grapheme, level, expectedCode, actual)
		}
	}
}

func TestPartitionsValued(t *testing.T) {
	geom := loadTestGeometry(t)
	sys := loadTestModel(t, "phoible", geom)
	pt := ComputePartitions(sys, geom)
	rows := readGoldenTSV(t, "phoible_partitions.tsv")
	for _, row := range rows {
		grapheme := row["GRAPHEME"]
		level := row["LEVEL"]
		expectedCode := row["CLASS_CODE"]
		actual := pt.Partition(level, grapheme)
		if actual != expectedCode {
			t.Errorf("phoible partition %q@%s: expected %q, got %q",
				grapheme, level, expectedCode, actual)
		}
	}
}

// ── Registry test ──────────────────────────────────────────────────

func TestRegistry(t *testing.T) {
	modelsFS := os.DirFS("../models")
	geomFS := os.DirFS("../geometries")
	reg, err := NewRegistry(modelsFS, geomFS)
	if err != nil {
		t.Fatalf("creating registry: %v", err)
	}
	names := reg.List()
	if len(names) < 9 {
		t.Errorf("expected at least 9 models, got %d: %v", len(names), names)
	}
	def := reg.Default()
	if def == nil {
		t.Fatal("default system is nil")
	}
	if def.Name() != "descriptive" {
		t.Errorf("default name: expected descriptive, got %s", def.Name())
	}
	for _, name := range names {
		sys, err := reg.Get(name)
		if err != nil {
			t.Errorf("Get(%q): %v", name, err)
			continue
		}
		if sys.Name() != name {
			t.Errorf("Get(%q).Name() = %q", name, sys.Name())
		}
	}
	_, err = reg.Get("nonexistent")
	if err == nil {
		t.Error("expected error for nonexistent system")
	}
}

// ── Role derivation test ───────────────────────────────────────────

func TestDeriveRole(t *testing.T) {
	geom := loadTestGeometry(t)
	sys := loadTestModel(t, "descriptive", geom)
	cases := map[string]Role{
		"p": RoleC, "b": RoleC, "t": RoleC, "k": RoleC, "s": RoleC,
		"a": RoleV, "i": RoleV, "u": RoleV, "e": RoleV, "o": RoleV,
		"m": RoleR, "n": RoleR, "l": RoleR, "r": RoleR,
		"j": RoleG, "w": RoleG,
	}
	for grapheme, expected := range cases {
		actual := DeriveRole(grapheme, sys)
		if actual != expected {
			t.Errorf("DeriveRole(%q, descriptive): expected %v, got %v",
				grapheme, expected, actual)
		}
	}
}

func TestKnown(t *testing.T) {
	geom := loadTestGeometry(t)
	sys := loadTestModel(t, "descriptive", geom)
	if !Known(sys, "p") {
		t.Error("expected 'p' to be known")
	}
	if Known(sys, "zzz_invalid") {
		t.Error("expected 'zzz_invalid' to be unknown")
	}
}

func sortedKeys(m map[string]bool) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}
