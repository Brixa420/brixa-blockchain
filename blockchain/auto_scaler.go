package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"sync"
	"time"
)

// ==================== HASH FUNCTIONS ====================

func sha256Hash(data string) string {
	h := sha256.Sum256([]byte(data))
	return hex.EncodeToString(h[:])
}

func doubleSHA256(data string) string {
	return sha256Hash(sha256Hash(data))
}

// ==================== AUTO-SCALING ORCHESTRATOR ====================

type Orchestrator struct {
	mu           sync.RWMutex
	shards       map[int]*ShardInfo
	routerAddr   string
	portStart    int
	maxShards    int
	tpsThreshold float64
	tpsHistory   []float64
	ticker       *time.Ticker
	metricsPort  int
}

type ShardInfo struct {
	ID         int     `json:"id"`
	Port       int     `json:"port"`
	PID        int     `json:"pid"`
	Started    float64 `json:"started"`
	CurrentTPS float64 `json:"current_tps"`
	MemoryMB   float64 `json:"memory_mb"`
	Status     string  `json:"status"`
}

var orch *Orchestrator

const (
	DefaultMaxShards   = 10000
	DefaultTPSThreshold = 15000.0
	MetricsWindow       = 10
	ScaleUpCooldown     = 5
)

func NewOrchestrator(portStart, maxShards int, routerAddr string) *Orchestrator {
	return &Orchestrator{
		shards:       make(map[int]*ShardInfo),
		routerAddr:   routerAddr,
		portStart:    portStart,
		maxShards:    maxShards,
		tpsThreshold: DefaultTPSThreshold,
		tpsHistory:   make([]float64, 0, MetricsWindow),
		ticker:       time.NewTicker(2 * time.Second),
		metricsPort:  6099,
	}
}

func (o *Orchestrator) Start() {
	log.Printf("🚀 Starting Auto-Scaler (max %d shards, TPS threshold %.0f)\n", o.maxShards, o.tpsThreshold)
	
	initialShards := 10
	for i := 0; i < initialShards; i++ {
		o.spawnShard()
		time.Sleep(100 * time.Millisecond)
	}
	
	go func() {
		for range o.ticker.C {
			o.collectMetrics()
			o.evaluateScaling()
			o.cleanupDeadShards()
		}
	}()
	
	go func() {
		http.HandleFunc("/orchestrator/metrics", o.metricsHandler)
		http.HandleFunc("/orchestrator/shards", o.listShardsHandler)
		http.HandleFunc("/orchestrator/scale", o.scaleHandler)
		log.Printf("📊 Metrics server on port %d\n", o.metricsPort)
		log.Fatal(http.ListenAndServe(fmt.Sprintf(":%d", o.metricsPort), nil))
	}()
	
	log.Printf("✅ Orchestrator ready at http://localhost:%d", o.metricsPort)
}

func (o *Orchestrator) spawnShard() error {
	o.mu.Lock()
	defer o.mu.Unlock()
	
	shardID := len(o.shards)
	port := o.portStart + shardID
	
	if shardID >= o.maxShards {
		return fmt.Errorf("max shards reached (%d)", o.maxShards)
	}
	
	cmd := exec.Command("./super_node", "--port", strconv.Itoa(port), "--shard", strconv.Itoa(shardID))
	cmd.Dir = getCurrentDir()
	cmd.Stdout = nil
	cmd.Stderr = nil
	
	if err := cmd.Start(); err != nil {
		return err
	}
	
	info := &ShardInfo{
		ID:      shardID,
		Port:    port,
		PID:     cmd.Process.Pid,
		Started: float64(time.Now().Unix()),
		Status:  "active",
	}
	
	o.shards[shardID] = info
	o.registerWithRouter(shardID, port)
	
	log.Printf("  ✅ Spawned Shard %d on port %d (PID %d)", shardID, port, cmd.Process.Pid)
	
	return nil
}

func (o *Orchestrator) registerWithRouter(shardID, port int) {
	url := fmt.Sprintf("http://%s/shard/register", o.routerAddr)
	req := map[string]interface{}{
		"shard_id": shardID,
		"port":     port,
		"addr":     fmt.Sprintf("localhost:%d", port),
	}
	body, _ := json.Marshal(req)
	http.Post(url, "application/json", strings.NewReader(string(body)))
}

