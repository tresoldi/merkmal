package merkmal

// FeatureState represents a symbolic feature value used by multi-state systems.
type FeatureState string

const (
	StatePositive FeatureState = "+"
	StateNegative FeatureState = "-"
	StateN        FeatureState = "n"
	StateDot      FeatureState = "."
	StateO        FeatureState = "o"
	StateX        FeatureState = "x"
)
