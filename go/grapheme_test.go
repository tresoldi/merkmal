package merkmal

import (
	"reflect"
	"strings"
	"testing"

	"golang.org/x/text/unicode/norm"
)

func TestSegmentIPA(t *testing.T) {
	tests := []struct {
		input string
		want  []string
	}{
		{"pa", []string{"p", "a"}},
		{"tʰoŋ", []string{"tʰ", "o", "ŋ"}},
		{"t͡sʰa", []string{"t͡sʰ", "a"}},
		{"k͡pa", []string{"k͡p", "a"}},
		{"ⁿda", []string{"ⁿd", "a"}},
		{"aːi", []string{"aː", "i"}},
		{"kan⁵⁵", []string{"k", "a", "n", "⁵⁵"}},
		{"a+b", []string{"a", "+", "b"}},
		{"a.b", []string{"a", ".", "b"}},
		{"p a", []string{"p", "a"}},
		{"str", []string{"s", "t", "r"}},
		{"p", []string{"p"}},
		{"", nil},
	}

	for _, tc := range tests {
		got := SegmentIPA(tc.input)
		if tc.want == nil && got == nil {
			continue
		}
		if !reflect.DeepEqual(got, tc.want) {
			t.Errorf("SegmentIPA(%q) = %v, want %v", tc.input, got, tc.want)
		}
	}
}

func TestSegmentIPARoundtrip(t *testing.T) {
	inputs := []string{"pʰatʰa", "t͡sʰit͡sʰa", "ⁿdaⁿba"}
	for _, ipa := range inputs {
		segments := SegmentIPA(ipa)
		joined := strings.Join(segments, "")
		nfd := norm.NFD.String(ipa)
		if joined != nfd {
			t.Errorf("SegmentIPA(%q) roundtrip: got %q, want %q", ipa, joined, nfd)
		}
	}
}

func TestSegmentIPAChaoSeparate(t *testing.T) {
	segments := SegmentIPA("tʰo³¹pan¹³")
	found31 := false
	found13 := false
	for _, s := range segments {
		if s == "³¹" {
			found31 = true
		}
		if s == "¹³" {
			found13 = true
		}
	}
	if !found31 || !found13 {
		t.Errorf("SegmentIPA did not emit Chao groups as separate tokens: %v", segments)
	}
}

func TestMergeToneDigits(t *testing.T) {
	tests := []struct {
		input []string
		want  []string
	}{
		{
			[]string{"tʰ", "o", "³¹", "+", "p", "e", "j", "¹³"},
			[]string{"tʰ", "o³¹", "+", "p", "e¹³", "j"},
		},
		{
			[]string{"k", "a", "n", "⁵⁵"},
			[]string{"k", "a⁵⁵", "n"},
		},
		{
			[]string{"a", "⁰"},
			[]string{"a"},
		},
		{
			[]string{"p", "a"},
			[]string{"p", "a"},
		},
		{
			[]string{"tʰ", "a", "ŋ", "³", "⁵"},
			[]string{"tʰ", "a³⁵", "ŋ"},
		},
		{
			[]string{"m", "a", "⁵", "¹"},
			[]string{"m", "a⁵¹"},
		},
	}

	for _, tc := range tests {
		got := MergeToneDigits(tc.input)
		if !reflect.DeepEqual(got, tc.want) {
			t.Errorf("MergeToneDigits(%v) = %v, want %v", tc.input, got, tc.want)
		}
	}
}

func TestSegmentMergePipeline(t *testing.T) {
	segments := SegmentIPA("tʰo³¹pan¹³")
	merged := MergeToneDigits(segments)
	found := false
	for _, s := range merged {
		if s == "o³¹" {
			found = true
		}
	}
	if !found {
		t.Errorf("pipeline did not produce o³¹: %v", merged)
	}
}

func TestNormalizeInputGrapheme(t *testing.T) {
	tests := []struct {
		input string
		want  string
	}{
		{"ɡ", "g"},    // reversible IPA equivalence
		{"y/j", "j"},  // CLTS slash: keep post-slash
		{"sh/ʃ", "ʃ"}, // CLTS slash with digraph source
		{"ʤ", "dʒ"},   // ligature expansion
		{"ʧ", "tʃ"},   //
		{"ʨ", "tɕ"},   //
		{"a:", "aː"},  // ASCII colon → length
		{"ˈɛ", "ɛ"},   // leading stress stripped
		{"ˌa", "a"},   //
	}
	for _, tt := range tests {
		if got := NormalizeInputGrapheme(tt.input); got != tt.want {
			t.Errorf("NormalizeInputGrapheme(%q) = %q, want %q", tt.input, got, tt.want)
		}
	}
	// last slash wins; pre-slash content discarded
	if got, want := NormalizeInputGrapheme("tsʰ~ʨʰ/ʨʰ"), NormalizeInputGrapheme("ʨʰ"); got != want {
		t.Errorf("slash last-wins: got %q want %q", got, want)
	}
}

func TestNormalize(t *testing.T) {
	tests := []struct {
		input string
		want  string
	}{
		{"y/j", "j"},
		{"ʤ", "dʒ"},
		{"a:", "aː"},
		{"ˈɛ", "ɛ"},
		{"g", "ɡ"}, // mapped back to preferred IPA
		{"ˈ", ""},  // bare stress normalizes away
	}
	for _, tt := range tests {
		if got := Normalize(tt.input); got != tt.want {
			t.Errorf("Normalize(%q) = %q, want %q", tt.input, got, tt.want)
		}
	}
	// NFC output and idempotence on clean IPA
	if got := Normalize(norm.NFD.String("ã")); got != "ã" {
		t.Errorf("Normalize NFC: got %q", got)
	}
	for _, g := range []string{"p", "t̠ʃ", "aː", "kʰ", "o⁵⁵"} {
		if Normalize(g) != Normalize(Normalize(g)) {
			t.Errorf("Normalize not idempotent on %q", g)
		}
	}
}
