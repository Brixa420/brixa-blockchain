"""
Wrath of Cali Blockchain - Distributed Load Test
Tests TPS across multiple shards via router
"""
import time
import random
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List
import statistics


@dataclass
class TestResult:
    threads: int
    total_txs: int
    successful: int
    duration: float
    tps: float
    latency_avg: float
    latency_p99: float


class DistributedLoadTester:
    def __init__(self, router_url: str = "http://localhost:6000"):
        self.router_url = router_url
        
    def create_wallet(self) -> dict:
        """Create wallet via router (auto-routed)"""
        try:
            # Create wallet locally then fund
            import hashlib, secrets
            priv = secrets.token_hex(32)
            pub = hashlib.sha256(priv.encode()).hexdigest()
            addr = pub[:40]  # Simplified
            
            # Fund from any shard's faucet
            resp = requests.post(f"http://localhost:5010/faucet", json={"address": addr}, timeout=5)
            return {"address": addr, "private_key": priv, "funded": resp.status_code == 200}
        except:
            return None
    
    def route_and_send(self, sender: dict, recipient: str, amount: float) -> dict:
        """Route transaction via shard router"""
        start = time.time()
        
        try:
            # Get shard for recipient
            resp = requests.get(f"{self.router_url}/route/{recipient}", timeout=5)
            if resp.status_code != 200:
                return {"error": "No route", "latency": (time.time() - start) * 1000}
            
            shard = resp.json()
            target_url = shard["url"]
            
            # Build transaction
            tx = {
                "tx_type": "TRANSFER",
                "sender": sender["address"],
                "recipient": recipient,
                "amount": amount,
                "fee": 0.001,
                "signature": f"sig_{sender['private_key'][:16]}",
                "timestamp": time.time()
            }
            
            # Send to correct shard
            resp = requests.post(f"{target_url}/broadcast", json=tx, timeout=5)
            latency = (time.time() - start) * 1000
            
            return {
                "success": resp.status_code == 200,
                "latency": latency,
                "shard": shard.get("shard_id")
            }
        except Exception as e:
            return {"error": str(e), "latency": (time.time() - start) * 1000}
    
    def run_distributed_test(self, num_threads: int, txs_per_thread: int) -> TestResult:
        """Run distributed load test"""
        print(f"\n📊 Distributed test: {num_threads} threads × {txs_per_thread} txs")
        
        # Get available shards
        resp = requests.get(f"{self.router_url}/shards", timeout=5)
        shards = resp.json()
        print(f"   Available shards: {len(shards)}")
        
        if not shards:
            print("   ❌ No shards available!")
            return None
        
        # Create sender with funds
        sender = self.create_wallet()
        if not sender or not sender.get("funded"):
            # Fallback: use direct shard
            resp = requests.post("http://localhost:5010/wallet/create")
            sender = resp.json()
            requests.post("http://localhost:5010/faucet", json={"address": sender["address"]})
        
        print(f"   Sender: {sender['address'][:20]}...")
        
        # Create recipients (one per transaction)
        recipients = [f"recipient_{i}_{random.randint(1000,9999)}" for i in range(num_threads * txs_per_thread)]
        
        latencies = []
        successes = 0
        errors = 0
        
        start_time = time.time()
        
        def worker(thread_id: int):
            thread_success = 0
            thread_latencies = []
            
            for i in range(txs_per_thread):
                recipient = recipients[thread_id * txs_per_thread + i]
                result = self.route_and_send(sender, recipient, 0.001)
                
                if result.get("success"):
                    thread_success += 1
                    thread_latencies.append(result.get("latency", 0))
                else:
                    thread_latencies.append(result.get("latency", 0))
            
            return thread_success, thread_latencies
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            
            for future in as_completed(futures):
                s, l = future.result()
                successes += s
                latencies.extend(l)
        
        duration = time.time() - start_time
        total = num_threads * txs_per_thread
        tps = successes / duration if duration > 0 else 0
        
        avg_latency = statistics.mean(latencies) if latencies else 0
        p99_latency = sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0
        
        print(f"   ✅ {successes}/{total} successful in {duration:.2f}s = {tps:.1f} TPS")
        
        return TestResult(
            threads=num_threads,
            total_txs=total,
            successful=successes,
            duration=duration,
            tps=tps,
            latency_avg=avg_latency,
            latency_p99=p99_latency
        )


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--router", default="http://localhost:6000")
    parser.add_argument("--threads", "-t", type=int, default=10)
    parser.add_argument("--txs", "-n", type=int, default=100)
    args = parser.parse_args()
    
    tester = DistributedLoadTester(args.router)
    
    print("=" * 60)
    print("🚀 DISTRIBUTED BLOCKCHAIN LOAD TEST")
    print("=" * 60)
    
    # Check router
    resp = requests.get(f"{args.router}/health", timeout=5)
    data = resp.json()
    print(f"\n📡 Router: {args.router}")
    print(f"   Active shards: {data.get('shards', 0)}")
    
    results = []
    
    # Test with increasing load
    for threads in [5, 10, 25, 50, 100]:
        result = tester.run_distributed_test(threads, args.txs)
        if result:
            results.append(result)
    
    # Summary
    print("\n" + "=" * 60)
    print("📈 SCALING RESULTS")
    print("=" * 60)
    print(f"{'Threads':<10} {'Total Txs':<12} {'TPS':<12} {'Latency':<12} {'P99':<8}")
    print("-" * 60)
    
    max_tps = 0
    for r in results:
        print(f"{r.threads:<10} {r.total_txs:<12} {r.tps:<12.1f} {r.latency_avg:<10.1f}ms {r.latency_p99:<8.1f}ms")
        max_tps = max(max_tps, r.tps)
    
    print("-" * 60)
    print(f"Max TPS: {max_tps:.1f}")
    
    # Calculate what we'd need for 1M TPS
    if max_tps > 0:
        shards_needed = 1000000 / max_tps
        print(f"Shards needed for 1M TPS: ~{shards_needed:.0f}")
    print("=" * 60)


if __name__ == "__main__":
    main()