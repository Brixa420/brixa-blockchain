package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"
)

// Optimizations: Connection pooling, batch API, cross-shard txs

type Shard struct {
	ID       int     `json:"id"`
	URL      string  `json:"url"`
	Load     float64 `json:"load"`
	Height   int     `json:"height"`
	LastHB   int64   `json:"last_heartbeat"`
}

type Router struct {
	mu             sync.RWMutex
	shards         map[int]Shard
	crossShardTxs  map[string]chan bool  // Pending cross-shard txs
}

var router Router

func init() {
	router.shards = make(map[int]Shard)
	router.crossShardTxs = make(map[string]chan bool)
}

func (r *Router) getShardID(addr string) int {
	h := 0
	for _, c := range addr {
		h = h*31 + int(c)
	}
	r.mu.RLock()
	n := len(r.shards)
	r.mu.RUnlock()
	if n == 0 {
		return 0
	}
	return ((h % n) + n) % n
}

func (r *Router) registerShard(id int, url string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.shards[id] = Shard{ID: id, URL: url, LastHB: time.Now().Unix()}
	log.Printf("📛 Registered Shard %d -> %s", id, url)
}

func (r *Router) getShard(id int) (Shard, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	s, ok := r.shards[id]
	return s, ok
}

func (r *Router) listShards() []Shard {
	r.mu.RLock()
	defer r.mu.RUnlock()
	list := make([]Shard, 0, len(r.shards))
	for _, s := range r.shards {
		list = append(list, s)
	}
	return list
}

func (r *Router) getLeastLoaded() (Shard, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	if len(r.shards) == 0 {
		return Shard{}, false
	}
	minLoad := float64(1 << 63)
	var minShard Shard
	for _, s := range r.shards {
		if s.Load < minLoad {
			minLoad = s.Load
			minShard = s
		}
	}
	return minShard, true
}

func (r *Router) getShardForAddress(addr string) (Shard, bool) {
	shardID := r.getShardID(addr)
	return r.getShard(shardID)
}

// Cross-shard transaction support
func (r *Router) routeCrossShard(txHash, senderShard, recipientShard string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	
	// If sender and recipient on same shard, no coordination needed
	if senderShard == recipientShard {
		return
	}
	
	// Mark as cross-shard pending
	r.crossShardTxs[txHash] = make(chan bool, 1)
}

func (r *Router) confirmCrossShard(txHash string, success bool) {
	r.mu.Lock()
	defer r.mu.Unlock()
	
	if ch, ok := r.crossShardTxs[txHash]; ok {
		ch <- success
		close(ch)
		delete(r.crossShardTxs, txHash)
	}
}

// HTTP Handlers
func healthHandler(w http.ResponseWriter, r *http.Request) {
	list := router.listShards()
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":          "ok",
		"shards":          len(list),
		"list":            list,
		"cross_shard_txs": len(router.crossShardTxs),
	})
}

func registerHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		ShardID int    `json:"shard_id"`
		URL     string `json:"url"`
	}
	json.NewDecoder(r.Body).Decode(&req)
	router.registerShard(req.ShardID, req.URL)
	json.NewEncoder(w).Encode(map[string]string{"status": "registered"})
}

func shardsHandler(w http.ResponseWriter, r *http.Request) {
	json.NewEncoder(w).Encode(router.listShards())
}

func routeHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Recipient string `json:"recipient"`
		Sender    string `json:"sender"`  // Optional: for cross-shard detection
	}
	json.NewDecoder(r.Body).Decode(&req)
	
	shardID := router.getShardID(req.Recipient)
	shard, ok := router.getShard(shardID)
	if !ok {
		http.Error(w, "No shards available", 503)
		return
	}
	
	// Check if cross-shard
	crossShard := -1
	if req.Sender != "" {
		senderShardID := router.getShardID(req.Sender)
		if senderShardID != shardID {
			crossShard = senderShardID
		}
	}
	
	json.NewEncoder(w).Encode(map[string]interface{}{
		"shard_id":    shard.ID,
		"url":         shard.URL,
		"cross_shard": crossShard >= 0,
		"from_shard":  crossShard,
	})
}

func joinHandler(w http.ResponseWriter, r *http.Request) {
	shard, ok := router.getLeastLoaded()
	if !ok {
		http.Error(w, "No shards", 503)
		return
	}
	json.NewEncoder(w).Encode(map[string]interface{}{
		"shard_id": shard.ID,
		"url":      shard.URL,
	})
}

// Batch broadcast - send multiple txs at once
func batchBroadcastHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		ShardID int `json:"shard_id"`
		Txs     []struct {
			Sender    string  `json:"sender"`
			Recipient string  `json:"recipient"`
			Amount    float64 `json:"amount"`
		} `json:"transactions"`
	}
	json.NewDecoder(r.Body).Decode(&req)
	
	shard, ok := router.getShard(req.ShardID)
	if !ok {
		http.Error(w, "Shard not found", 404)
		return
	}
	
	// Forward to shard
	client := &http.Client{Timeout: 30 * time.Second}
	body, _ := json.Marshal(req.Txs)
	resp, err := client.Post(shard.URL+"/broadcast/batch", "application/json", bytes.NewBuffer(body))
	if err != nil {
		http.Error(w, err.Error(), 502)
		return
	}
	defer resp.Body.Close()
	
	var result map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&result)
	json.NewEncoder(w).Encode(result)
}

func main() {
	port := flag.Int("port", 6000, "Router port")
	flag.Parse()
	
	http.HandleFunc("/health", healthHandler)
	http.HandleFunc("/register", registerHandler)
	http.HandleFunc("/shards", shardsHandler)
	http.HandleFunc("/route", routeHandler)
	http.HandleFunc("/join", joinHandler)
	http.HandleFunc("/batch", batchBroadcastHandler)
	
	fmt.Printf("\n🌐 Wrath of Cali - Optimized Shard Router\n")
	fmt.Printf("   Port: %d\n", *port)
	fmt.Printf("   Features: Cross-shard txs, Batch API, Load balancing\n\n")
	
	log.Fatal(http.ListenAndServe(fmt.Sprintf(":%d", *port), nil))
}