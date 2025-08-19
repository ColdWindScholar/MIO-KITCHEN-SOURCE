// Package checkpoint implements methods to interact with checkpoints
// as described below.
//
// Root is the internal representation of the information needed to
// commit to the contents of the tree, and contains the root hash and size.
//
// When a commitment needs to be sent to other processes (such as a witness or
// other log clients), it is put in the form of a checkpoint, which also
// includes an "origin" string. The origin should is a unique identifier for
// the log identity which issues the checkpoint. This package deals only with
// the origin for the Pixel Binary Transparency Log.
//
// This checkpoint is signed in a note format (golang.org/x/mod/sumdb/note)
// before sending out. An unsigned checkpoint is not a valid commitment and
// must not be used.
//
// There is only a single signature.
// Support for multiple signing identities will be added as needed.
package checkpoint

import (
	"crypto/ecdsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/binary"
	"encoding/pem"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"path"
	"strconv"
	"strings"

	"golang.org/x/mod/sumdb/note"
)

const (
	// originID identifies a checkpoint for the Pixel Binary Transparency Log.
	originID = "developers.google.com/android/binary_transparency/0\n"
)

type verifier interface {
	Verify(msg []byte, sig []byte) bool
	Name() string
	KeyHash() uint32
}

// EcdsaVerifier verifies a message signature that was signed using ECDSA.
type EcdsaVerifier struct {
	PubKey *ecdsa.PublicKey
	name   string
	hash   uint32
}

// Verify returns whether the signature of the message is valid using its
// pubKey.
func (v EcdsaVerifier) Verify(msg, sig []byte) bool {
	h := sha256.Sum256(msg)
	if !ecdsa.VerifyASN1(v.PubKey, h[:], sig) {
		return false
	}
	return true
}

// KeyHash returns a 4 byte hash of the public key to be used as a hint to the
// verifier.
func (v EcdsaVerifier) KeyHash() uint32 {
	return v.hash
}

// Name returns the name of the key.
func (v EcdsaVerifier) Name() string {
	return v.name
}

// NewVerifier expects an ECDSA public key in PEM format in a file with the provided path and key name.
func NewVerifier(pemKey []byte, name string) (EcdsaVerifier, error) {
	b, _ := pem.Decode(pemKey)
	if b == nil || b.Type != "PUBLIC KEY" {
		return EcdsaVerifier{}, fmt.Errorf("Failed to decode public key, must contain an ECDSA public key in PEM format")
	}

	key := b.Bytes
	sum := sha256.Sum256(key)
	keyHash := binary.BigEndian.Uint32(sum[:])

	pub, err := x509.ParsePKIXPublicKey(key)
	if err != nil {
		return EcdsaVerifier{}, fmt.Errorf("Can't parse key: %v", err)
	}
	return EcdsaVerifier{
		PubKey: pub.(*ecdsa.PublicKey),
		hash:   keyHash,
		name:   name,
	}, nil
}

// Root contains the checkpoint data.
type Root struct {
	// Size is the number of entries in the log at this point.
	Size uint64
	// Hash commits to the contents of the entire log.
	Hash []byte
}

func parseCheckpoint(ckpt string) (Root, error) {
	if !strings.HasPrefix(ckpt, originID) {
		return Root{}, errors.New(fmt.Sprintf("invalid checkpoint - unknown origin, must be %s", originID))
	}
	// Strip the origin ID and parse the rest of the checkpoint.
	body := ckpt[len(originID):]
	// body must contain exactly 2 lines, size and the root hash.
	l := strings.SplitN(body, "\n", 3)
	if len(l) != 3 || len(l[2]) != 0 {
		return Root{}, errors.New("invalid checkpoint - bad format: must have origin id, size and root hash each followed by newline")
	}
	size, err := strconv.ParseUint(l[0], 10, 64)
	if err != nil {
		return Root{}, fmt.Errorf("invalid checkpoint - cannot read size: %w", err)
	}
	rh, err := base64.StdEncoding.DecodeString(l[1])
	if err != nil {
		return Root{}, fmt.Errorf("invalid checkpoint - invalid roothash: %w", err)
	}
	return Root{Size: size, Hash: rh}, nil
}

func getSignedCheckpoint(logURL string) ([]byte, error) {
	// Sanity check the input url.
	u, err := url.Parse(logURL)
	if err != nil {
		return []byte{}, fmt.Errorf("invalid URL %s: %v", u, err)
	}

	u.Path = path.Join(u.Path, "checkpoint.txt")

	resp, err := http.Get(u.String())
	if err != nil {
		return []byte{}, fmt.Errorf("http.Get(%s): %v", u, err)
	}
	defer resp.Body.Close()
	if code := resp.StatusCode; code != 200 {
		return []byte{}, fmt.Errorf("http.Get(%s): %s", u, http.StatusText(code))
	}

	return io.ReadAll(resp.Body)
}

// FromURL verifies the signature and unpacks and returns a Root.
//
// Validates signature before reading data, using a provided verifier.
// Data at `logURL` is the checkpoint and must be in the note format
// (golang.org/x/mod/sumdb/note).
//
// The checkpoint must be for the Pixel Binary Transparency Log origin.
//
// Returns error if the signature fails to verify or if the checkpoint
// does not conform to the following format:
//
//	[]byte("[origin]\n[size]\n[hash]").
func FromURL(logURL string, v verifier) (Root, error) {
	b, err := getSignedCheckpoint(logURL)
	if err != nil {
		return Root{}, fmt.Errorf("failed to get signed checkpoint: %v", err)
	}

	n, err := note.Open(b, note.VerifierList(v))
	if err != nil {
		return Root{}, fmt.Errorf("failed to verify note signatures: %v", err)
	}
	return parseCheckpoint(n.Text)
}
