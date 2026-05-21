package merkmal

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io/fs"
	"strings"
)

// ModelConfig holds parsed model.json plus loaded data files.
type ModelConfig struct {
	Name              string
	Version           string
	ModelType         string
	Description       string
	DefaultGeometry   string
	FeatureExtraction string
	ScalarDimensions  []ScalarDimension

	InventoryHeader []string
	InventoryRows   [][]string

	FeatureCategories map[string]string
	ClassesData       map[string]ClassDef

	Partitions map[string]map[string][]string

	RawJSON json.RawMessage
}

// ScalarDimension defines a continuous dimension overlay for categorical features.
type ScalarDimension struct {
	Name         string   `json:"name"`
	Positive     []string `json:"positive"`
	Negative     []string `json:"negative"`
	GeometryNode string   `json:"geometry_node"`
}

// ClassDef holds a sound class definition from classes.tsv.
type ClassDef struct {
	Description string
	Features    string
	Graphemes   []string
}

type rawModelJSON struct {
	Name              string                         `json:"name"`
	Version           string                         `json:"version"`
	Type              string                         `json:"type"`
	Description       string                         `json:"description"`
	DefaultGeometry   string                         `json:"default_geometry"`
	FeatureExtraction string                         `json:"feature_extraction"`
	ScalarDimensions  []ScalarDimension              `json:"scalar_dimensions"`
	Partitions        map[string]map[string][]string `json:"partitions"`
}

func readTSV(fsys fs.FS, path string) ([]string, [][]string, error) {
	f, err := fsys.Open(path)
	if err != nil {
		return nil, nil, err
	}
	defer f.Close()

	r := csv.NewReader(f)
	r.Comma = '\t'
	r.LazyQuotes = true
	r.FieldsPerRecord = -1

	records, err := r.ReadAll()
	if err != nil {
		return nil, nil, err
	}
	if len(records) == 0 {
		return nil, nil, fmt.Errorf("empty TSV: %s", path)
	}
	return records[0], records[1:], nil
}

// LoadModelConfig reads model.json and associated data files from an fs.FS.
func LoadModelConfig(fsys fs.FS) (*ModelConfig, error) {
	data, err := fs.ReadFile(fsys, "model.json")
	if err != nil {
		return nil, fmt.Errorf("reading model.json: %w", err)
	}

	var raw rawModelJSON
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("parsing model.json: %w", err)
	}

	invHeader, invRows, err := readTSV(fsys, "inventory.tsv")
	if err != nil {
		return nil, fmt.Errorf("reading inventory.tsv: %w", err)
	}

	featureCategories := map[string]string{}
	if _, featRows, err := readTSV(fsys, "features.tsv"); err == nil {
		for _, row := range featRows {
			if len(row) >= 2 {
				featureCategories[row[0]] = row[1]
			}
		}
	}

	classesData := map[string]ClassDef{}
	if _, clsRows, err := readTSV(fsys, "classes.tsv"); err == nil {
		for _, row := range clsRows {
			if len(row) >= 4 {
				var graphemes []string
				if row[3] != "" {
					graphemes = strings.Split(row[3], "|")
				}
				classesData[row[0]] = ClassDef{
					Description: row[1],
					Features:    row[2],
					Graphemes:   graphemes,
				}
			}
		}
	}

	if raw.DefaultGeometry == "" {
		raw.DefaultGeometry = "clements-hume"
	}

	return &ModelConfig{
		Name:              raw.Name,
		Version:           raw.Version,
		ModelType:         raw.Type,
		Description:       raw.Description,
		DefaultGeometry:   raw.DefaultGeometry,
		FeatureExtraction: raw.FeatureExtraction,
		ScalarDimensions:  raw.ScalarDimensions,
		InventoryHeader:   invHeader,
		InventoryRows:     invRows,
		FeatureCategories: featureCategories,
		ClassesData:       classesData,
		Partitions:        raw.Partitions,
		RawJSON:           data,
	}, nil
}

// LoadModel loads a model from an fs.FS and returns a System.
func LoadModel(fsys fs.FS, geom *Geometry) (System, error) {
	config, err := LoadModelConfig(fsys)
	if err != nil {
		return nil, err
	}

	switch config.ModelType {
	case "categorical":
		return NewCategoricalEngine(config, geom), nil
	case "valued":
		return NewValuedEngine(config, geom)
	case "trained":
		return NewTrainedEngine(fsys, config, geom)
	default:
		return nil, fmt.Errorf("unsupported model type: %s", config.ModelType)
	}
}
