// bgac-contention — experiment chaincode for the second (contention) paper.
//
// It isolates ONE thing from the BGAC pipeline of fabric-realty: how the
// per-actor request counter is stored, read and updated. Everything else
// (roles, KMS, notifications, suspension) is deliberately left out so the
// measurements reflect the counting design only.
//
// Fabric 1.4.x, Go shim. Deterministic: time comes from stub.GetTxTimestamp(),
// partition choice from stub.GetTxID(); no randomness, no time.Now().
//
// Invoke functions
//   request    [strategy, actor, partitions, limit, bucketSecs, runTag]
//   checkpoint [actor, bucketSecs, limit]          (strategy "deltawrite" only)
//   block      [actor, bucketSecs]                 (E5 off-chain monitor: write-only)
// Query functions
//   exportLog  [runTag]   -> JSON array of LogEntry for that round
//   count      [actor, bucketSecs] -> number of delta keys in the current bucket
//
// Strategies (argument 0 of request)
//   single     one counter key per actor+bucket; read, compare, +1      (baseline)
//   part       N counter keys; tx reads/writes only partition hash(TxID)%N;
//              per-partition threshold = max(1, floor(limit/N))      (Array paper v2.1)
//   partceil   as part, threshold = ceil(limit/N)                    (other rounding)
//   partsum    N counter keys; tx READS ALL N, writes its own        (ablation)
//   deltarange one new key per request; count = range query over the
//              actor's delta keys (phantom-read check applies)
//   deltawrite one new key per request; NO read of counts; admits unless
//              a BLOCK flag exists, which only `checkpoint` writes
//
// A request ALWAYS returns shim.Success (decision in the payload) so that
// a denial is a committed, measurable outcome, not an endorsement error.
// Every request writes one unique LOG key so enforcement accuracy can be
// reconstructed from the committed ledger afterwards.
package main

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"strconv"

	"github.com/hyperledger/fabric/core/chaincode/shim"
	pb "github.com/hyperledger/fabric/protos/peer"
)

const (
	logObj   = "LOG"   // composite key: LOG~runTag~txID
	deltaObj = "DELTA" // composite key: DELTA~actor~bucket~txID
)

type Contention struct{}

type LogEntry struct {
	TxID      string `json:"txId"`
	RunTag    string `json:"runTag"`
	Strategy  string `json:"strategy"`
	Actor     string `json:"actor"`
	Partition int    `json:"partition"` // -1 when not partitioned
	Observed  int    `json:"observed"`  // count the decision was based on
	Threshold int    `json:"threshold"` // value Observed was compared with
	Allowed   bool   `json:"allowed"`
	TsNanos   int64  `json:"tsNanos"` // proposal timestamp (client-side)
}

func (c *Contention) Init(stub shim.ChaincodeStubInterface) pb.Response {
	return shim.Success(nil)
}

func (c *Contention) Invoke(stub shim.ChaincodeStubInterface) pb.Response {
	fn, args := stub.GetFunctionAndParameters()
	switch fn {
	case "request":
		return c.request(stub, args)
	case "checkpoint":
		return c.checkpoint(stub, args)
	case "exportLog":
		return c.exportLog(stub, args)
	case "count":
		return c.count(stub, args)
	case "block":
		return c.block(stub, args)
	}
	return shim.Error("unknown function: " + fn)
}

// ---------- helpers ----------

func partitionFor(txID string, n int) int {
	h := sha256.Sum256([]byte(txID))
	return int(binary.BigEndian.Uint32(h[:4]) % uint32(n))
}

func counterKey(actor string, bucket int64, part int) string {
	if part < 0 {
		return fmt.Sprintf("CNT_%s_%d", actor, bucket)
	}
	return fmt.Sprintf("CNT_%s_%d_p%d", actor, bucket, part)
}

func blockKey(actor string, bucket int64) string {
	return fmt.Sprintf("BLOCK_%s_%d", actor, bucket)
}

func readInt(stub shim.ChaincodeStubInterface, key string) (int, error) {
	b, err := stub.GetState(key)
	if err != nil {
		return 0, err
	}
	if b == nil {
		return 0, nil
	}
	return strconv.Atoi(string(b))
}

func writeInt(stub shim.ChaincodeStubInterface, key string, v int) error {
	return stub.PutState(key, []byte(strconv.Itoa(v)))
}

