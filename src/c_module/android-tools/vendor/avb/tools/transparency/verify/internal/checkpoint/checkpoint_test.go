package checkpoint

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"path"
	"testing"

	"github.com/google/go-cmp/cmp"
)

func TestInvalidCheckpointFormat(t *testing.T) {
	tests := []struct {
		desc    string
		m       string
		wantErr bool
	}{
		{
			desc:    "unknown origin",
			m:       "UNKNOWN\n1\nbananas\n",
			wantErr: true,
		},
		{
			desc:    "bad size",
			m:       "developers.google.com/android/binary_transparency/0\n-1\nbananas\n",
			wantErr: true,
		},
		{
			desc:    "not enough newlines",
			m:       "developers.google.com/android/binary_transparency/0\n1\n",
			wantErr: true,
		},
		{
			desc:    "non-numeric size",
			m:       "developers.google.com/android/binary_transparency/0\nbananas\ndGhlIHZpZXcgZnJvbSB0aGUgdHJlZSB0b3BzIGlzIGdyZWF0IQ==\n",
			wantErr: true,
		},
		{
			desc:    "too many newlines",
			m:       "developers.google.com/android/binary_transparency/0\n1\n\n\n\n",
			wantErr: true,
		},
		{
			desc:    "does not end with newline",
			m:       "developers.google.com/android/binary_transparency/0\n1\ngarbage",
			wantErr: true,
		},
		{
			desc:    "invalid - empty header",
			m:       "\n9944\ndGhlIHZpZXcgZnJvbSB0aGUgdHJlZSB0b3BzIGlzIGdyZWF0IQ==\n",
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.desc, func(t *testing.T) {
			if _, gotErr := parseCheckpoint(tt.m); gotErr == nil {
				t.Fatalf("fromText(%v): want error, got nil", tt.m)
			}
		})
	}
}

// testServer serves a test envelope `e` at path "test/file" and 404 otherwise.
// It is used to minimally test FromURL.
func testServer(t *testing.T, e string) *httptest.Server {
	t.Helper()
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.String() == "/test/file/checkpoint.txt" {
			w.Write([]byte(e))
		} else {
			w.WriteHeader(http.StatusNotFound)
		}
	}))
}

// TestGetSignedCheckpoint is a minimal test to check URL I/O.
// Content specific tests are done in the other tests.
func TestGetSignedCheckpoint(t *testing.T) {
	serverContent := "testContent"
	s := testServer(t, serverContent)
	u, err := url.Parse(s.URL)
	if err != nil {
		t.Fatalf("invalid URL for testServer %s: %v", s.URL, err)
	}
	defer s.Close()

	for _, tt := range []struct {
		desc    string
		path    string
		want    string
		wantErr bool
	}{
		{
			desc:    "good_file",
			path:    "test/file",
			want:    serverContent,
			wantErr: false,
		},
		{
			desc:    "bad_path",
			path:    "bad/path",
			wantErr: true,
		},
	} {
		t.Run(tt.desc, func(t *testing.T) {
			u.Path = path.Join(u.Path, tt.path)
			b, gotErr := getSignedCheckpoint(u.String())
			got := string(b)
			if diff := cmp.Diff(got, tt.want); diff != "" {
				t.Errorf("bad response body: got %v, want %v", got, tt.want)
			}
			if gotErr != nil && !tt.wantErr {
				t.Errorf("unexpected error: got %t, want %t", gotErr, tt.wantErr)
			}
		})
	}
}
