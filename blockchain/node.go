package main

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"
)

// Configuration
const (
	BlockTime            = time.Second
	MaxBatchesPerBlock  = 10000
	MaxTxsPerBatch      = 50000
	PendingTxCap        = 100000
	MinStake      float64 = 1000
)

// Hash functions
func sha256Hash(data string) string {
	h := sha256.Sum256([]byte(data))
	return hex.EncodeToString(h[:])
}

func doubleSHA256(data string) string {
	return sha256Hash(sha256Hash(data))
}

// Data structures
type Transaction struct {
	Type      string  `json:"tx_type"`
	Sender    string  `json:"sender"`
	Recipient string  `json:"recipient"`
	Amount    float64 `json:"amount"`
	Fee       float64 `json:"fee"`
	Timestamp float64 `json:"timestamp"`
	Signature string  `json:"signature"`
	Hash      string  `json:"hash"`
}

type Batch struct {
	Validator   string   `json:"validator"`
	Transactions []string `json:"transactions"`
	BatchHash  string   `json:"batch_hash"`
	Timestamp  float64  `json:"timestamp"`
	Signature  string   `json:"signature"`
}

type Block struct {
	Height       int           `json:"height"`
	PreviousHash string        `json:"previous_hash"`
	Timestamp    float64       `json:"timestamp"`
	Validator    string        `json:"validator"`
	BatchHashes  []string      `json:"batch_hashes"`
	Transactions []Transaction `json:"transactions"`
	MerkleRoot   string        `json:"merkle_root"`
	Hash         string        `json:"hash"`
}

// Blockchain state
type State struct {
	mu         sync.RWMutex
	Balances   map[string]float64 `json:"balances"`
	Stakes     map[string]float64 `json:"stakes"`
	Validators map[string]ValidatorInfo `json:"validators"`
}

type ValidatorInfo struct {
	Address          string  `json:"address"`
	Staked           float64 `json:"staked"`
	Joined           float64 `json:"joined"`
	BatchesSubmitted int     `json:"batches_submitted"`
}

// Node state
type Node struct {
	mu                 sync.RWMutex
	chain              []Block
	state              State
	pendingTxs         []Transaction
	pendingBatches     []Batch
	validatorAddr      string
	shardID            int
	txCounter          int
	blockCounter       int
}

var node Node

// Initialize
func initGenesis(shardID int) {
	node.shardID = shardID
	node.chain = make([]Block, 0)
	node.state = State{
		Balances:   make(map[string]float64),
		Stakes:     make(map[string]float64),
		Validators: make(map[string]ValidatorInfo),
	}
	node.pendingTxs = make([]Transaction, 0, PendingTxCap)
	node.pendingBatches = make([]Batch, 0, 1000)
	
	// Generate validator address (simplified)
	node.validatorAddr = doubleSHA256(fmt.Sprintf("validator_%d_%d", shardID, time.Now().Unix()))
	
	// Fund validator
	node.state.Balances[node.validatorAddr] = 100_000_000
	
	// Create genesis block
	genesis := Block{
		Height:       0,
		PreviousHash: "0000000000000000000000000000000000000000000000000000000000000000",
		Timestamp:    0,
		Validator:    node.validatorAddr,
		Hash:         doubleSHA256("genesis"),
	}
	node.chain = append(node.chain, genesis)
	
	log.Printf("🔷 Shard %d initialized: %s...", shardID, node.validatorAddr[:16])
}

// Apply transaction
func (n *Node) applyTransaction(tx Transaction) bool {
	if tx.Type == "TRANSFER" {
		total := tx.Amount + tx.Fee
		if n.state.Balances[tx.Sender] >= total {
			n.state.Balances[tx.Sender] -= total
			n.state.Balances[tx.Recipient] += tx.Amount
			return true
		}
	} else if tx.Type == "STAKE" {
		if n.state.Balances[tx.Sender] >= tx.Amount {
			n.state.Balances[tx.Sender] -= tx.Amount
			n.state.Stakes[tx.Sender] += tx.Amount
			if _, ok := n.state.Validators[tx.Sender]; !ok {
				n.state.Validators[tx.Sender] = ValidatorInfo{
					Address: tx.Sender,
					Staked: tx.Amount,
					Joined: float64(time.Now().Unix()),
				}
			}
			return true
		}
	}
	return true // Genesis txs
}

