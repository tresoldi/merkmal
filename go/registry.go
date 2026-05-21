package merkmal

import (
	"fmt"
	"io/fs"
	"sort"
	"sync"
)

// Registry provides named access to loaded feature systems.
type Registry struct {
	mu            sync.RWMutex
	systems       map[string]System
	defaultName   string
	geometriesFS  fs.FS
	modelsFS      fs.FS
	defaultGeom   *Geometry
}

// NewRegistry creates a registry that discovers models from the given filesystems.
// modelsFS should contain model subdirectories; geometriesFS should contain geometry JSON files.
func NewRegistry(modelsFS, geometriesFS fs.FS) (*Registry, error) {
	geom, err := LoadGeometry(geometriesFS, "clements-hume")
	if err != nil {
		return nil, fmt.Errorf("loading default geometry: %w", err)
	}

	r := &Registry{
		systems:      make(map[string]System),
		defaultName:  "descriptive",
		geometriesFS: geometriesFS,
		modelsFS:     modelsFS,
		defaultGeom:  geom,
	}

	entries, err := fs.ReadDir(modelsFS, ".")
	if err != nil {
		return nil, fmt.Errorf("listing models: %w", err)
	}
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		name := entry.Name()
		modelFS, err := fs.Sub(modelsFS, name)
		if err != nil {
			continue
		}
		sys, err := LoadModel(modelFS, geom)
		if err != nil {
			continue
		}
		r.systems[name] = sys
	}

	return r, nil
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
