package merkmal

// Role represents the prosodic role of a grapheme.
type Role byte

const (
	RoleC       Role = 'C' // obstruent consonant
	RoleV       Role = 'V' // vowel
	RoleR       Role = 'R' // sonorant consonant (nasal, lateral, trill, tap)
	RoleG       Role = 'G' // glide / approximant
	RoleT       Role = 'T' // tone
	RoleS       Role = 'S' // suprasegmental (stress, length)
	RoleUnknown Role = 'X'
)

func (r Role) String() string { return string(r) }

// System is the interface all feature-system implementations satisfy.
type System interface {
	Name() string
	RepresentationKind() string
	ListGraphemes() []string
	GraphemeToFeatures(grapheme string) (map[string]bool, bool)
	FeatureDistance(a, b string) float64
	SegmentDistance(a, b string, opts ...DistanceOption) float64
	SoundDistance(featsA, featsB map[string]bool, opts ...DistanceOption) float64
	IsSegment(grapheme string) bool
	IsClass(grapheme string) bool
	ClassFeatures(grapheme string) (map[string]bool, bool)
}

// DistanceOption configures distance computation.
type DistanceOption func(*distanceConfig)

type distanceConfig struct {
	nodeWeights   map[string]float64
	presetName    string
	featureToNode map[string]string
}

func applyOpts(opts []DistanceOption) distanceConfig {
	var cfg distanceConfig
	for _, o := range opts {
		o(&cfg)
	}
	return cfg
}

// WithNodeWeights sets explicit per-node weights for distance computation.
func WithNodeWeights(w map[string]float64) DistanceOption {
	return func(c *distanceConfig) { c.nodeWeights = w }
}

// WithPreset selects a named weight preset (e.g. "ignore-tone", "flat").
func WithPreset(name string) DistanceOption {
	return func(c *distanceConfig) { c.presetName = name }
}
