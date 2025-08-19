package tiles

import (
	"bytes"
	"context"
	"encoding/hex"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/google/go-cmp/cmp"
	"golang.org/x/mod/sumdb/tlog"
)

const (
	tileHeight = 1
)

// mustHexDecode decodes its input string from hex and panics if this fails.
func mustHexDecode(b string) []byte {
	r, err := hex.DecodeString(b)
	if err != nil {
		log.Fatalf("unable to decode string %v", err)
	}
	return r
}

// nodeHashes is a structured slice of node hashes for all complete subtrees of a Merkle tree built from test data using the RFC 6962 hashing strategy. The first index in the slice is the tree level (zero being the leaves level), the second is the horizontal index within a level.
var nodeHashes = [][][]byte{{
	mustHexDecode("6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d"),
	mustHexDecode("96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7"),
	mustHexDecode("0298d122906dcfc10892cb53a73992fc5b9f493ea4c9badb27b791b4127a7fe7"),
	mustHexDecode("07506a85fd9dd2f120eb694f86011e5bb4662e5c415a62917033d4a9624487e7"),
	mustHexDecode("bc1a0643b12e4d2d7c77918f44e0f4f79a838b6cf9ec5b5c283e1f4d88599e6b"),
	mustHexDecode("4271a26be0d8a84f0bd54c8c302e7cb3a3b5d1fa6780a40bcce2873477dab658"),
	mustHexDecode("b08693ec2e721597130641e8211e7eedccb4c26413963eee6c1e2ed16ffb1a5f"),
	mustHexDecode("46f6ffadd3d06a09ff3c5860d2755c8b9819db7df44251788c7d8e3180de8eb1"),
}, {
	mustHexDecode("fac54203e7cc696cf0dfcb42c92a1d9dbaf70ad9e621f4bd8d98662f00e3c125"),
	mustHexDecode("5f083f0a1a33ca076a95279832580db3e0ef4584bdff1f54c8a360f50de3031e"),
	mustHexDecode("0ebc5d3437fbe2db158b9f126a1d118e308181031d0a949f8dededebc558ef6a"),
	mustHexDecode("ca854ea128ed050b41b35ffc1b87b8eb2bde461e9e3b5596ece6b9d5975a0ae0"),
}, {
	mustHexDecode("d37ee418976dd95753c1c73862b9398fa2a2cf9b4ff0fdfe8b30cd95209614b7"),
	mustHexDecode("6b47aaf29ee3c2af9af889bc1fb9254dabd31177f16232dd6aab035ca39bf6e4"),
}, {
	mustHexDecode("5dc9da79a70659a9ad559cb701ded9a2ab9d823aad2f4960cfe370eff4604328"),
}}

// testServer serves a tile based log of height 1, using the test data in
// nodeHashes.
func testServer(ctx context.Context, t *testing.T) *httptest.Server {
	t.Helper()
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {

		// Parse the tile data out of r.URL.
		// Strip the leading `/` to get a valid tile path.
		tile, err := tlog.ParseTilePath(r.URL.String()[1:])
		if err != nil {
			t.Fatalf("ParseTilePath(%s): %v", r.URL.String(), err)
		}
		// Fill the response with the test nodeHashes ...
		io.Copy(w, bytes.NewReader(nodeHashes[tile.L][2*tile.N]))
		if tile.W == 2 {
			// ... with special handling when the width is 2
			io.Copy(w, bytes.NewReader(nodeHashes[tile.L][2*tile.N+1]))
		}
	}))
}

func TestReadHashesWithReadTileData(t *testing.T) {
	ctx := context.Background()
	s := testServer(ctx, t)
	defer s.Close()

	for _, tc := range []struct {
		desc string
		size uint64
		want [][]byte
	}{
		{desc: "empty-0", size: 0},
		{
			desc: "size-3",
			size: 3,
			want: [][]byte{
				nodeHashes[0][0],
				append(nodeHashes[0][0], nodeHashes[0][1]...),
				nodeHashes[1][0],
				nodeHashes[0][2],
			},
		},
	} {
		t.Run(tc.desc, func(t *testing.T) {
			r := HashReader{URL: s.URL}

			// Read hashes.
			for i, want := range tc.want {
				tile := tlog.TileForIndex(tileHeight, int64(i))
				got, err := tlog.ReadTileData(tile, r)
				if err != nil {
					t.Fatalf("ReadTileData: %v", err)
				}
				if !cmp.Equal(got, want) {
					t.Errorf("tile %+v: got %X, want %X", tile, got, want)
				}
			}
		})
	}
}

func TestReadHashesCachedTile(t *testing.T) {
	ctx := context.Background()
	s := testServer(ctx, t)
	defer s.Close()

	wantHash := nodeHashes[0][0]
	r := HashReader{URL: s.URL}

	// Read hash at index 0 twice, to exercise the caching of tiles.
	// On the first pass, the read is fresh and readFromURL is called.
	// On the second pass, the tile is cached, so we skip readFromURL.
	// We don't explicitly check that readFromURL is only called once,
	// but we do check ReadHashes returns the correct values.
	indices := []int64{0, 0}
	hashes, err := r.ReadHashes(indices)
	if err != nil {
		t.Fatalf("ReadHashes: %v", err)
	}

	got := make([][]byte, 0, len(indices))
	for _, hash := range hashes {
		got = append(got, hash[:])
	}

	if !bytes.Equal(got[0], got[1]) {
		t.Errorf("expected the same hash: got %X, want %X", got[0], got[1])
	}
	if !bytes.Equal(got[0], wantHash) {
		t.Errorf("wrong ReadHashes result: got %X, want %X", got[0], wantHash)
	}
}

func TestParseImageInfosIndex(t *testing.T) {
	for _, tc := range []struct {
		desc       string
		imageInfos string
		want       map[string]int64
		wantErr    bool
	}{
		{
			desc:       "size 2",
			imageInfos: "0\nbuild_fingerprint0\nimage_digest0\n\n1\nbuild_fingerprint1\nimage_digest1\n",
			wantErr:    false,
			want: map[string]int64{
				"build_fingerprint0\nimage_digest0\n": 0,
				"build_fingerprint1\nimage_digest1\n": 1,
			},
		},
		{
			desc:       "invalid log entry (no newlines)",
			imageInfos: "0build_fingerprintimage_digest",
			wantErr:    true,
		},
	} {
		t.Run(tc.desc, func(t *testing.T) {
			got, err := parseImageInfosIndex(tc.imageInfos)
			if err != nil && !tc.wantErr {
				t.Fatalf("parseImageInfosIndex(%s) received unexpected err %q", tc.imageInfos, err)
			}

			if err == nil && tc.wantErr {
				t.Fatalf("parseImageInfosIndex(%s) did not return err, expected err", tc.imageInfos)
			}

			if diff := cmp.Diff(tc.want, got); diff != "" {
				t.Errorf("parseImageInfosIndex returned unexpected diff (-want +got):\n%s", diff)
			}
		})
	}
}