func (o *Orchestrator) collectMetrics() {
	o.mu.RLock()
	defer o.mu.RUnlock()
	
	var totalTPS float64
	var active int
	
	for _, info := range o.shards {
		if info.Status != "active" {
			continue
		}
		
		resp, err := http.Get(fmt.Sprintf("http://localhost:%d/health", info.Port))
		if err != nil {
			info.Status = "unreachable"
			continue
		}
		
		var health map[string]interface{}
		json.NewDecoder(resp.Body).Decode(&health)
		resp.Body.Close()
		
		pending := health["pending_txs"].(float64)
		info.CurrentTPS = pending / 2.0
		info.MemoryMB = o.getProcessMemory(info.PID)
		
		totalTPS += info.CurrentTPS
		active++
	}
	
	avgTPS := 0.0
	if active > 0 {
		avgTPS = totalTPS / float64(active)
	}
	
	o.tpsHistory = append(o.tpsHistory, avgTPS)
	if len(o.tpsHistory) > MetricsWindow {
		o.tpsHistory = o.tpsHistory[1:]
	}
}

func (o *Orchestrator) getProcessMemory(pid int) float64 {
	cmd := exec.Command("ps", "-o", "rss=", "-p", strconv.Itoa(pid))
	out, err := cmd.Output()
	if err != nil {
		return 0
	}
	rss, _ := strconv.ParseFloat(strings.TrimSpace(string(out)), 64)
	return rss / 1024
}

func (o *Orchestrator) evaluateScaling() {
	var sum float64
	for _, tps := range o.tpsHistory {
		sum += tps
	}
	avgTPS := sum / float64(len(o.tpsHistory))
	
	o.mu.Lock()
	defer o.mu.Unlock()
	
	shardCount := len(o.shards)
	
	if avgTPS > o.tpsThreshold && shardCount < o.maxShards {
		log.Printf("📈 High TPS (%.0f > %.0f) - scaling UP!", avgTPS, o.tpsThreshold)
		o.mu.Unlock()
		o.spawnShard()
		o.mu.Lock()
	}
	
	lowTPSThreshold := o.tpsThreshold * 0.2
	if avgTPS < lowTPSThreshold && shardCount > 10 {
		log.Printf("📉 Low TPS (%.0f < %.0f) - scaling DOWN", avgTPS, lowTPSThreshold)
		for id, info := range o.shards {
			if info.CurrentTPS < 50 && info.Status == "active" {
				o.stopShardLocked(id)
				break
			}
		}
	}
}

func (o *Orchestrator) stopShard(id int) {
	o.mu.Lock()
	defer o.mu.Unlock()
	o.stopShardLocked(id)
}

func (o *Orchestrator) stopShardLocked(id int) {
	if info, exists := o.shards[id]; exists {
		log.Printf("  🛑 Stopping Shard %d (port %d, TPS %.0f)", id, info.Port, info.CurrentTPS)
		proc, err := os.FindProcess(info.PID)
		if err == nil {
			proc.Kill()
		}
		info.Status = "stopping"
		o.deregisterFromRouter(id)
	}
}

func (o *Orchestrator) deregisterFromRouter(shardID int) {
	url := fmt.Sprintf("http://%s/shard/deregister", orch.routerAddr)
	req := map[string]interface{}{"shard_id": shardID}
	body, _ := json.Marshal(req)
	http.Post(url, "application/json", strings.NewReader(string(body)))
}

func (o *Orchestrator) cleanupDeadShards() {
	o.mu.Lock()
	defer o.mu.Unlock()
	
	for id, info := range o.shards {
		if info.Status == "stopping" {
			delete(o.shards, id)
		}
	}
}

func (o *Orchestrator) metricsHandler(w http.ResponseWriter, r *http.Request) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	
	var sumTPS float64
	var active, total int
	var totalMem float64
	
	for _, s := range o.shards {
		total++
		if s.Status == "active" {
			active++
			sumTPS += s.CurrentTPS
			totalMem += s.MemoryMB
		}
	}
	
	avgTPS := 0.0
	if active > 0 {
		avgTPS = sumTPS / float64(active)
	}
	
	json.NewEncoder(w).Encode(map[string]interface{}{
		"shards":           total,
		"active":           active,
		"avg_tps":          avgTPS,
		"total_tps":        sumTPS,
		"total_memory_gb":  totalMem / 1024,
		"max_shards":       o.maxShards,
		"tps_threshold":    o.tpsThreshold,
	})
}

