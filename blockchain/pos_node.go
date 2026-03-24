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
	"sort"
	"sync"
	"time"
)

// ==================== CONSTANTS ====================
const (
	BlockTime       = 3 * time.Second
	EpochLength     = 100
	MinStake        = 1000.0
	RewardPerBlock  = 10.0
	RewardPerEpoch  = 100.0
	DelegationShare = 0.80
	Commission      = 0.05
)

// ==================== HASH ====================
func doubleSHA256(data string) string {
	h := sha256.Sum256([]byte(data))
	return hex.EncodeToString(h[:])
}

func randomBytes(n int) []byte {
	b := make([]byte, n)
	rand.Read(b)
	return b
}

// ==================== PROOF OF STAKE ====================
type Validator struct {
	Address     string  `json:"address"`
	Stake       float64 `json:"stake"`
	Delegated   float64 `json:"delegated"`
	TotalStake  float64 `json:"total_stake"`
	Delegators  map[string]DelegatorInfo `json:"delegators"`
	Commission  float64 `json:"commission"`
	Rewards     float64 `json:"rewards"`
	BlocksProduced int `json:"blocks_produced"`
	Active      bool   `json:"active"`
}

type DelegatorInfo struct {
	Address  string  `json:"address"`
	Amount   float64 `json:"amount"`
	Rewards  float64 `json:"rewards"`
}

type ValidatorSet struct {
	mu         sync.RWMutex
	validators map[string]*Validator
	epoch      int
}

func NewValidatorSet() *ValidatorSet {
	return &ValidatorSet{
		validators: make(map[string]*Validator),
		epoch:      1,
	}
}

func (vs *ValidatorSet) Register(addr string, stake float64) error {
	if stake < MinStake {
		return fmt.Errorf("min stake is %.0f", MinStake)
	}
	vs.mu.Lock()
	defer vs.mu.Unlock()
	if vs.validators[addr] != nil {
		return fmt.Errorf("already validator")
	}
	vs.validators[addr] = &Validator{
		Address:    addr,
		Stake:      stake,
		TotalStake: stake,
		Delegators: make(map[string]DelegatorInfo),
		Commission: Commission,
		Active:    true,
	}
	return nil
}

func (vs *ValidatorSet) Delegate(valAddr, delAddr string, amount float64) error {
	vs.mu.Lock()
	defer vs.mu.Unlock()
	v := vs.validators[valAddr]
	if v == nil {
		return fmt.Errorf("validator not found")
	}
	if d, ok := v.Delegators[delAddr]; ok {
		d.Amount += amount
		v.Delegators[delAddr] = d
	} else {
		v.Delegators[delAddr] = DelegatorInfo{Address: delAddr, Amount: amount}
	}
	v.Delegated += amount
	v.TotalStake += amount
	return nil
}

func (vs *ValidatorSet) SelectProposer(seed string) string {
	vs.mu.RLock()
	defer vs.mu.RUnlock()

	active := make([]*Validator, 0)
	for _, v := range vs.validators {
		if v.Active {
			active = append(active, v)
		}
	}
	if len(active) == 0 {
		return ""
	}
	sort.Slice(active, func(i, j int) bool {
		return active[i].TotalStake > active[j].TotalStake
	})

	seedHash := sha256.Sum256([]byte(seed))
	r := int(seedHash[0]) % 10000
	total := 0.0
	for _, v := range active {
		total += v.TotalStake
	}
	threshold := float64(r) / 10000.0 * total

	cum := 0.0
	for _, v := range active {
		cum += v.TotalStake
		if cum >= threshold {
			return v.Address
		}
	}
	return active[0].Address
}

func (vs *ValidatorSet) DistributeBlockReward(addr string) {
	vs.mu.Lock()
	defer vs.mu.Unlock()
	if v := vs.validators[addr]; v != nil {
		v.Rewards += RewardPerBlock
		v.BlocksProduced++
	}
}

func (vs *ValidatorSet) DistributeEpochRewards() {
	vs.mu.Lock()
	defer vs.mu.Unlock()
	for _, v := range vs.validators {
		if !v.Active {
			continue
		}
		// Validator share
		v.Rewards += RewardPerEpoch * (1 - v.Commission)
		// Delegators share
		if v.Delegated > 0 {
			pool := RewardPerEpoch * DelegationShare
			for addr, d := range v.Delegators {
				share := d.Amount / v.Delegated
				d.Rewards += pool * share
				v.Delegators[addr] = d
			}
		}
	}
}

func (vs *ValidatorSet) Claim(addr string) float64 {
	vs.mu.Lock()
	defer vs.mu.Unlock()
	if v := vs.validators[addr]; v != nil {
		r := v.Rewards
		v.Rewards = 0
		return r
	}
	return 0
}