func txTime(stub shim.ChaincodeStubInterface) (int64, int64, error) {
	ts, err := stub.GetTxTimestamp()
	if err != nil {
		return 0, 0, err
	}
	return ts.Seconds, ts.Seconds*1e9 + int64(ts.Nanos), nil
}

func bucketOf(sec, bucketSecs int64) int64 {
	if bucketSecs <= 0 {
		return 0
	}
	return sec - sec%bucketSecs
}

func countDeltas(stub shim.ChaincodeStubInterface, actor string, bucket int64) (int, error) {
	it, err := stub.GetStateByPartialCompositeKey(deltaObj, []string{actor, strconv.FormatInt(bucket, 10)})
	if err != nil {
		return 0, err
	}
	defer it.Close()
	n := 0
	for it.HasNext() {
		if _, err := it.Next(); err != nil {
			return 0, err
		}
		n++
	}
	return n, nil
}

// ---------- request ----------

func (c *Contention) request(stub shim.ChaincodeStubInterface, args []string) pb.Response {
	if len(args) != 6 {
		return shim.Error("request needs [strategy, actor, partitions, limit, bucketSecs, runTag]")
	}
	strategy, actor, runTag := args[0], args[1], args[5]
	nParts, err1 := strconv.Atoi(args[2])
	limit, err2 := strconv.Atoi(args[3])
	bucketSecs, err3 := strconv.ParseInt(args[4], 10, 64)
	if err1 != nil || err2 != nil || err3 != nil || nParts < 1 || limit < 1 {
		return shim.Error("bad numeric argument")
	}
	txID := stub.GetTxID()
	sec, nanos, err := txTime(stub)
	if err != nil {
		return shim.Error(err.Error())
	}
	bucket := bucketOf(sec, bucketSecs)

	e := LogEntry{TxID: txID, RunTag: runTag, Strategy: strategy, Actor: actor, Partition: -1, TsNanos: nanos}

	switch strategy {
	case "single":
		k := counterKey(actor, bucket, -1)
		v, err := readInt(stub, k)
		if err != nil {
			return shim.Error(err.Error())
		}
		e.Observed, e.Threshold, e.Allowed = v, limit, v < limit
		if err := writeInt(stub, k, v+1); err != nil {
			return shim.Error(err.Error())
		}

	case "part", "partceil":
		p := partitionFor(txID, nParts)
		thr := limit / nParts
		if strategy == "partceil" {
			thr = (limit + nParts - 1) / nParts
		}
		if thr < 1 {
			thr = 1
		}
		k := counterKey(actor, bucket, p)
		v, err := readInt(stub, k)
		if err != nil {
			return shim.Error(err.Error())
		}
		e.Partition, e.Observed, e.Threshold, e.Allowed = p, v, thr, v < thr
		if err := writeInt(stub, k, v+1); err != nil {
			return shim.Error(err.Error())
		}

	case "partsum":
		p := partitionFor(txID, nParts)
		sum, own := 0, 0
		for i := 0; i < nParts; i++ {
			v, err := readInt(stub, counterKey(actor, bucket, i))
			if err != nil {
				return shim.Error(err.Error())
			}
			sum += v
			if i == p {
				own = v
			}
		}
		e.Partition, e.Observed, e.Threshold, e.Allowed = p, sum, limit, sum < limit
		if err := writeInt(stub, counterKey(actor, bucket, p), own+1); err != nil {
			return shim.Error(err.Error())
		}

	case "deltarange":
		n, err := countDeltas(stub, actor, bucket)
		if err != nil {
			return shim.Error(err.Error())
		}
		e.Observed, e.Threshold, e.Allowed = n, limit, n < limit
		if err := c.putDelta(stub, actor, bucket, txID); err != nil {
			return shim.Error(err.Error())
		}

	case "deltawrite":
		blocked, err := stub.GetState(blockKey(actor, bucket))
		if err != nil {
			return shim.Error(err.Error())
		}
		e.Observed, e.Threshold, e.Allowed = -1, limit, blocked == nil
		if err := c.putDelta(stub, actor, bucket, txID); err != nil {
			return shim.Error(err.Error())
		}

	default:
		return shim.Error("unknown strategy: " + strategy)
	}

	lk, err := stub.CreateCompositeKey(logObj, []string{runTag, txID})
	if err != nil {
		return shim.Error(err.Error())
	}
	b, _ := json.Marshal(e)
	if err := stub.PutState(lk, b); err != nil {
		return shim.Error(err.Error())
	}
	return shim.Success(b)
}