// Create block
func (n *Node) createBlock() *Block {
	n.mu.Lock()
	defer n.mu.Unlock()
	
	if len(n.pendingBatches) == 0 && len(n.pendingTxs) == 0 {
		return nil
	}
	
	prevBlock := n.chain[len(n.chain)-1]
	height := prevBlock.Height + 1
	n.blockCounter++
	
	// Take batches
	batchesToInclude := n.pendingBatches
	if len(batchesToInclude) > MaxBatchesPerBlock {
		batchesToInclude = batchesToInclude[:MaxBatchesPerBlock]
	}
	
	batchHashes := make([]string, len(batchesToInclude))
	for i, b := range batchesToInclude {
		batchHashes[i] = b.BatchHash
	}
	
	// Collect transactions
	allTxs := make([]Transaction, 0)
	txHashSet := make(map[string]bool)
	
	for _, batch := range batchesToInclude {
		for _, txHash := range batch.Transactions {
			if !txHashSet[txHash] {
				for _, tx := range n.pendingTxs {
					if tx.Hash == txHash && !txHashSet[txHash] {
						allTxs = append(allTxs, tx)
						txHashSet[txHash] = true
						break
					}
				}
			}
		}
	}
	
	// Merkle root
	merkle := ""
	if len(allTxs) > 0 {
		merkle = doubleSHA256(fmt.Sprintf("%v", allTxs))
	}
	
	block := Block{
		Height:       height,
		PreviousHash: prevBlock.Hash,
		Timestamp:    float64(time.Now().Unix()),
		Validator:    n.validatorAddr,
		BatchHashes:  batchHashes,
		Transactions: allTxs,
		MerkleRoot:   merkle,
		Hash:         doubleSHA256(fmt.Sprintf("%d:%s:%f:%s", height, prevBlock.Hash, time.Now().Unix(), merkle)),
	}
	
	// Cleanup
	n.pendingBatches = n.pendingBatches[len(batchesToInclude):]
	usedTxs := make(map[string]bool)
	for _, tx := range allTxs {
		usedTxs[tx.Hash] = true
	}
	
	remainingTxs := make([]Transaction, 0)
	for _, tx := range n.pendingTxs {
		if !usedTxs[tx.Hash] {
			remainingTxs = append(remainingTxs, tx)
		}
	}
	n.pendingTxs = remainingTxs
	
	// Apply transactions
	for _, tx := range allTxs {
		n.applyTransaction(tx)
	}
	
	n.chain = append(n.chain, block)
	return &block
}

// Block producer loop
func blockProducer() {
	for {
		time.Sleep(BlockTime)
		block := node.createBlock()
		if block != nil {
			log.Printf("📦 Shard %d Block #%d (%d txs)", node.shardID, block.Height, len(block.Transactions))
		}
	}
}

// HTTP Handlers
func healthHandler(w http.ResponseWriter, r *http.Request) {
	node.mu.RLock()
	defer node.mu.RUnlock()
	
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":         "ok",
		"shard":          node.shardID,
		"height":          len(node.chain),
		"pending_txs":    len(node.pendingTxs),
		"pending_batches": len(node.pendingBatches),
	})
}

func getBlockHandler(w http.ResponseWriter, r *http.Request) {
	var height int
	fmt.Sscanf(r.URL.Path[len("/block/"):], "%d", &height)
	
	node.mu.RLock()
	defer node.mu.RUnlock()
	
	if height >= 0 && height < len(node.chain) {
		json.NewEncoder(w).Encode(node.chain[height])
	} else {
		http.Error(w, "Block not found", 404)
	}
}

func getBalanceHandler(w http.ResponseWriter, r *http.Request) {
	addr := r.URL.Path[len("/balance/"):]
	
	node.mu.RLock()
	balance := node.state.Balances[addr]
	staked := node.state.Stakes[addr]
	node.mu.RUnlock()
	
	json.NewEncoder(w).Encode(map[string]interface{}{
		"address": addr,
		"balance": balance,
		"staked":  staked,
		"total":   balance + staked,
	})
}

