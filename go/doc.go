// Package merkmal provides phonological feature systems for computational
// historical linguistics.
//
// It loads pluggable model directories and geometry files via fs.FS,
// then exposes a System interface for feature extraction, distance
// computation, and partition derivation.
//
// # Supported model types
//
//   - categorical (descriptive, broad, distinctive)
//   - valued (phoible, pbase-hc, pbase-jfh, pbase-spe, pbase-uftc)
//   - trained (classfeat)
//
// # Quick start
//
//	modelsFS := os.DirFS("models")
//	geomFS := os.DirFS("geometries")
//	reg, _ := merkmal.NewRegistry(modelsFS, geomFS)
//	sys, _ := reg.Get("descriptive")
//	dist := sys.SegmentDistance("p", "b")
//
// # Embedding models
//
// For compiled-in models, use embed.FS:
//
//	//go:embed models
//	var modelsFS embed.FS
//	//go:embed geometries
//	var geomFS embed.FS
package merkmal
