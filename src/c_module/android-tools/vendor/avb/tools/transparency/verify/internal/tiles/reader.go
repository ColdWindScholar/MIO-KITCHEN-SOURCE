// Package tiles contains methods to work with tlog based verifiable logs.
package tiles

import (
	"crypto/sha256"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"path"
	"strconv"
	"strings"

	"golang.org/x/mod/sumdb/tlog"
)

// HashReader implements tlog.HashReader, reading from tlog-based log located at
// URL.
type HashReader struct {
	URL string
}


// Domain separation prefix for Merkle tree hashing with second preimage
// resistance similar to that used in RFC 6962.
const (
	leafHashPrefix = 0
)

// ReadHashes implements tlog.HashReader's ReadHashes.
// See: https://pkg.go.dev/golang.org/x/mod/sumdb/tlog#HashReader.
func (h HashReader) ReadHashes(indices []int64) ([]tlog.Hash, error) {
	tiles := make(map[string][]byte)
	hashes := make([]tlog.Hash, 0, len(indices))
	for _, index := range indices {
		// The PixelBT log is tiled at height = 1.
		tile := tlog.TileForIndex(1, index)

		var content []byte
		var exists bool
		var err error
		content, exists = tiles[tile.Path()]
		if !exists {
			content, err = readFromURL(h.URL, tile.Path())
			if err != nil {
				return nil, fmt.Errorf("failed to read from %s: %v", tile.Path(), err)
			}
			tiles[tile.Path()] = content
		}

		hash, err := tlog.HashFromTile(tile, content, index)
		if err != nil {
			return nil, fmt.Errorf("failed to read data from tile for index %d: %v", index, err)
		}
		hashes = append(hashes, hash)
	}
	return hashes, nil
}

// ImageInfosIndex returns a map from payload to its index in the
// transparency log according to the image_info.txt.
func ImageInfosIndex(logBaseURL string) (map[string]int64, error) {
	b, err := readFromURL(logBaseURL, "image_info.txt")
	if err != nil {
		return nil, err
	}

	imageInfos := string(b)
	return parseImageInfosIndex(imageInfos)
}

func parseImageInfosIndex(imageInfos string) (map[string]int64, error) {
	m := make(map[string]int64)

	infosStr := strings.Split(imageInfos, "\n\n")
	for _, infoStr := range infosStr {
		pieces := strings.SplitN(infoStr, "\n", 2)
		if len(pieces) != 2 {
			return nil, errors.New("missing newline, malformed image_info.txt")
		}

		idx, err := strconv.ParseInt(pieces[0], 10, 64)
		if err != nil {
			return nil, fmt.Errorf("failed to convert %q to int64", pieces[0])
		}

		// Ensure that each log entry does not have extraneous whitespace, but
		// also terminates with a newline.
		logEntry := strings.TrimSpace(pieces[1]) + "\n"
		m[logEntry] = idx
	}

	return m, nil
}

func readFromURL(base, suffix string) ([]byte, error) {
	u, err := url.Parse(base)
	if err != nil {
		return nil, fmt.Errorf("invalid URL %s: %v", base, err)
	}
	u.Path = path.Join(u.Path, suffix)

	resp, err := http.Get(u.String())
	if err != nil {
		return nil, fmt.Errorf("http.Get(%s): %v", u.String(), err)
	}
	defer resp.Body.Close()
	if code := resp.StatusCode; code != 200 {
		return nil, fmt.Errorf("http.Get(%s): %s", u.String(), http.StatusText(code))
	}

	return io.ReadAll(resp.Body)
}

// PayloadHash returns the hash of the payload.
func PayloadHash(p []byte) (tlog.Hash, error) {
	l := append([]byte{leafHashPrefix}, p...)
	h := sha256.Sum256(l)

	var hash tlog.Hash
	copy(hash[:], h[:])
	return hash, nil
}
