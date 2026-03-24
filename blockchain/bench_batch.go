package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"math/rand"
	"net/http"
	"sync"
	"sync/atomic"
	"time"
)

const TxPerThread = 100

var shards = []string{
	"http://localhost:5001", "http://localhost:5002", "http://localhost:5003", "http://localhost:5004",
	"http://localhost:5005", "http://localhost:5006", "http://localhost:5007", "http://localhost:5008",
	"http://localhost:5009", "http://localhost:5010", "http://localhost:5011", "http://localhost:5012",
	"http://localhost:5013", "http://localhost:5014", "http://localhost:5015", "http://localhost:5016",
	"http://localhost:5017", "http://localhost:5018", "http://localhost:5019", "http://localhost:5020",
	"http://localhost:5021", "http://localhost:5022", "http://localhost:5023", "http://localhost:5024",
	"http://localhost:5025",
}

var client = &http.Client{Timeout: 30 * time.Second}

func createWallet(baseURL string) string {
	resp, err := http.Post(baseURL+"/wallet/create", "application/json", nil)
	if err != nil {
		return ""
	}
	defer resp.Body.Close()
	var data struct{ Address string `json:"address"` }
	json.NewDecoder(resp.Body).Decode(&data)
	http.Post(baseURL+"/faucet", "application/json", bytes.NewBuffer([]byte(fmt.Sprintf(`{"address":"%s"}`, data.Address))))
	return data.Address
}

// Single tx (baseline)
func sendTx(baseURL, sender, recipient string) bool {
	body := []byte(fmt.Sprintf(`{"tx_type":"TRANSFER","sender":"%s","recipient":"%s","amount":0.001,"fee":0.001,"signature":"sig"}`, sender, recipient))
	resp, err := client.Post(baseURL+"/broadcast", "application/json", bytes.NewBuffer(body))
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == 200
}

// Batch tx (optimized)
func sendBatch(baseURL, sender string, recipients []string) int {
	txs := make([]map[string]interface{}, len(recipients))
	for i, r := range recipients {
		txs[i] = map[string]interface{}{
			"tx_type":   "TRANSFER",
			"sender":    sender,
			"recipient": r,
			"amount":    0.001,
			"fee":       0.001,
			"signature": "sig",
		}
	}
	body, _ := json.Marshal(txs)
	resp, err := client.Post(baseURL+"/broadcast/batch", "application/json", bytes.NewBuffer(body))
	if err != nil {
		return 0
	}
	defer resp.Body.Close()
	
	var result map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&result)
	count, _ := result["count"].(float64)
	return int(count)
}

func runSingleTest(numThreads int) float64 {
	var success int64
	var wg sync.WaitGroup
	start := time.Now()

	for i := 0; i < numThreads; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			shard := shards[rand.Intn(len(shards))]
			sender := createWallet(shard)
			if sender == "" {
				return
			}
			for j := 0; j < TxPerThread; j++ {
				if sendTx(shard, sender, fmt.Sprintf("r_%d_%d", rand.Int(), 9999)) {
					atomic.AddInt64(&success, 1)
				}
			}
		}()
	}
	wg.Wait()
	return float64(success) / time.Since(start).Seconds()
}

func runBatchTest(numThreads int) float64 {
	var success int64
	var wg sync.WaitGroup
	start := time.Now()

	for i := 0; i < numThreads; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			shard := shards[rand.Intn(len(shards))]
			sender := createWallet(shard)
			if sender == "" {
				return
			}
			// Send batches of 50
			for j := 0; j < TxPerThread/50; j++ {
				recipients := make([]string, 50)
				for k := range recipients {
					recipients[k] = fmt.Sprintf("r_%d_%d", rand.Int(), 9999)
				}
				count := sendBatch(shard, sender, recipients)
				atomic.AddInt64(&success, int64(count))
			}
		}()
	}
	wg.Wait()
	return float64(success) / time.Since(start).Seconds()
}

func main() {
	rand.Seed(time.Now().UnixNano())

	fmt.Println("🚀 BLOCKCHAIN BENCHMARK - SINGLE vs BATCH")
	fmt.Println("==========================================")

	// Check shards
	resp, _ := http.Get(shards[0] + "/health")
	if resp == nil {
		fmt.Println("❌ No shards running!")
		return
	}
	resp.Body.Close()
	fmt.Printf("Shards: %d\n\n", len(shards))

	// Single tx test
	fmt.Println("📤 SINGLE TRANSACTIONS:")
	threads := []int{10, 25, 50}
	var singleTPS float64
	for _, t := range threads {
		fmt.Printf("  %d threads... ", t)
		tps := runSingleTest(t)
		fmt.Printf("%.0f TPS\n", tps)
		singleTPS = tps
	}

	// Batch tx test
	fmt.Println("\n📦 BATCH TRANSACTIONS (50x):")
	var batchTPS float64
	for _, t := range threads {
		fmt.Printf("  %d threads... ", t)
		tps := runBatchTest(t)
		fmt.Printf("%.0f TPS\n", tps)
		batchTPS = tps
	}

	fmt.Println("\n📈 RESULTS")
	fmt.Println("==========")
	fmt.Printf("Single TX Max:    %.0f TPS\n", singleTPS)
	fmt.Printf("Batch TX Max:     %.0f TPS\n", batchTPS)
	fmt.Printf("Speedup:          %.1fx\n", batchTPS/singleTPS)
	fmt.Printf("\nFor 1M TPS: ~%.0f batch shards\n", 1000000/batchTPS)
}