package merkmal

import (
	"io/fs"
	"os"
	"testing"
	"testing/fstest"
)

// customModelFS returns an in-memory model directory for a minimal
// categorical model declaring the given default geometry.
func customModelFS(geometry string) fstest.MapFS {
	modelJSON := `{
		"schema_version": 1, "name": "mymodel", "version": "0.1.0",
		"type": "categorical", "description": "byo test model",
		"default_geometry": "` + geometry + `", "feature_extraction": "filtered"
	}`
	return fstest.MapFS{
		"mymodel/model.json":    {Data: []byte(modelJSON)},
		"mymodel/inventory.tsv": {Data: []byte("GRAPHEME\tNAME\nx\tvoiceless velar fricative consonant\n")},
		"mymodel/features.tsv":  {Data: []byte("VALUE\tFEATURE\nvelar\tplace\nfricative\tmanner\nvoiceless\tphonation\nconsonant\ttype\n")},
	}
}

func TestLayeredRegistryAddsCustomModel(t *testing.T) {
	bundled, err := NewDefaultRegistry()
	if err != nil {
		t.Fatalf("NewDefaultRegistry: %v", err)
	}
	builtinCount := len(bundled.List())

	// Layer the in-memory custom model on top of the bundled data.
	reg, err := NewLayeredRegistry(
		[]fs.FS{customModelFS("clements-hume"), os.DirFS("data/models")},
		[]fs.FS{os.DirFS("data/geometries")},
		[]fs.FS{os.DirFS("data/diacritics")},
	)
	if err != nil {
		t.Fatalf("NewLayeredRegistry: %v", err)
	}

	if len(reg.List()) != builtinCount+1 {
		t.Fatalf("expected %d systems, got %d", builtinCount+1, len(reg.List()))
	}
	if _, err := reg.Get("mymodel"); err != nil {
		t.Errorf("custom model not registered: %v", err)
	}
	if _, err := reg.Get("descriptive"); err != nil {
		t.Errorf("built-in model lost after layering: %v", err)
	}

	sys, _ := reg.Get("mymodel")
	if !sys.IsSegment("x") {
		t.Errorf("custom model failed to recognise its inventory grapheme")
	}
}

func TestPerModelGeometryIsHonored(t *testing.T) {
	// A model declaring an alternate (but present) geometry must load.
	reg, err := NewLayeredRegistry(
		[]fs.FS{customModelFS("deep-clements-hume")},
		[]fs.FS{os.DirFS("data/geometries")},
		[]fs.FS{os.DirFS("data/diacritics")},
	)
	if err != nil {
		t.Fatalf("NewLayeredRegistry: %v", err)
	}
	if _, err := reg.Get("mymodel"); err != nil {
		t.Fatalf("model with alternate geometry failed to load: %v", err)
	}
}

func TestCustomDiacriticVocabulary(t *testing.T) {
	// A model declaring its own diacritic set produces custom feature names.
	modelJSON := `{
		"schema_version": 1, "name": "diamodel", "version": "0.1.0",
		"type": "categorical", "description": "custom diacritics",
		"default_geometry": "clements-hume", "feature_extraction": "filtered",
		"diacritics": "myipa"
	}`
	models := fstest.MapFS{
		"diamodel/model.json":    {Data: []byte(modelJSON)},
		"diamodel/inventory.tsv": {Data: []byte("GRAPHEME\tNAME\nt\tvoiceless alveolar stop consonant\n")},
		"diamodel/features.tsv":  {Data: []byte("VALUE\tFEATURE\nalveolar\tplace\nstop\tmanner\nvoiceless\tphonation\nconsonant\ttype\n")},
	}
	// myipa maps ʰ (U+02B0) to "ASP" instead of "aspirated".
	diac := fstest.MapFS{
		"myipa.json": {Data: []byte(`{
			"name": "myipa",
			"suffix": {"02B0": "ASP"},
			"tone_levels": {"onset": {}, "mid": {}, "offset": {}}
		}`)},
	}
	reg, err := NewLayeredRegistry(
		[]fs.FS{models},
		[]fs.FS{os.DirFS("data/geometries")},
		[]fs.FS{diac, os.DirFS("data/diacritics")},
	)
	if err != nil {
		t.Fatalf("NewLayeredRegistry: %v", err)
	}
	sys, err := reg.Get("diamodel")
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	feats, ok := sys.GraphemeToFeatures("tʰ")
	if !ok {
		t.Fatal("tʰ not recognised")
	}
	if !feats["ASP"] {
		t.Errorf("expected custom feature ASP, got %v", feats)
	}
	if feats["aspirated"] {
		t.Errorf("did not expect default feature 'aspirated', got %v", feats)
	}
}

func TestLoadModelDir(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(dir+"/model.json", []byte(`{
		"schema_version": 1, "name": "dirmodel", "version": "0.1.0",
		"type": "categorical", "description": "dir test",
		"default_geometry": "clements-hume", "feature_extraction": "filtered"
	}`), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(dir+"/inventory.tsv",
		[]byte("GRAPHEME\tNAME\nx\tvoiceless velar fricative consonant\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(dir+"/features.tsv",
		[]byte("VALUE\tFEATURE\nvelar\tplace\nfricative\tmanner\nvoiceless\tphonation\nconsonant\ttype\n"), 0o644); err != nil {
		t.Fatal(err)
	}

	sys, err := LoadModelDir(dir, "data/geometries", "")
	if err != nil {
		t.Fatalf("LoadModelDir: %v", err)
	}
	if sys.Name() != "dirmodel" {
		t.Errorf("expected name dirmodel, got %s", sys.Name())
	}
	if !sys.IsSegment("x") {
		t.Errorf("loaded model failed to recognise its grapheme")
	}
}
