package main

import (
	"context"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"
	"strings"

	// This package is imported from the phase 1 to use the hashfunction
	"switchboard/relay/internal/cache"
	"switchboard/relay/internal/routing"
)

type rolloutStore interface {
	GetRollout(context.Context, string) (int, error)
}

var CacheClient rolloutStore

// so a struct is Go's way of grouping things together. Basically, this struct is used
// to define what the server expects from the incoming requests.
type decisionRequest struct {
	DeviceID string `json:"device_id"`
	FlagName string `json:"flag_name"`
}

// decisionReponse defines the response the server has to send back which is the feature bucket and the decision (Legacy or new feature)
type decisionResponse struct {
	Bucket   int    `json:"bucket"`
	Decision string `json:"decision"`
}

// Handle the decision (feature bucket or legacy)
func handleDecision(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.Header().Set("Allow", http.MethodPost)
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	r.Body = http.MaxBytesReader(w, r.Body, 4096)
	decoder := json.NewDecoder(r.Body)
	var req decisionRequest
	if err := decoder.Decode(&req); err != nil {
		http.Error(w, "invalid body request", http.StatusBadRequest)
		return
	}
	if err := decoder.Decode(new(any)); err != io.EOF {
		http.Error(w, "expected a single JSON object", http.StatusBadRequest)
		return
	}
	if strings.TrimSpace(req.DeviceID) == "" || strings.TrimSpace(req.FlagName) == "" {
		http.Error(w, "device_id and flag_name are required", http.StatusBadRequest)
		return
	}
	// Step 2: Call the BucketFor function to process
	bucket := routing.BucketFor(req.DeviceID, req.FlagName)
	rollout, err := CacheClient.GetRollout(r.Context(), req.FlagName)
	if err != nil || rollout < 0 || rollout > 100 {
		log.Printf("could not read rollout for flag %q: %v, defaulting to legacy", req.FlagName, err)
		rollout = 0

	}

	// Step 3: Compare the value against the hardcoded rollout percentage
	decision := "legacy"
	if bucket <= rollout {
		decision = "new"

	}
	// Step 4: Build the response and send it back
	response := decisionResponse{
		Bucket:   bucket,
		Decision: decision,
	}
	w.Header().Set("Content-type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func main() {

	redisAddr := os.Getenv("REDIS_ADDR")
	if redisAddr == "" {
		redisAddr = "localhost:6379"
	}
	CacheClient = cache.NewClient(redisAddr)

	//whenever a request comes in for the
	// address "/decide", run the handleDecision function to handle
	// it.
	http.HandleFunc("/decide", handleDecision)

	log.Println("relay listening on :8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}
