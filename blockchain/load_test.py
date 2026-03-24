"""
Wrath of Cali Blockchain - Load Tester
Tests TPS with multiple validators and shards
"""
import time
import threading
import random
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Dict
import requests


@dataclass
class LoadTestResult:
    """Result of a load test"""
    validators: int
    duration_seconds: float
    total_transactions: int
    tps_achieved: float
    avg_latency_ms: float
    errors: int


class LoadTester:
    """Load test the blockchain"""
    
    def __init__(self, main_node_url: str):
        self.main_node_url = main_node_url
        self.results: List[LoadTestResult] = []
    
    def create_wallet(self) -> Dict:
        """Create a test wallet"""
        try:
            resp = requests.post(f"{self.main_node_url}/wallet/create", timeout=10)
            return resp.json()
        except Exception as e:
            return {"error": str(e)}
    
    def send_transaction(self, sender: str, recipient: str, amount: float, private_key: str) -> Dict:
        """Send a transaction and measure latency"""
        start = time.time()
        try:
            resp = requests.post(
                f"{self.main_node_url}/wallet/transfer",
                json={
                    "sender": sender,
                    "recipient": recipient,
                    "amount": amount,
                    "fee": 0.01,
                    "private_key": private_key
                },
                timeout=5
            )
            latency = (time.time() - start) * 1000
            result = resp.json()
            result["latency_ms"] = latency
            return result
        except Exception as e:
            return {"error": str(e), "latency_ms": (time.time() - start) * 1000}
    
    def run_single_threaded_tps(self, num_transactions: int = 1000) -> LoadTestResult:
        """Test single-threaded TPS (baseline)"""
        print(f"\n📊 Running single-threaded TPS test: {num_transactions} transactions...")
        
        # Create sender wallet with funds
        sender = self.create_wallet()
        if "error" in sender:
            return LoadTestResult(0, 0, 0, 0, 0, 1)
        
        # Create many recipients
        recipients = [self.create_wallet() for _ in range(100)]
        
        errors = 0
        latencies = []
        start_time = time.time()
        
        for i in range(num_transactions):
            recipient = random.choice(recipients)
            result = self.send_transaction(
                sender["address"],
                recipient["address"],
                0.01,
                sender["private_key"]
            )
            
            if "error" in result:
                errors += 1
            else:
                latencies.append(result.get("latency_ms", 0))
            
            if (i + 1) % 100 == 0:
                print(f"  Progress: {i+1}/{num_transactions}")
        
        duration = time.time() - start_time
        successful = num_transactions - errors
        tps = successful / duration if duration > 0 else 0
        avg_latency = statistics.mean(latencies) if latencies else 0
        
        result = LoadTestResult(
            validators=1,
            duration_seconds=duration,
            total_transactions=num_transactions,
            tps_achieved=tps,
            avg_latency_ms=avg_latency,
            errors=errors
        )
        
        print(f"  ✅ Single-threaded: {tps:.1f} TPS, {avg_latency:.1f}ms avg latency")
        return result
    
    def run_parallel_tps(self, num_threads: int, txs_per_thread: int = 100) -> LoadTestResult:
        """Test parallel TPS with multiple threads"""
        print(f"\n📊 Running parallel TPS test: {num_threads} threads × {txs_per_thread} txs...")
        
        # Create sender wallet with funds
        sender = self.create_wallet()
        if "error" in sender:
            return LoadTestResult(0, 0, 0, 0, 0, 1)
        
        recipients = [self.create_wallet() for _ in range(num_threads * 2)]
        
        errors = 0
        latencies = []
        start_time = time.time()
        
        def worker(thread_id: int):
            thread_errors = 0
            thread_latencies = []
            
            for i in range(txs_per_thread):
                recipient = random.choice(recipients)
                result = self.send_transaction(
                    sender["address"],
                    recipient["address"],
                    0.01,
                    sender["private_key"]
                )
                
                if "error" in result:
                    thread_errors += 1
                else:
                    thread_latencies.append(result.get("latency_ms", 0))
            
            return thread_errors, thread_latencies
        
        # Run threads in parallel
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            
            for future in as_completed(futures):
                e, l = future.result()
                errors += e
                latencies.extend(l)
        
        duration = time.time() - start_time
        total_txs = num_threads * txs_per_thread
        successful = total_txs - errors
        tps = successful / duration if duration > 0 else 0
        avg_latency = statistics.mean(latencies) if latencies else 0
        
        result = LoadTestResult(
            validators=num_threads,
            duration_seconds=duration,
            total_transactions=total_txs,
            tps_achieved=tps,
            avg_latency_ms=avg_latency,
            errors=errors
        )
        
        print(f"  ✅ Parallel ({num_threads} threads): {tps:.1f} TPS, {avg_latency:.1f}ms avg latency")
        return result
    
    def run_burst_test(self, num_transactions: int = 1000) -> LoadTestResult:
        """Burst test - send all at once"""
        print(f"\n📊 Running burst test: {num_transactions} simultaneous transactions...")
        
        sender = self.create_wallet()
        if "error" in sender:
            return LoadTestResult(0, 0, 0, 0, 0, 1)
        
        recipients = [self.create_wallet() for _ in range(num_transactions)]
        
        start_time = time.time()
        errors = 0
        latencies = []
        
        def send_one(recipient):
            result = self.send_transaction(
                sender["address"],
                recipient["address"],
                0.01,
                sender["private_key"]
            )
            return result
        
        with ThreadPoolExecutor(max_workers=num_transactions) as executor:
            futures = [executor.submit(send_one, r) for r in recipients]
            
            for future in as_completed(futures):
                result = future.result()
                if "error" in result:
                    errors += 1
                else:
                    latencies.append(result.get("latency_ms", 0))
        
        duration = time.time() - start_time
        successful = num_transactions - errors
        tps = successful / duration if duration > 0 else 0
        avg_latency = statistics.mean(latencies) if latencies else 0
        
        result = LoadTestResult(
            validators=num_transactions,
            duration_seconds=duration,
            total_transactions=num_transactions,
            tps_achieved=tps,
            avg_latency_ms=avg_latency,
            errors=errors
        )
        
        print(f"  ✅ Burst ({num_transactions} concurrent): {tps:.1f} TPS, {avg_latency:.1f}ms avg latency")
        return result


