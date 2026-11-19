package main

// Unit tests run against Fabric 1.4's shim.MockStub. MockStub executes
// transactions serially, so these tests check LOGIC (counting, thresholds,
// decisions, logs). MVCC/phantom conflicts only appear on a real network.

import (
	"encoding/json"
	"fmt"
	"testing"

	"github.com/golang/protobuf/ptypes/timestamp"
	"github.com/hyperledger/fabric/core/chaincode/shim"
)

func newStub(t *testing.T) *shim.MockStub {
	s := shim.NewMockStub("bgac-contention", new(Contention))
	s.TxTimestamp = &timestamp.Timestamp{Seconds: 1_700_000_000}
	return s
}

func call(t *testing.T, s *shim.MockStub, txID string, args ...string) []byte {
	b := [][]byte{}
	for _, a := range args {
		b = append(b, []byte(a))
	}
	r := s.MockInvoke(txID, b)
	if r.Status != shim.OK {
		t.Fatalf("%v failed: %s", args, r.Message)
	}
	return r.Payload
}

// run sends n requests and returns how many were allowed.
func run(t *testing.T, s *shim.MockStub, strategy, parts, limit string, n int, tag string) int {
	allowed := 0
	for i := 0; i < n; i++ {
		p := call(t, s, fmt.Sprintf("%s-tx%04d", tag, i), "request", strategy, "actorA", parts, limit, "0", tag)
		var e LogEntry
		if err := json.Unmarshal(p, &e); err != nil {
			t.Fatal(err)
		}
		if e.Allowed {
			allowed++
		}
	}
	return allowed
}

func TestSingleIsExact(t *testing.T) {
	if got := run(t, newStub(t), "single", "1", "50", 200, "s"); got != 50 {
		t.Fatalf("single admitted %d, want 50", got)
	}
}

func TestPartsumIsExactSerially(t *testing.T) {
	if got := run(t, newStub(t), "partsum", "16", "50", 200, "ps"); got != 50 {
		t.Fatalf("partsum admitted %d, want 50", got)
	}
}

func TestDeltarangeIsExactSerially(t *testing.T) {
	if got := run(t, newStub(t), "deltarange", "1", "50", 200, "dr"); got != 50 {
		t.Fatalf("deltarange admitted %d, want 50", got)
	}
}

func TestPartitionedIsApproximate(t *testing.T) {
	// floor(50/16)=3 per partition -> at most 16*3 = 48 admitted.
	got := run(t, newStub(t), "part", "16", "50", 400, "p")
	if got > 48 {
		t.Fatalf("part admitted %d, cap is 48", got)
	}
	// ceil(50/16)=4 per partition -> at most 64 admitted (over-admission possible).
	got2 := run(t, newStub(t), "partceil", "16", "50", 400, "pc")
	if got2 > 64 {
		t.Fatalf("partceil admitted %d, cap is 64", got2)
	}
	t.Logf("400 serial requests, limit 50: part16(floor) admitted %d, partceil16 admitted %d", got, got2)
}

func TestPartitionOneEqualsSingle(t *testing.T) {
	if got := run(t, newStub(t), "part", "1", "50", 200, "p1"); got != 50 {
		t.Fatalf("part with N=1 admitted %d, want 50", got)
	}
}

func TestDeltawriteNeedsCheckpoint(t *testing.T) {
	s := newStub(t)
	if got := run(t, s, "deltawrite", "1", "50", 60, "dw"); got != 60 {
		t.Fatalf("deltawrite without checkpoint admitted %d, want all 60", got)
	}
	n := call(t, s, "cp1", "checkpoint", "actorA", "0", "50")
	if string(n) != "60" {
		t.Fatalf("checkpoint counted %s, want 60", n)
	}
	if got := run(t, s, "deltawrite", "1", "50", 10, "dw2"); got != 0 {
		t.Fatalf("deltawrite after checkpoint admitted %d, want 0", got)
	}
}

func TestBlockStopsDeltawrite(t *testing.T) {
	s := newStub(t)
	if got := run(t, s, "deltawrite", "1", "50", 30, "b1"); got != 30 {
		t.Fatalf("before block admitted %d, want 30", got)
	}
	if n := call(t, s, "q-count", "count", "actorA", "0"); string(n) != "30" {
		t.Fatalf("count = %s, want 30", n)
	}
	call(t, s, "blk", "block", "actorA", "0")
	if got := run(t, s, "deltawrite", "1", "50", 10, "b2"); got != 0 {
		t.Fatalf("after block admitted %d, want 0", got)
	}
}

func TestExportLog(t *testing.T) {
	s := newStub(t)
	run(t, s, "single", "1", "5", 12, "exp")
	r := s.MockInvoke("q1", [][]byte{[]byte("exportLog"), []byte("exp")})
	var entries []LogEntry
	if err := json.Unmarshal(r.Payload, &entries); err != nil {
		t.Fatal(err)
	}
	if len(entries) != 12 {
		t.Fatalf("exported %d entries, want 12", len(entries))
	}
}

func TestPartitionDeterministic(t *testing.T) {
	if partitionFor("abc", 16) != partitionFor("abc", 16) {
		t.Fatal("partition not deterministic")
	}
}
