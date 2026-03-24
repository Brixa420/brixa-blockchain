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
	TxPerThread = 100
	NodeURL     = "http://localhost:5001"
)

var client = &http.Client{Timeout: 10 * time.Second}

type Result struct {
	Threads    int
	TotalTxs   int
	Successful int
	Duration   float64
	TPS        float64
}

func createWallet() string {
	resp, err := http.Post(NodeURL+"/wallet/create", "application/json", nil)
	if err != nil {
		return ""
	}
	defer resp.Body.Close()

	var data struct {
		Address string `json:"address"`
	}
	json.NewDecoder(resp.Body).Decode(&data)

	// Fund wallet
	http.Post(NodeURL+"/faucet", "application/json", 
		bytes.NewBuffer([]byte(fmt.Sprintf(`{"address":"%s"}`, data.Address))))

	return data.Address
}

func sendTx(sender, recipient string) bool {
	body := []byte(fmt.Sprintf(`{
		"tx_type": "TRANSFER",
		"sender": "%s",
		"recipient": "%s", 
		"amount": 0.001,
		"fee": 0.001,
		"signature": "sig_placeholder"
	}`, sender, recipient))

	resp, err := client.Post(NodeURL+"/broadcast", "application/json", bytes.NewBuffer(body))
	if err != nil {
		return false
	}
	defer resp.Body.Close()

	return resp.StatusCode == 200
}

func runTest(numThreads int) Result {
	sender := createWallet()
	if sender == "" {
		return Result{Threads: numThreads}
	}

	start := time.Now()
	var success int64
	var wg sync.WaitGroup

	for i := 0; i < numThreads; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < TxPerThread; j++ {
				recipient := fmt.Sprintf("recipient_%d_%d", rand.Int(), 9999)
				if sendTx(sender, recipient) {
					atomic.AddInt64(&success, 1)
				}
			}
		}()
	}

	wg.Wait()
	duration := time.Since(start).Seconds()
	total := numThreads * TxPerThread
	tps := float64(success) / duration

	return Result{
		Threads:    numThreads,
		TotalTxs:   total,
		Successful: int(success),
		Duration:   duration,
		TPS:        tps,
	}
}

func main() {
	fmt.Println("🚀 GO BLOCKCHAIN LOAD TEST")
	fmt.Println("===========================")

	// Check node
	resp, err := client.Get(NodeURL + "/health")
	if err != nil {
		fmt.Printf("❌ Cannot connect to %s\n", NodeURL)
		return
	}
	resp.Body.Close()
	fmt.Printf("Connected to %s\n\n", NodeURL)

	threads := []int{1, 5, 10, 25, 50, 100}
	results := []Result{}

	for _, t := range threads {
		fmt.Printf("Testing %d threads × %d txs... ", t, TxPerThread)
		r := runTest(t)
		results = append(results, r)
		fmt.Printf("%.0f TPS\n", r.TPS)
		time.Sleep(time.Second)
	}

	// Summary
	fmt.Println("\n📈 RESULTS")
	fmt.Println("==========")
	fmt.Printf("%-10s %-12s %-12s\n", "Threads", "Total", "TPS")
	fmt.Println("-----------------------------")

	maxTPS := 0.0
	for _, r := range results {
		fmt.Printf("%-10d %-12d %-12.1f\n", r.Threads, r.TotalTxs, r.TPS)
		if r.TPS > maxTPS {
			maxTPS = r.TPS
		}
	}

	fmt.Println("-----------------------------")
	fmt.Printf("Max TPS: %.1f\n", maxTPS)
	if maxTPS > 0 {
		fmt.Printf("Shards for 1M TPS: ~%.0f\n", 1000000/maxTPS)
		fmt.Printf("Shards for 10M TPS: ~%.0f\n", 10000000/maxTPS)
	}
}