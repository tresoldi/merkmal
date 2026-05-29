package merkmal

import (
	"fmt"
	"io/fs"
	"sort"
	"sync"
)

// Registry provides named access to loaded feature systems.
type Registry struct {
	mu           sync.RWMutex
	systems      map[string]System
	defaultName  string
	geometriesFS fs.FS
	modelsFS     fs.FS
	diacriticsFS fs.FS
	defaultGeom  *Geometry
	geomCache    map[string]*Geometry
	diacCache    map[string]*DiacriticTable
}

const defaultGeometryName = "clements-hume"

// NewRegistry creates a registry that discovers models from the given filesystems.
// modelsFS should contain model subdirectories; geometriesFS should contain geometry JSON files.
//
// Each model is loaded with the geometry it declares in its model.json
// (default_geometry), falling back to "clements-hume" when unset or
// unavailable. The built-in IPA/CLTS diacritic set is used; supply
// diacritic layers via NewLayeredRegistry for custom diacritic sets.
func NewRegistry(modelsFS, geometriesFS fs.FS) (*Registry, error) {
	return NewLayeredRegistry([]fs.FS{modelsFS}, []fs.FS{geometriesFS}, nil)
}

// NewLayeredRegistry discovers models across several model filesystems,
// resolving geometries and diacritic sets across their respective
// filesystem layers. Earlier layers take precedence: a model (geometry,
// diacritic set) found in an earlier filesystem shadows the same name in
// a later one. This lets callers drop their own data on top of merkmal's
// bundled set. diacriticLayers may be nil to use only the built-in set.
func NewLayeredRegistry(modelLayers, geometryLayers, diacriticLayers []fs.FS) (*Registry, error) {
	if len(modelLayers) == 0 {
		return nil, fmt.Errorf("no model layers provided")
	}

	r := &Registry{
		systems:      make(map[string]System),
		defaultName:  "descriptive",
		geometriesFS: layeredFS(geometryLayers),
		modelsFS:     layeredFS(modelLayers),
		diacriticsFS: layeredFS(diacriticLayers),
		geomCache:    make(map[string]*Geometry),
		diacCache:    make(map[string]*DiacriticTable),
	}

	geom, err := r.geometry(defaultGeometryName)
	if err != nil {
		return nil, fmt.Errorf("loading default geometry: %w", err)
	}
	r.defaultGeom = geom

	for _, modelsFS := range modelLayers {
		entries, err := fs.ReadDir(modelsFS, ".")
		if err != nil {
			continue
		}
		for _, entry := range entries {
			if !entry.IsDir() {
				continue
			}
			name := entry.Name()
			if _, seen := r.systems[name]; seen {
				continue // earlier layer wins
			}
			modelFS, err := fs.Sub(modelsFS, name)
			if err != nil {
				continue
			}
			sys, err := r.loadModelWithGeometry(modelFS)
			if err != nil {
				continue
			}
			r.systems[name] = sys
		}
	}

	return r, nil
}

// geometry returns the named geometry, loading and caching it on first use.
func (r *Registry) geometry(name string) (*Geometry, error) {
	if name == "" {
		name = defaultGeometryName
	}
	if g, ok := r.geomCache[name]; ok {
		return g, nil
	}
	g, err := LoadGeometry(r.geometriesFS, name)
	if err != nil {
		return nil, err
	}
	r.geomCache[name] = g
	return g, nil
}

// diacritics returns the named diacritic table, loading and caching it on
// first use. An empty name (or an unavailable built-in name) yields the
// built-in default.
func (r *Registry) diacritics(name string) *DiacriticTable {
	if name == "" {
		return DefaultDiacritics
	}
	if d, ok := r.diacCache[name]; ok {
		return d
	}
	d, err := LoadDiacritics(r.diacriticsFS, name)
	if err != nil {
		if name == defaultDiacriticsName {
			return DefaultDiacritics
		}
		// Unknown custom set: fall back to the default rather than failing
		// the whole registry; the model still loads with built-in diacritics.
		return DefaultDiacritics
	}
	r.diacCache[name] = d
	return d
}

// loadModelWithGeometry loads a model using its declared default_geometry
// and diacritic set.
func (r *Registry) loadModelWithGeometry(modelFS fs.FS) (System, error) {
	config, err := LoadModelConfig(modelFS)
	if err != nil {
		return nil, err
	}
	geom, err := r.geometry(config.DefaultGeometry)
	if err != nil {
		// Fall back to the registry default geometry.
		geom = r.defaultGeom
	}
	config.Diacritics = r.diacritics(config.DiacriticsName)
	return buildSystem(modelFS, config, geom)
}

// Get returns the named system, or the default if name is empty.
func (r *Registry) Get(name string) (System, error) {
	if name == "" {
		name = r.defaultName
	}
	r.mu.RLock()
	sys, ok := r.systems[name]
	r.mu.RUnlock()
	if !ok {
		return nil, fmt.Errorf("unknown feature system: %q (available: %v)", name, r.List())
	}
	return sys, nil
}

// List returns sorted names of all registered systems.
func (r *Registry) List() []string {
	r.mu.RLock()
	defer r.mu.RUnlock()
	names := make([]string, 0, len(r.systems))
	for name := range r.systems {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

// Default returns the default system.
func (r *Registry) Default() System {
	r.mu.RLock()
	sys := r.systems[r.defaultName]
	r.mu.RUnlock()
	return sys
}

// SetDefault changes the default system name.
func (r *Registry) SetDefault(name string) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	if _, ok := r.systems[name]; !ok {
		return fmt.Errorf("unknown feature system: %q", name)
	}
	r.defaultName = name
	return nil
}

// Register adds or replaces a named system.
func (r *Registry) Register(name string, sys System) {
	r.mu.Lock()
	r.systems[name] = sys
	r.mu.Unlock()
}

// Geometry returns the default geometry used by this registry.
func (r *Registry) Geometry() *Geometry {
	return r.defaultGeom
}