func (o *Orchestrator) listShardsHandler(w http.ResponseWriter, r *http.Request) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	
	list := make([]ShardInfo, 0, len(o.shards))
	for _, s := range o.shards {
		list = append(list, *s)
	}
	
	json.NewEncoder(w).Encode(map[string]interface{}{"shards": list, "count": len(list)})
}

func (o *Orchestrator) scaleHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Target int `json:"target"`
	}
	json.NewDecoder(r.Body).Decode(&req)
	
	o.mu.Lock()
	defer o.mu.Unlock()
	
	current := len(o.shards)
	
	if req.Target > current {
		for i := current; i < req.Target; i++ {
			o.mu.Unlock()
			o.spawnShard()
			o.mu.Lock()
			time.Sleep(100 * time.Millisecond)
		}
	} else if req.Target < current {
		for i := current - 1; i >= req.Target; i-- {
			o.stopShardLocked(i)
		}
	}
	
	json.NewEncoder(w).Encode(map[string]interface{}{"status": "scaled", "shards": req.Target})
}

func getCurrentDir() string {
	dir, _ := os.Getwd()
	return dir
}

// ==================== MESH ROUTER ====================

type MeshRouter struct {
	mu     sync.RWMutex
	shards map[int]ShardEndpoint
}

type ShardEndpoint struct {
	ID      int    `json:"shard_id"`
	Port    int    `json:"port"`
	Addr    string `json:"addr"`
	Healthy bool   `json:"healthy"`
}

var router *MeshRouter

func NewMeshRouter() *MeshRouter {
	return &MeshRouter{
		shards: make(map[int]ShardEndpoint),
	}
}

func (r *MeshRouter) Register(shardID int, port int, addr string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	
	r.shards[shardID] = ShardEndpoint{
		ID:      shardID,
		Port:    port,
		Addr:    addr,
		Healthy: true,
	}
	
	log.Printf("🔗 Registered Shard %d -> %s", shardID, addr)
}

func (r *MeshRouter) Deregister(shardID int) {
	r.mu.Lock()
	defer r.mu.Unlock()
	
	delete(r.shards, shardID)
	log.Printf("🔗 Deregistered Shard %d", shardID)
}

func (r *MeshRouter) GetShardForKey(key string) int {
	r.mu.RLock()
	defer r.mu.RUnlock()
	
	if len(r.shards) == 0 {
		return 0
	}
	
	hash := sha256Hash(key)
	shardID := int(hash[0]) % len(r.shards)
	
	i := 0
	for id := range r.shards {
		if i == shardID {
			return id
		}
		i++
	}
	
	return 0
}

func (r *MeshRouter) HandleRegister(w http.ResponseWriter, req *http.Request) {
	var body struct {
		ShardID int    `json:"shard_id"`
		Port    int    `json:"port"`
		Addr    string `json:"addr"`
	}
	json.NewDecoder(req.Body).Decode(&body)
	
	r.Register(body.ShardID, body.Port, body.Addr)
	json.NewEncoder(w).Encode(map[string]interface{}{"status": "registered"})
}

func (r *MeshRouter) HandleDeregister(w http.ResponseWriter, req *http.Request) {
	var body struct {
		ShardID int `json:"shard_id"`
	}
	json.NewDecoder(req.Body).Decode(&body)
	
	r.Deregister(body.ShardID)
	json.NewEncoder(w).Encode(map[string]interface{}{"status": "deregistered"})
}

func (r *MeshRouter) HandleCrossShard(w http.ResponseWriter, req *http.Request) {
	var body struct {
		Key    string `json:"key"`
		Type   string `json:"type"`
		Action string `json:"action"`
	}
	json.NewDecoder(req.Body).Decode(&body)
	
	targetShard := r.GetShardForKey(body.Key)
	
	r.mu.RLock()
	endpoint, exists := r.shards[targetShard]
	r.mu.RUnlock()
	
	if !exists {
		http.Error(w, "Shard not found", 404)
		return
	}
	
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":       "routed",
		"target_shard": targetShard,
		"target_port":  endpoint.Port,
	})
}

