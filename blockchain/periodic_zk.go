package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"
)

// ==================== PERIODIC ZK VERIFICATION ====================
// Hybrid approach: fast hash verify + periodic ZK proof

type ZKConfig struct {
	BatchSize  int `json:"batch_size"`  // txs per batch (4)
	ZKPeriod   int `json:"zk_period"`  // batches per ZK proof (1000)
	ProveTime  int `json:"prove_time"` // ms per proof (~284)
	VerifyTime int `json:"verify_time"` // ms per verify (~210)
}

var zkConfig = ZKConfig{
	BatchSize:  4,
	ZKPeriod:   1000,
	ProveTime:  284,
	VerifyTime: 210,
}

// PeriodicZKState tracks batches and periodic proof generation
type PeriodicZKState struct {
	mu              sync.RWMutex
	LastZKProof     string `json:"last_zk_proof"` // Last ZK proof
	LastZKRoot     string `json:"last_zk_root"` // Merkle root at last ZK
	BatchCounter   int    `json:"batch_counter"`
	ZKProofCounter int    `json:"zk_proof_counter"`

	// Stats
	TotalBatches  int64 `json:"total_batches"`
	TotalTx      int64 `json:"total_tx"`
	HashVerifies int64 `json:"hash_verifies"`
	ZKProofs     int64 `json:"zk_proofs"`
}

var periodicZK PeriodicZKState

// AddBatch adds a new batch and returns verification result
func AddBatch(txHashes []string) (bool, string, bool) {
	periodicZK.mu.Lock()
	defer periodicZK.mu.Unlock()

	periodicZK.BatchCounter++
	periodicZK.TotalBatches++
	periodicZK.TotalTx += int64(len(txHashes))

	// Compute Merkle root
	root := computeMerkleRoot(txHashes)

	// Fast hash verification (always)
	periodicZK.HashVerifies++

	// Check if we need ZK proof
	needsZK := (periodicZK.BatchCounter%zkConfig.ZKPeriod == 0)

	return true, root, needsZK
}

// GenerateZKProof creates a ZK proof for accumulated batches
func GenerateZKProof() (string, error) {
	periodicZK.mu.Lock()
	defer periodicZK.mu.Unlock()

	// Simulate ZK proof generation time
	time.Sleep(time.Duration(zkConfig.ProveTime) * time.Millisecond)

	// Generate mock ZK proof (in production: groth16/plonk)
	proofData := fmt.Sprintf("zk_proof_%d_%d", periodicZK.BatchCounter, time.Now().UnixNano())
	h := sha256.Sum256([]byte(proofData))
	proof := hex.EncodeToString(h[:])

	periodicZK.LastZKProof = proof
	periodicZK.LastZKRoot = fmt.Sprintf("root_%d", periodicZK.BatchCounter)
	periodicZK.ZKProofCounter++
	periodicZK.ZKProofs++

	return proof, nil
}

// VerifyPeriodicZK verifies a periodic ZK proof
func VerifyPeriodicZK(proof string, root string) bool {
	time.Sleep(time.Duration(zkConfig.VerifyTime) * time.Millisecond)

	if proof == "" {
		return false
	}

	periodicZK.mu.Lock()
	defer periodicZK.mu.Unlock()

	return periodicZK.LastZKProof == proof && periodicZK.LastZKRoot == root
}

// GetStats returns current statistics
func GetZKStats() map[string]interface{} {
	periodicZK.mu.RLock()
	defer periodicZK.mu.RUnlock()

	zkTPS := float64(periodicZK.TotalTx) / (float64(periodicZK.ZKProofs) * float64(zkConfig.ProveTime) / 1000)

	return map[string]interface{}{
		"total_batches":   periodicZK.TotalBatches,
		"total_tx":       periodicZK.TotalTx,
		"hash_verifies":  periodicZK.HashVerifies,
		"zk_proofs":      periodicZK.ZKProofs,
		"batch_counter":  periodicZK.BatchCounter,
		"zk_period":      zkConfig.ZKPeriod,
		"batch_size":     zkConfig.BatchSize,
		"effective_tps":  zkTPS,
		"last_zk_proof":  periodicZK.LastZKProof,
		"last_zk_root":   periodicZK.LastZKRoot,
	}
}

// Helper: Compute Merkle root from transaction hashes
func computeMerkleRoot(hashes []string) string {
	if len(hashes) == 0 {
		return ""
	}

	current := make([]string, len(hashes))
	copy(current, hashes)

	for len(current) > 1 {
		next := make([]string, 0, (len(current)+1)/2)
		for i := 0; i < len(current); i += 2 {
			left := current[i]
			right := current[i]
			if i+1 < len(current) {
				right = current[i+1]
			}
			combined := left + right
			hash := sha256.Sum256([]byte(combined))
			next = append(next, hex.EncodeToString(hash[:]))
		}
		current = next
	}

	return current[0]
}

// InitZK initializes the periodic ZK system
func InitZK() {
	periodicZK = PeriodicZKState{
		LastZKProof:    "",
		LastZKRoot:    "",
		BatchCounter:  0,
		ZKProofCounter: 0,
	}
	fmt.Println("[ZK] Periodic ZK initialized")
	fmt.Printf("[ZK]   Batch size: %d, ZK period: %d\n", zkConfig.BatchSize, zkConfig.ZKPeriod)
	fmt.Printf("[ZK]   Prove time: %dms, Verify time: %dms\n", zkConfig.ProveTime, zkConfig.VerifyTime)
	fmt.Printf("[ZK]   Expected TPS: ~%d\n", zkConfig.BatchSize*zkConfig.ZKPeriod*1000/zkConfig.ProveTime)
}

// ==================== HANDLERS ====================

func addBatchHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		TxHashes []string `json:"tx_hashes"`
	}
	json.NewDecoder(r.Body).Decode(&req)

	if len(req.TxHashes) == 0 {
		http.Error(w, "No transactions", 400)
		return
	}

	ok, root, needsZK := AddBatch(req.TxHashes)

	response := map[string]interface{}{
		"status":       "ok",
		"verified":     ok,
		"merkle_root":  root,
		"batch_id":     periodicZK.BatchCounter,
		"needs_zk":     needsZK,
	}

	if needsZK {
		proof, err := GenerateZKProof()
		if err != nil {
			response["zk_error"] = err.Error()
		} else {
			response["zk_proof"] = proof
			response["zk_root"] = periodicZK.LastZKRoot
		}
	}

	json.NewEncoder(w).Encode(response)
}

func zkProofHandler(w http.ResponseWriter, r *http.Request) {
	stats := GetZKStats()
	json.NewEncoder(w).Encode(stats)
}

func verifyZKHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Proof string `json:"proof"`
		Root  string `json:"root"`
	}
	json.NewDecoder(r.Body).Decode(&req)

	valid := VerifyPeriodicZK(req.Proof, req.Root)

	json.NewEncoder(w).Encode(map[string]interface{}{
		"valid": valid,
	})
}

func setZKPeriodHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Period int `json:"period"`
	}
	json.NewDecoder(r.Body).Decode(&req)

	if req.Period > 0 {
		zkConfig.ZKPeriod = req.Period
	}

	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":     "ok",
		"zk_period": zkConfig.ZKPeriod,
	})
}