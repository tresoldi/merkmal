package merkmal

import (
	"embed"
	"fmt"
	"io/fs"
)

//go:embed data/models data/geometries data/diacritics
var defaultData embed.FS

// NewDefaultRegistry creates a registry backed by merkmal's bundled models,
// geometries, and diacritic sets. Use NewRegistry / NewLayeredRegistry when
// callers need custom data.
func NewDefaultRegistry() (*Registry, error) {
	modelsFS, err := fs.Sub(defaultData, "data/models")
	if err != nil {
		return nil, fmt.Errorf("opening bundled models: %w", err)
	}
	geometriesFS, err := fs.Sub(defaultData, "data/geometries")
	if err != nil {
		return nil, fmt.Errorf("opening bundled geometries: %w", err)
	}
	diacriticsFS, err := fs.Sub(defaultData, "data/diacritics")
	if err != nil {
		return nil, fmt.Errorf("opening bundled diacritics: %w", err)
	}
	return NewLayeredRegistry(
		[]fs.FS{modelsFS},
		[]fs.FS{geometriesFS},
		[]fs.FS{diacriticsFS},
	)
}