func (vs *ValidatorSet) GetAll() []Validator {
	vs.mu.RLock()
	defer vs.mu.RUnlock()
	list := make([]Validator, 0, len(vs.validators))
	for _, v := range vs.validators {
		list = append(list, *v)
	}
	sort.Slice(list, func(i, j int) bool {
		return list[i].TotalStake > list[j].TotalStake
	})
	return list
}

func (vs *ValidatorSet) NextEpoch() {
	vs.mu.Lock()
	vs.epoch++
	vs.mu.Unlock()
}

func (vs *ValidatorSet) GetEpoch() int {
	vs.mu.RLock()
	defer vs.mu.RUnlock()
	return vs.epoch
}

var validators *ValidatorSet

// ==================== BLOCKCHAIN ====================
type Block struct {
	Height       int         `json:"height"`
	PreviousHash string      `json:"previous_hash"`
	Timestamp    float64     `json:"timestamp"`
	Proposer     string      `json:"proposer"`
	Epoch        int         `json:"epoch"`
	Transactions []Tx        `json:"transactions"`
	Hash         string      `json:"hash"`
}

type Tx struct {
	Type      string  `json:"tx_type"`
	Sender    string  `json:"sender"`
	Recipient string  `json:"recipient"`
	Amount    float64 `json:"amount"`
	Fee       float64 `json:"fee"`
	Hash      string  `json:"hash"`
}

type Chain struct {
	mu          sync.RWMutex
	blocks      []Block
	pendingTxs  []Tx
	balances    map[string]float64
	validator   string
	shardID     int
	txCount     int
}

var chain Chain

func initChain(shard int, valAddr string) {
	chain = Chain{
		blocks:     []Block{{Height: 0, Hash: "genesis"}},
		pendingTxs: make([]Tx, 0, 50000),
		balances:  make(map[string]float64),
		validator:  valAddr,
		shardID:    shard,
	}
	validators = NewValidatorSet()
	validators.Register(valAddr, 10000)
	chain.balances[valAddr] = 100_000_000
}

func (c *Chain) addTx(tx Tx) bool {
	total := tx.Amount + tx.Fee
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.balances[tx.Sender] < total {
		return false
	}
	c.balances[tx.Sender] -= total
	c.balances[tx.Recipient] += tx.Amount
	c.balances[c.validator] += tx.Fee
	c.pendingTxs = append(c.pendingTxs, tx)
	c.txCount++
	return true
}

func (c *Chain) produceBlock() Block {
	c.mu.Lock()
	prev := c.blocks[len(c.blocks)-1]
	height := prev.Height + 1
	epoch := validators.GetEpoch()

	// Check epoch transition
	if height%EpochLength == 0 {
		validators.NextEpoch()
		validators.DistributeEpochRewards()
	}

	// Select proposer
	seed := fmt.Sprintf("%d:%s:%d", height, prev.Hash, time.Now().UnixNano())
	proposer := validators.SelectProposer(seed)

	// Only proposer can create blocks
	if proposer != c.validator {
		c.mu.Unlock()
		time.Sleep(BlockTime / 2)
		return Block{}
	}

	// Take txs
	txs := c.pendingTxs
	if len(txs) > 1000 {
		txs = txs[:1000]
	}
	c.pendingTxs = c.pendingTxs[len(txs):]

	block := Block{
		Height:       height,
		PreviousHash: prev.Hash,
		Timestamp:    float64(time.Now().Unix()),
		Proposer:     c.validator,
		Epoch:        epoch,
		Transactions: txs,
		Hash:         doubleSHA256(fmt.Sprintf("%d:%s:%v", height, prev.Hash, txs)),
	}
	c.blocks = append(c.blocks, block)

	validators.DistributeBlockReward(c.validator)
	c.mu.Unlock()

	log.Printf("📦 Block #%d by %s... (%d txs)", height, c.validator[:16], len(txs))
	return block
}

// ==================== HANDLERS ====================
func health(w http.ResponseWriter, r *http.Request) {
	chain.mu.RLock()
	h := len(chain.blocks)
	chain.mu.RUnlock()

	seed := fmt.Sprintf("%d", h)
	proposer := validators.SelectProposer(seed)

	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":       "ok",
		"shard":        chain.shardID,
		"height":       h,
		"epoch":        validators.GetEpoch(),
		"pending":      len(chain.pendingTxs),
		"validators":   len(validators.GetAll()),
		"proposer":     proposer[:16],
		"is_proposer": proposer == chain.validator,
	})
}