func broadcastHandler(w http.ResponseWriter, r *http.Request) {
	var tx Transaction
	if err := json.NewDecoder(r.Body).Decode(&tx); err != nil {
		http.Error(w, err.Error(), 400)
		return
	}
	
	node.mu.RLock()
	balance := node.state.Balances[tx.Sender]
	node.mu.RUnlock()
	
	if balance < tx.Amount+tx.Fee {
		http.Error(w, "Insufficient balance", 400)
		return
	}
	
	tx.Timestamp = float64(time.Now().Unix())
	tx.Hash = doubleSHA256(fmt.Sprintf("%s:%s:%f:%f", tx.Type, tx.Sender, tx.Amount, tx.Timestamp))
	
	node.mu.Lock()
	if len(node.pendingTxs) < PendingTxCap {
		node.pendingTxs = append(node.pendingTxs, tx)
		node.txCounter++
	}
	node.mu.Unlock()
	
	json.NewEncoder(w).Encode(map[string]string{"status": "accepted", "hash": tx.Hash})
}

func batchHandler(w http.ResponseWriter, r *http.Request) {
	var batch Batch
	if err := json.NewDecoder(r.Body).Decode(&batch); err != nil {
		http.Error(w, err.Error(), 400)
		return
	}
	
	node.mu.RLock()
	staked := node.state.Stakes[batch.Validator]
	node.mu.RUnlock()
	
	if staked < MinStake {
		http.Error(w, "Validator not staked enough", 400)
		return
	}
	
	batch.Timestamp = float64(time.Now().Unix())
	batch.BatchHash = doubleSHA256(fmt.Sprintf("%s:%v:%f", batch.Validator, batch.Transactions, batch.Timestamp))
	
	node.mu.Lock()
	node.pendingBatches = append(node.pendingBatches, batch)
	
	if v, ok := node.state.Validators[batch.Validator]; ok {
		v.BatchesSubmitted++
		node.state.Validators[batch.Validator] = v
	}
	node.mu.Unlock()
	
	json.NewEncoder(w).Encode(map[string]string{"status": "accepted", "batch_hash": batch.BatchHash})
}

func createWalletHandler(w http.ResponseWriter, r *http.Request) {
	// Generate simple wallet
	addr := doubleSHA256(fmt.Sprintf("wallet_%d", time.Now().UnixNano()))[:40]
	priv := doubleSHA256(fmt.Sprintf("priv_%d", time.Now().UnixNano()))
	
	node.mu.Lock()
	node.state.Balances[addr] = 0
	node.mu.Unlock()
	
	json.NewEncoder(w).Encode(map[string]string{
		"address":    addr,
		"private_key": priv,
	})
}

func transferHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Sender    string  `json:"sender"`
		Recipient string  `json:"recipient"`
		Amount    float64 `json:"amount"`
		Fee       float64 `json:"fee"`
		PrivateKey string `json:"private_key"`
	}
	
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), 400)
		return
	}
	
	if req.Fee == 0 {
		req.Fee = 0.01
	}
	
	node.mu.RLock()
	balance := node.state.Balances[req.Sender]
	node.mu.RUnlock()
	
	if balance < req.Amount+req.Fee {
		http.Error(w, "Insufficient balance", 400)
		return
	}
	
	tx := Transaction{
		Type:      "TRANSFER",
		Sender:    req.Sender,
		Recipient: req.Recipient,
		Amount:    req.Amount,
		Fee:       req.Fee,
		Timestamp: float64(time.Now().Unix()),
	}
	tx.Hash = doubleSHA256(fmt.Sprintf("%s:%s:%f:%f", tx.Type, tx.Sender, tx.Amount, tx.Timestamp))
	
	node.mu.Lock()
	if len(node.pendingTxs) < PendingTxCap {
		node.pendingTxs = append(node.pendingTxs, tx)
		node.txCounter++
	}
	node.mu.Unlock()
	
	json.NewEncoder(w).Encode(map[string]interface{}{"status": "accepted", "transaction": tx})
}

func faucetHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Address string `json:"address"`
	}
	
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), 400)
		return
	}
	
	node.mu.Lock()
	defer node.mu.Unlock()
	
	if node.state.Balances[node.validatorAddr] >= 10000 {
		node.state.Balances[node.validatorAddr] -= 10000
		node.state.Balances[req.Address] += 10000
		json.NewEncoder(w).Encode(map[string]interface{}{"status": "funded", "amount": 10000})
	} else {
		http.Error(w, "Faucet empty", 500)
	}
}

