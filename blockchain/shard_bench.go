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

const (
	TxPerThread = 50
)

var client = &http.Client{Timeout: 10 * time.Second}

// Shards to test
var shards = []string{
	"http://localhost:5001", "http://localhost:5002", "http://localhost:5003", "http://localhost:5004",
	"http://localhost:5005", "http://localhost:5006", "http://localhost:5007", "http://localhost:5008",
	"http://localhost:5009", "http://localhost:5010", "http://localhost:5011", "http://localhost:5012",
	"http://localhost:5013", "http://localhost:5014", "http://localhost:5015", "http://localhost:5016",
	"http://localhost:5017", "http://localhost:5018", "http://localhost:5019", "http://localhost:5020",
	"http://localhost:5021", "http://localhost:5022", "http://localhost:5023", "http://localhost:5024",
	"http://localhost:5025", "http://localhost:5026", "http://localhost:5027", "http://localhost:5028",
	"http://localhost:5029", "http://localhost:5030", "http://localhost:5031", "http://localhost:5032",
	"http://localhost:5033", "http://localhost:5034", "http://localhost:5035", "http://localhost:5036",
	"http://localhost:5037", "http://localhost:5038", "http://localhost:5039", "http://localhost:5040",
	"http://localhost:5041", "http://localhost:5042", "http://localhost:5043", "http://localhost:5044",
	"http://localhost:5045", "http://localhost:5046", "http://localhost:5047", "http://localhost:5048",
	"http://localhost:5049", "http://localhost:5050",
}

func createWallet(baseURL string) string {
	resp, err := http.Post(baseURL+"/wallet/create", "application/json", nil)
	if err != nil {
		return ""
	}
	defer resp.Body.Close()

	var data struct {
		Address string `json:"address"`
	}
	json.NewDecoder(resp.Body).Decode(&data)

	http.Post(baseURL+"/faucet", "application/json", 
		bytes.NewBuffer([]byte(fmt.Sprintf(`{"address":"%s"}`, data.Address))))

	return data.Address
}

func sendTx(baseURL, sender, recipient string) bool {
	body := []byte(fmt.Sprintf(`{
		"tx_type": "TRANSFER",
		"sender": "%s",
		"recipient": "%s", 
		"amount": 0.001,
		"fee": 0.001,
		"signature": "sig"
	}`, sender, recipient))

	resp, err := client.Post(baseURL+"/broadcast", "application/json", bytes.NewBuffer(body))
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == 200
}

func runDistributedTest(numThreads int) float64 {
	var success int64
	var wg sync.WaitGroup

	start := time.Now()

	for i := 0; i < numThreads; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			// Pick random shard
			shard := shards[rand.Intn(len(shards))]
			// Create funded wallet on that shard
			sender := createWallet(shard)
			if sender == "" {
				return
			}
			for j := 0; j < TxPerThread; j++ {
				recipient := fmt.Sprintf("recipient_%d_%d", rand.Int(), 9999)
				if sendTx(shard, sender, recipient) {
					atomic.AddInt64(&success, 1)
				}
			}
		}()
	}

	wg.Wait()
	duration := time.Since(start).Seconds()
	return float64(success) / duration
}

func main() {
	rand.Seed(time.Now().UnixNano())

	fmt.Println("🚀 50-SHARD DISTRIBUTED LOAD TEST")
	fmt.Println("==================================")
	fmt.Printf("Shards: %d\n\n", len(shards))

	threads := []int{10, 25, 50, 100}
	maxTPS := 0.0

	for _, t := range threads {
		fmt.Printf("Testing %d parallel shard-writers... ", t)
		tps := runDistributedTest(t)
		fmt.Printf("%.0f TPS\n", tps)
		if tps > maxTPS {
			maxTPS = tps
		}
		time.Sleep(2 * time.Second)
	}

	fmt.Println("\n📈 FINAL RESULTS")
	fmt.Println("================")
	fmt.Printf("Max TPS achieved: %.0f\n", maxTPS)
	fmt.Printf("1M TPS in production: ~%.0f shards\n", 1000000/maxTPS)
	fmt.Printf("10M TPS in production: ~%.0f shards\n", 10000000/maxTPS)
}