def run_scaling_test(main_node_url: str = "http://localhost:5001"):
    """Run comprehensive scaling test"""
    tester = LoadTester(main_node_url)
    
    print("=" * 60)
    print("🚀 WRATH OF CALI BLOCKCHAIN - SCALING TEST")
    print("=" * 60)
    
    results = []
    
    # Test 1: Baseline single-threaded
    results.append(tester.run_single_threaded_tps(500))
    
    # Test 2: Parallel with different thread counts
    for threads in [5, 10, 25, 50]:
        results.append(tester.run_parallel_tps(threads, 50))
    
    # Test 3: Burst
    results.append(tester.run_burst_test(100))
    
    print("\n" + "=" * 60)
    print("📈 SCALING TEST RESULTS")
    print("=" * 60)
    print(f"{'Test':<30} {'TPS':>10} {'Latency':>12} {'Errors':>8}")
    print("-" * 60)
    
    for r in results:
        test_name = f"{r.validators} threads" if r.validators > 1 else "single-threaded"
        if r.validators == r.total_transactions:
            test_name = f"burst-{r.total_transactions}"
        print(f"{test_name:<30} {r.tps_achieved:>10.1f} {r.avg_latency_ms:>10.1f}ms {r.errors:>8}")
    
    max_tps = max(r.tps_achieved for r in results)
    print("-" * 60)
    print(f"Max TPS achieved: {max_tps:.1f}")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:5001")
    args = parser.parse_args()
    
    run_scaling_test(args.url)