func shardStatusHandler(w http.ResponseWriter, r *http.Request) {
	node.mu.RLock()
	defer node.mu.RUnlock()
	
	json.NewEncoder(w).Encode(map[string]interface{}{
		"shard_id":            node.shardID,
		"height":              len(node.chain),
		"pending_txs":        len(node.pendingTxs),
		"pending_batches":    len(node.pendingBatches),
		"validators":         len(node.state.Validators),
		"total_txs_processed": node.txCounter,
		"total_blocks":       node.blockCounter,
	})
}

// Batch broadcast - accept multiple transactions at once
func batchBroadcastHandler(w http.ResponseWriter, r *http.Request) {
	var txs []Transaction
	if err := json.NewDecoder(r.Body).Decode(&txs); err != nil {
		http.Error(w, err.Error(), 400)
		return
	}
	
	accepted := []string{}
	
	node.mu.Lock()
	defer node.mu.Unlock()
	
	for i := range txs {
		tx := &txs[i]
		tx.Timestamp = float64(time.Now().Unix())
		
		// Balance check
		if node.state.Balances[tx.Sender] >= tx.Amount+tx.Fee {
			node.state.Balances[tx.Sender] -= tx.Amount + tx.Fee
			node.state.Balances[tx.Recipient] += tx.Amount
			
			tx.Hash = doubleSHA256(fmt.Sprintf("%s:%s:%f:%f", tx.Type, tx.Sender, tx.Amount, tx.Timestamp))
			
			if len(node.pendingTxs) < PendingTxCap {
				node.pendingTxs = append(node.pendingTxs, *tx)
				node.txCounter++
				accepted = append(accepted, tx.Hash)
			}
		}
	}
	
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":   "accepted",
		"count":    len(accepted),
		"hashes":   accepted,
	})
}

// ==================== ZK PRIVACY ====================

func initZK() {
	// Initialize ZK params
}

type ZKProof struct {
	Commitment    string `json:"commitment"`
	Random        string `json:"random"`
	Proof         string `json:"proof"`
	NullifierHash string `json:"nullifier_hash"`
	MerkleRoot    string `json:"merkle_root"`
}

type ShieldedPool struct {
	mu          sync.RWMutex
	Commitments map[string]float64
	Nullifiers  map[string]bool
	MerkleTree  []string
}

var shieldedPool ShieldedPool

func init() {
	shieldedPool.Commitments = make(map[string]float64)
	shieldedPool.Nullifiers = make(map[string]bool)
	shieldedPool.MerkleTree = make([]string, 0)
}

func shieldHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Address string  `json:"address"`
		Amount  float64 `json:"amount"`
	}
	json.NewDecoder(r.Body).Decode(&req)

	// Generate commitment (simplified Pedersen)
	random := make([]byte, 32)
	rand.Read(random)
	commitment := doubleSHA256(fmt.Sprintf("%f:%s", req.Amount, string(random)))

	shieldedPool.mu.Lock()
	shieldedPool.Commitments[commitment] = req.Amount
	shieldedPool.MerkleTree = append(shieldedPool.MerkleTree, commitment)
	merkleRoot := shieldedPool.MerkleTree[len(shieldedPool.MerkleTree)-1]
	nullifierHash := doubleSHA256(fmt.Sprintf("%s:%s", req.Address, string(random)))
	shieldedPool.mu.Unlock()

	proof := ZKProof{
		Commitment:    commitment,
		Random:        hex.EncodeToString(random),
		Proof:         doubleSHA256(fmt.Sprintf("%s:%s", commitment, nullifierHash)),
		NullifierHash: nullifierHash,
		MerkleRoot:    merkleRoot,
	}

	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":      "shielded",
		"commitment":  commitment,
		"merkle_root": merkleRoot,
		"proof":       proof,
	})
}

func unshieldHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Commitment string  `json:"commitment"`
		Recipient  string  `json:"recipient"`
		Proof      ZKProof `json:"proof"`
	}
	json.NewDecoder(r.Body).Decode(&req)

	shieldedPool.mu.RLock()
	_, exists := shieldedPool.Commitments[req.Commitment]
	nullifierUsed := shieldedPool.Nullifiers[req.Proof.NullifierHash]
	shieldedPool.mu.RUnlock()

	if !exists {
		http.Error(w, "Invalid commitment", 400)
		return
	}
	if nullifierUsed {
		http.Error(w, "Double spend detected", 400)
		return
	}

	shieldedPool.mu.Lock()
	shieldedPool.Nullifiers[req.Proof.NullifierHash] = true
	amount := shieldedPool.Commitments[req.Commitment]
	delete(shieldedPool.Commitments, req.Commitment)
	shieldedPool.mu.Unlock()

	node.state.Balances[req.Recipient] += amount

	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":    "unshielded",
		"recipient": req.Recipient,
		"amount":    amount,
	})
}

func shieldedTransferHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Sender        string  `json:"sender"`
		Recipient     string  `json:"recipient"`
		InputCommit   string  `json:"input_commitment"`
		OutputCommit  string  `json:"output_commitment"`
		Fee           float64 `json:"fee"`
		Proof         ZKProof `json:"proof"`
	}
	json.NewDecoder(r.Body).Decode(&req)

	shieldedPool.mu.RLock()
	_, inputExists := shieldedPool.Commitments[req.InputCommit]
	nullifierUsed := shieldedPool.Nullifiers[req.Proof.NullifierHash]
	shieldedPool.mu.RUnlock()

	if !inputExists {
		http.Error(w, "Invalid input", 400)
		return
	}
	if nullifierUsed {
		http.Error(w, "Double spend", 400)
		return
	}

	shieldedPool.mu.Lock()
	shieldedPool.Nullifiers[req.Proof.NullifierHash] = true
	delete(shieldedPool.Commitments, req.InputCommit)
	shieldedPool.Commitments[req.OutputCommit] = shieldedPool.Commitments[req.InputCommit] - req.Fee
	shieldedPool.MerkleTree = append(shieldedPool.MerkleTree, req.OutputCommit)
	shieldedPool.mu.Unlock()

	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":        "shielded_transfer",
		"merkle_root":   shieldedPool.MerkleTree[len(shieldedPool.MerkleTree)-1],
		"amount_hidden": true,
	})
}

func shieldedPoolHandler(w http.ResponseWriter, r *http.Request) {
	shieldedPool.mu.RLock()
	defer shieldedPool.mu.RUnlock()
	json.NewEncoder(w).Encode(map[string]interface{}{
		"pool_size":  len(shieldedPool.Commitments),
		"nullifiers": len(shieldedPool.Nullifiers),
	})
}

func main() {
	port := flag.Int("port", 5001, "Port to listen on")
	shard := flag.Int("shard", 0, "Shard ID")
	flag.Parse()
	
	initGenesis(*shard)
	
	// Routes
	http.HandleFunc("/health", healthHandler)
	http.HandleFunc("/block/", getBlockHandler)
	http.HandleFunc("/balance/", getBalanceHandler)
	http.HandleFunc("/broadcast", broadcastHandler)
	http.HandleFunc("/broadcast/batch", batchBroadcastHandler)
	http.HandleFunc("/batch", batchHandler)
	http.HandleFunc("/wallet/create", createWalletHandler)
	http.HandleFunc("/wallet/transfer", transferHandler)
	http.HandleFunc("/faucet", faucetHandler)
	http.HandleFunc("/shard/status", shardStatusHandler)
	
	// ZK Privacy Routes
	http.HandleFunc("/zk/shield", shieldHandler)
	http.HandleFunc("/zk/unshield", unshieldHandler)
	http.HandleFunc("/zk/transfer", shieldedTransferHandler)
	http.HandleFunc("/zk/pool", shieldedPoolHandler)
	
	// Periodic ZK Routes (Hybrid Batching)
	InitZK() // Initialize periodic ZK
	http.HandleFunc("/zk/batch", addBatchHandler)
	http.HandleFunc("/zk/proof", zkProofHandler)
	http.HandleFunc("/zk/verify", verifyZKHandler)
	http.HandleFunc("/zk/period", setZKPeriodHandler)
	
	// Start block producer
	go blockProducer()
	
	fmt.Printf("\n⚡ Wrath of Cali - Go Node\n")
	fmt.Printf("   Shard: %d\n", *shard)
	fmt.Printf("   Port: %d\n", *port)
	fmt.Printf("   Max batches/block: %d\n", MaxBatchesPerBlock)
	fmt.Printf("   Max pending txs: %d\n\n", PendingTxCap)
	
	log.Fatal(http.ListenAndServe(fmt.Sprintf(":%d", *port), nil))
}