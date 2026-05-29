package merkmal

import (
	"io/fs"
	"os"
)

// layeredFS overlays several filesystems. Opening a path tries each
// layer in order and returns the first hit, so earlier layers take
// precedence. It lets callers stack their own data on top of merkmal's
// bundled geometries (and any other per-name lookups).
type overlayFS struct {
	layers []fs.FS
}

func (o overlayFS) Open(name string) (fs.File, error) {
	var lastErr error
	for _, l := range o.layers {
		f, err := l.Open(name)
		if err == nil {
			return f, nil
		}
		lastErr = err
	}
	if lastErr == nil {
		lastErr = fs.ErrNotExist
	}
	return nil, lastErr
}

// layeredFS returns a single fs.FS view over the given layers. With one
// layer it returns that layer directly to avoid indirection.
func layeredFS(layers []fs.FS) fs.FS {
	switch len(layers) {
	case 0:
		return overlayFS{}
	case 1:
		return layers[0]
	default:
		return overlayFS{layers: layers}
	}
}

// LoadModelDir loads a single model directly from a directory path on
// disk, using the model's declared default_geometry resolved from
// geometryDir (or "clements-hume" when unset) and its declared diacritic
// set resolved from diacriticDir. Pass diacriticDir == "" to use the
// built-in IPA/CLTS diacritic set. It is a convenience wrapper over the
// fs.FS loaders for the common case of bringing your own model from a
// directory.
func LoadModelDir(modelDir, geometryDir, diacriticDir string) (System, error) {
	modelFS := os.DirFS(modelDir)
	config, err := LoadModelConfig(modelFS)
	if err != nil {
		return nil, err
	}

	geomName := config.DefaultGeometry
	if geomName == "" {
		geomName = defaultGeometryName
	}
	geom, err := LoadGeometry(os.DirFS(geometryDir), geomName)
	if err != nil {
		return nil, err
	}

	if config.DiacriticsName != "" && diacriticDir != "" {
		if d, err := LoadDiacritics(os.DirFS(diacriticDir), config.DiacriticsName); err == nil {
			config.Diacritics = d
		}
	}

	return buildSystem(modelFS, config, geom)
}