func (c *Contention) putDelta(stub shim.ChaincodeStubInterface, actor string, bucket int64, txID string) error {
	k, err := stub.CreateCompositeKey(deltaObj, []string{actor, strconv.FormatInt(bucket, 10), txID})
	if err != nil {
		return err
	}
	return stub.PutState(k, []byte{1})
}

// ---------- checkpoint (deltawrite companion) ----------

// checkpoint counts the actor's delta keys and writes the BLOCK flag once the
// count reaches the limit. Run it periodically (scripts/checkpoint_loop.sh).
func (c *Contention) checkpoint(stub shim.ChaincodeStubInterface, args []string) pb.Response {
	if len(args) != 3 {
		return shim.Error("checkpoint needs [actor, bucketSecs, limit]")
	}
	bucketSecs, err1 := strconv.ParseInt(args[1], 10, 64)
	limit, err2 := strconv.Atoi(args[2])
	if err1 != nil || err2 != nil {
		return shim.Error("bad numeric argument")
	}
	sec, _, err := txTime(stub)
	if err != nil {
		return shim.Error(err.Error())
	}
	bucket := bucketOf(sec, bucketSecs)
	n, err := countDeltas(stub, args[0], bucket)
	if err != nil {
		return shim.Error(err.Error())
	}
	if n >= limit {
		if err := stub.PutState(blockKey(args[0], bucket), []byte(strconv.Itoa(n))); err != nil {
			return shim.Error(err.Error())
		}
	}
	return shim.Success([]byte(strconv.Itoa(n)))
}

// block writes the BLOCK flag without reading anything, so it can never
// conflict. It is the write half of the off-chain monitor used in E5: the
// client queries "count" (read-only, not validated) and calls "block" once
// the count reaches the limit.
func (c *Contention) block(stub shim.ChaincodeStubInterface, args []string) pb.Response {
	if len(args) != 2 {
		return shim.Error("block needs [actor, bucketSecs]")
	}
	bucketSecs, err := strconv.ParseInt(args[1], 10, 64)
	if err != nil {
		return shim.Error("bad bucketSecs")
	}
	sec, _, err := txTime(stub)
	if err != nil {
		return shim.Error(err.Error())
	}
	if err := stub.PutState(blockKey(args[0], bucketOf(sec, bucketSecs)), []byte("1")); err != nil {
		return shim.Error(err.Error())
	}
	return shim.Success(nil)
}

// ---------- queries ----------

func (c *Contention) exportLog(stub shim.ChaincodeStubInterface, args []string) pb.Response {
	if len(args) != 1 {
		return shim.Error("exportLog needs [runTag]")
	}
	it, err := stub.GetStateByPartialCompositeKey(logObj, []string{args[0]})
	if err != nil {
		return shim.Error(err.Error())
	}
	defer it.Close()
	out := []json.RawMessage{}
	for it.HasNext() {
		kv, err := it.Next()
		if err != nil {
			return shim.Error(err.Error())
		}
		out = append(out, json.RawMessage(kv.Value))
	}
	b, _ := json.Marshal(out)
	return shim.Success(b)
}

func (c *Contention) count(stub shim.ChaincodeStubInterface, args []string) pb.Response {
	if len(args) != 2 {
		return shim.Error("count needs [actor, bucketSecs]")
	}
	bucketSecs, err := strconv.ParseInt(args[1], 10, 64)
	if err != nil {
		return shim.Error("bad bucketSecs")
	}
	sec, _, err := txTime(stub)
	if err != nil {
		return shim.Error(err.Error())
	}
	n, err := countDeltas(stub, args[0], bucketOf(sec, bucketSecs))
	if err != nil {
		return shim.Error(err.Error())
	}
	return shim.Success([]byte(strconv.Itoa(n)))
}

func main() {
	if err := shim.Start(new(Contention)); err != nil {
		fmt.Printf("Error starting bgac-contention chaincode: %s\n", err)
	}
}