func stake(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Address string  `json:"address"`
		Amount  float64 `json:"amount"`
	}
	json.NewDecoder(r.Body).Decode(&req)

	chain.mu.RLock()
	bal := chain.balances[req.Address]
	chain.mu.RUnlock()

	if bal < req.Amount {
		http.Error(w, "insufficient balance", 400)
		return
	}

	if err := validators.Register(req.Address, req.Amount); err != nil {
		http.Error(w, err.Error(), 400)
		return
	}

	chain.mu.Lock()
	chain.balances[req.Address] -= req.Amount
	chain.mu.Unlock()

	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":   "validator_registered",
		"stake":    req.Amount,
		"validators": len(validators.GetAll()),
	})
}

func delegate(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Validator string  `json:"validator"`
		Delegator string  `json:"delegator"`
		Amount    float64 `json:"amount"`
	}
	json.NewDecoder(r.Body).Decode(&req)

	chain.mu.RLock()
	bal := chain.balances[req.Delegator]
	chain.mu.RUnlock()

	if bal < req.Amount {
		http.Error(w, "insufficient balance", 400)
		return
	}

	if err := validators.Delegate(req.Validator, req.Delegator, req.Amount); err != nil {
		http.Error(w, err.Error(), 400)
		return
	}

	chain.mu.Lock()
	chain.balances[req.Delegator] -= req.Amount
	chain.mu.Unlock()

	json.NewEncoder(w).Encode(map[string]interface{}{
		"status": "delegated",
		"amount": req.Amount,
	})
}

func claim(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Address string `json:"address"`
	}
	json.NewDecoder(r.Body).Decode(&req)

	rewards := validators.Claim(req.Address)
	chain.mu.Lock()
	chain.balances[req.Address] += rewards
	chain.mu.Unlock()

	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":  "claimed",
		"rewards": rewards,
	})
}

func listValidators(w http.ResponseWriter, r *http.Request) {
	list := validators.GetAll()
	json.NewEncoder(w).Encode(map[string]interface{}{
		"validators": list,
		"epoch":      validators.GetEpoch(),
	})
}

func createWallet(w http.ResponseWriter, r *http.Request) {
	addr := doubleSHA256(hex.EncodeToString(randomBytes(32)))

	chain.mu.Lock()
	if chain.balances[addr] == 0 {
		chain.balances[addr] = 10000
	}
	chain.mu.Unlock()

	json.NewEncoder(w).Encode(map[string]interface{}{
		"address": addr,
	})
}

func broadcast(w http.ResponseWriter, r *http.Request) {
	var tx Tx
	json.NewDecoder(r.Body).Decode(&tx)
	tx.Type = "TRANSFER"
	tx.Hash = doubleSHA256(fmt.Sprintf("%s:%s:%f", tx.Sender, tx.Recipient, tx.Amount))

	ok := chain.addTx(tx)
	if !ok {
		http.Error(w, "invalid tx", 400)
		return
	}

	json.NewEncoder(w).Encode(map[string]interface{}{
		"status": "pending",
		"hash":   tx.Hash,
	})
}

func balance(w http.ResponseWriter, r *http.Request) {
	addr := r.URL.Path[len("/balance/"):]
	chain.mu.RLock()
	bal := chain.balances[addr]
	chain.mu.RUnlock()
	json.NewEncoder(w).Encode(map[string]interface{}{"address": addr, "balance": bal})
}

// ==================== MAIN ====================
func main() {
	port := flag.Int("port", 5001, "Port")
	shard := flag.Int("shard", 0, "Shard ID")
	flag.Parse()

	valAddr := "validator_" + doubleSHA256(fmt.Sprintf("shard%d", *shard))[:16]
	initChain(*shard, valAddr)

	http.HandleFunc("/health", health)
	http.HandleFunc("/validators", listValidators)
	http.HandleFunc("/pos/stake", stake)
	http.HandleFunc("/pos/delegate", delegate)
	http.HandleFunc("/pos/claim", claim)
	http.HandleFunc("/wallet/create", createWallet)
	http.HandleFunc("/broadcast", broadcast)
	http.HandleFunc("/balance/", balance)

	go func() {
		for {
			chain.produceBlock()
		}
	}()

	fmt.Printf("\n⚡ Wrath of Cali - Proof of Stake\n")
	fmt.Printf("   Shard: %d | Port: %d\n", *shard, *port)
	fmt.Printf("   Validator: %s\n", valAddr)
	fmt.Printf("   Block Time: %v | Epoch: %d blocks\n", BlockTime, EpochLength)
	fmt.Printf("   Min Stake: %.0f | Reward/Block: %.0f\n", MinStake, RewardPerBlock)

	log.Fatal(http.ListenAndServe(fmt.Sprintf(":%d", *port), nil))
}