func (r *MeshRouter) HandleTransfer(w http.ResponseWriter, req *http.Request) {
	var body struct {
		FromShard int     `json:"from_shard"`
		ToShard   int     `json:"to_shard"`
		To        string  `json:"to"`
		Amount    float64 `json:"amount"`
	}
	json.NewDecoder(req.Body).Decode(&body)
	
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status": "cross_shard_complete",
		"from":   body.FromShard,
		"to":     body.ToShard,
		"amount": body.Amount,
	})
}

// ==================== STATE SHARDING ====================

type StatePartitioner struct {
	mu              sync.RWMutex
	accountShard    map[string]int
	nftShard        map[string]int
	contractShard   map[string]int
}

var partitioner StatePartitioner

func NewStatePartitioner() *StatePartitioner {
	return &StatePartitioner{
		accountShard:  make(map[string]int),
		nftShard:      make(map[string]int),
		contractShard: make(map[string]int),
	}
}

func (sp *StatePartitioner) GetShardForAccount(addr string) int {
	sp.mu.RLock()
	defer sp.mu.RUnlock()
	
	if shard, exists := sp.accountShard[addr]; exists {
		return shard
	}
	
	hash := sha256Hash(addr)
	shard := int(hash[0]) % 256
	sp.accountShard[addr] = shard
	return shard
}

func (sp *StatePartitioner) GetShardForNFT(nftID string) int {
	sp.mu.RLock()
	defer sp.mu.RUnlock()
	
	if shard, exists := sp.nftShard[nftID]; exists {
		return shard
	}
	
	hash := sha256Hash(nftID)
	shard := int(hash[0]) % 256
	sp.nftShard[nftID] = shard
	return shard
}

func (sp *StatePartitioner) GetShardForContract(contractID string) int {
	sp.mu.RLock()
	defer sp.mu.RUnlock()
	
	if shard, exists := sp.contractShard[contractID]; exists {
		return shard
	}
	
	hash := sha256Hash(contractID)
	shard := int(hash[0]) % 256
	sp.contractShard[contractID] = shard
	return shard
}

// ==================== MAIN ====================

func main() {
	port := flag.Int("port", 6500, "Router/Orchestrator port")
	shards := flag.Int("shards", 50, "Initial shard count")
	maxShards := flag.Int("max-shards", 10000, "Maximum shards")
	autoScale := flag.Bool("auto-scale", true, "Enable auto-scaling")
	routerOnly := flag.Bool("router-only", false, "Run just the router")
	
	flag.Parse()
	
	router = NewMeshRouter()
	partitioner = *NewStatePartitioner()
	
	// Router endpoints
	http.HandleFunc("/shard/register", router.HandleRegister)
	http.HandleFunc("/shard/deregister", router.HandleDeregister)
	http.HandleFunc("/cross-shard/ops", router.HandleCrossShard)
	http.HandleFunc("/router/transfer", router.HandleTransfer)
	
	// Health
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status": "ok",
			"mode":   "router",
			"shards": len(router.shards),
		})
	})
	
	if *routerOnly {
		fmt.Printf("\n🕸️  Running as standalone router on port %d\n", *port)
		fmt.Printf("   Registered shards: 0\n")
		log.Fatal(http.ListenAndServe(fmt.Sprintf(":%d", *port), nil))
		return
	}
	
	// Start orchestrator
	routerAddr := fmt.Sprintf("localhost:%d", *port)
	orch = NewOrchestrator(5001, *maxShards, routerAddr)
	
	if *autoScale {
		orch.Start()
	} else {
		log.Printf("🚀 Starting %d shards (auto-scale disabled)", *shards)
		for i := 0; i < *shards; i++ {
			orch.spawnShard()
			time.Sleep(100 * time.Millisecond)
		}
	}
	
	fmt.Printf("\n🕸️  Wrath of Cali - Auto-Scaling Network\n")
	fmt.Printf("   Router Port: %d\n", *port)
	fmt.Printf("   Initial Shards: %d\n", *shards)
	fmt.Printf("   Max Shards: %d\n", *maxShards)
	fmt.Printf("   Auto-Scale: %v\n", *autoScale)
	fmt.Printf("   TPS Threshold: %.0f\n", DefaultTPSThreshold)
	fmt.Printf("   Metrics: http://localhost:%d/orchestrator/metrics\n", *port-1)
	
	log.Fatal(http.ListenAndServe(fmt.Sprintf(":%d", *port), nil))
}