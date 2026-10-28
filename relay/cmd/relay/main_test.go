package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

type fakeStore struct {
	rollout int
	err     error
	calls   int
}

func (s *fakeStore) GetRollout(context.Context, string) (int, error) {
	s.calls++
	return s.rollout, s.err
}

func TestDecisionRejectsInvalidRequestsBeforeCache(t *testing.T) {
	for _, tc := range []struct {
		name, method, body string
		status             int
	}{
		{"method", "GET", `{}`, 405},
		{"malformed", "POST", `{`, 400},
		{"missing", "POST", `{}`, 400},
		{"blank", "POST", `{"device_id":" ","flag_name":"a"}`, 400},
		{"trailing", "POST", `{"device_id":"d","flag_name":"f"} {}`, 400},
		{"null", "POST", `null`, 400},
		{"large", "POST", `{"device_id":"` + strings.Repeat("d", 5000) + `","flag_name":"f"}`, 400},
	} {
		t.Run(tc.name, func(t *testing.T) {
			store := &fakeStore{}
			CacheClient = store
			w := httptest.NewRecorder()
			handleDecision(w, httptest.NewRequest(tc.method, "/decide", strings.NewReader(tc.body)))
			if w.Code != tc.status || store.calls != 0 {
				t.Fatalf("status=%d cache calls=%d", w.Code, store.calls)
			}
		})
	}
}

func TestDecisionRolloutBoundariesAndCacheFailure(t *testing.T) {
	for _, tc := range []struct {
		name    string
		rollout int
		err     error
		want    string
	}{
		{"disabled", 0, nil, "legacy"},
		{"enabled", 100, nil, "new"},
		{"unavailable", 100, errors.New("offline"), "legacy"},
		{"invalid-high", 101, nil, "legacy"},
		{"invalid-low", -1, nil, "legacy"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			CacheClient = &fakeStore{rollout: tc.rollout, err: tc.err}
			w := httptest.NewRecorder()
			handleDecision(w, httptest.NewRequest(http.MethodPost, "/decide", strings.NewReader(`{"device_id":"d","flag_name":"f"}`)))
			var got decisionResponse
			if err := json.Unmarshal(w.Body.Bytes(), &got); err != nil {
				t.Fatal(err)
			}
			if w.Code != 200 || got.Decision != tc.want || got.Bucket < 1 || got.Bucket > 100 {
				t.Fatalf("status=%d response=%+v", w.Code, got)
			}
		})
	}
}
