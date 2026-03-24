"""
Wrath of Cali Blockchain - Smart Validator
Automatically discovers shards and routes to least-loaded
"""
import json
import time
import threading
import requests
from typing import Dict, List, Optional
from crypto import generate_keypair, get_address, sign, sha256
from core import Transaction

# Configuration
MAIN_NODE_URL = "http://localhost:5001"  # Default
ROUTER_URL = "http://localhost:6000"      # Shard router
BATCH_SIZE = 100
BATCH_INTERVAL = 2
MIN_STAKE = 1000


class SmartValidator:
    def __init__(self, private_key: str = None, main_node_url: str = None, router_url: str = None):
        self.main_node_url = main_node_url or MAIN_NODE_URL
        self.router_url = router_url or ROUTER_URL
        
        if private_key:
            self.private_key = private_key
            self.public_key = sha256(private_key)
            self.address = get_address(self.public_key)
        else:
            self.private_key, self.public_key = generate_keypair()
            self.address = get_address(self.public_key)
        
        self.current_shard_url = self.main_node_url
        self.pending_local_transactions: List[Dict] = []
        self.running = False
        self.shard_id = 0
        
        # Check if router is available
        self.has_router = self.check_router()
    
    def check_router(self) -> bool:
        """Check if router is available"""
        try:
            resp = requests.get(f"{self.router_url}/health", timeout=3)
            return resp.status_code == 200
        except:
            return False
    
    def discover_shard(self) -> bool:
        """Find the best shard to connect to"""
        if self.has_router:
            try:
                resp = requests.get(f"{self.router_url}/shard/join", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    self.current_shard_url = data["url"]
                    self.shard_id = data["shard_id"]
                    print(f"🔗 Connected to Shard {self.shard_id} via router")
                    return True
            except:
                pass
        
        # Fallback to direct main node
        self.current_shard_url = self.main_node_url
        return True
    
    def get_balance(self) -> float:
        """Get balance from current shard"""
        try:
            resp = requests.get(f"{self.current_shard_url}/balance/{self.address}", timeout=5)
            return resp.json().get("balance", 0)
        except:
            return 0
    
    def stake(self, amount: float) -> bool:
        """Stake coins to become a validator"""
        if amount < MIN_STAKE:
            print(f"❌ Minimum stake is {MIN_STAKE} Calicos")
            return False
        
        balance = self.get_balance()
        if balance < amount:
            print(f"❌ Insufficient balance. Have: {balance}, Need: {amount}")
            return False
        
        tx_data = {
            "tx_type": "STAKE",
            "sender": self.address,
            "recipient": self.address,
            "amount": amount,
            "fee": 0.01,
            "signature": sign(f"{self.address}:{amount}", self.private_key)
        }
        
        try:
            resp = requests.post(f"{self.current_shard_url}/broadcast", json=tx_data, timeout=5)
            result = resp.json()
            if result.get("status") == "accepted":
                print(f"✅ Staked {amount} Calicos on Shard {self.shard_id}!")
                return True
            else:
                print(f"❌ Stake failed: {result.get('error')}")
                return False
        except Exception as e:
            print(f"❌ Error staking: {e}")
            return False
    
    def broadcast_transaction(self, sender: str, recipient: str, amount: float, private_key: str, fee: float = 0.01) -> bool:
        """Broadcast a transaction (smart routing)"""
        tx = Transaction.create_transfer(sender, recipient, amount, private_key, fee)
        tx_dict = tx.to_dict()
        tx_dict["hash"] = tx.get_hash()
        
        # Use router if available
        if self.has_router:
            try:
                # Route based on recipient
                resp = requests.get(f"{self.router_url}/route/{recipient}", timeout=5)
                if resp.status_code == 200:
                    shard_info = resp.json()
                    target_url = shard_info["url"]
                else:
                    target_url = self.current_shard_url
            except:
                target_url = self.current_shard_url
        else:
            target_url = self.current_shard_url
        
        try:
            self.pending_local_transactions.append(tx_dict)
            resp = requests.post(f"{target_url}/broadcast", json=tx_dict, timeout=5)
            result = resp.json()
            
            if result.get("status") == "accepted":
                return True
            else:
                print(f"❌ Transaction rejected: {result.get('error')}")
                return False
        except Exception as e:
            print(f"❌ Error broadcasting: {e}")
            return False
    
    def submit_batch(self) -> bool:
        """Submit a batch to current shard"""
        if not self.pending_local_transactions:
            return False
        
        tx_hashes = [tx["hash"] for tx in self.pending_local_transactions[:BATCH_SIZE]]
        
        batch_data = f"{self.address}:{','.join(tx_hashes)}:{time.time()}"
        batch_signature = sign(batch_data, self.private_key)
        
        batch_payload = {
            "validator": self.address,
            "transactions": tx_hashes,
            "signature": batch_signature
        }
        
        try:
            resp = requests.post(f"{self.current_shard_url}/batch", json=batch_payload, timeout=10)
            result = resp.json()
            
            if result.get("status") == "accepted":
                print(f"📦 Submitted batch to Shard {self.shard_id}: {len(tx_hashes)} txs")
                submitted_hashes = set(tx_hashes)
                self.pending_local_transactions = [
                    tx for tx in self.pending_local_transactions 
                    if tx["hash"] not in submitted_hashes
                ]
                return True
            else:
                print(f"❌ Batch rejected: {result.get('error')}")
                return False
        except Exception as e:
            print(f"❌ Error submitting batch: {e}")
            return False
    
    def run(self, batch_interval: int = BATCH_INTERVAL):
        """Run the validator"""
        self.running = True
        
        # Discover best shard
        self.discover_shard()
        
        print(f"\n🔷 Smart Validator started: {self.address}")
        print(f"   Router: {'✅' if self.has_router else '❌'} {self.router_url}")
        print(f"   Connected to: {self.current_shard_url}")
        
        while self.running:
            time.sleep(batch_interval)
            
            if len(self.pending_local_transactions) >= 10:
                self.submit_batch()
            
            # Re-discover shard periodically for load balancing
            if int(time.time()) % 60 == 0:
                self.discover_shard()
        
        print("🛑 Validator stopped")
    
    def stop(self):
        self.running = False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Smart Validator Node")
    parser.add_argument("--private-key", "-k", help="Private key")
    parser.add_argument("--stake", "-s", type=float, help="Amount to stake")
    parser.add_argument("--main-node", "-m", default=MAIN_NODE_URL, help="Main node URL")
    parser.add_argument("--router", "-r", default=ROUTER_URL, help="Shard router URL")
    parser.add_argument("--create-wallet", "-c", action="store_true", help="Create new wallet")
    parser.add_argument("--daemon", "-d", action="store_true", help="Run as daemon")
    
    args = parser.parse_args()
    
    if args.create_wallet:
        priv, pub = generate_keypair()
        addr = get_address(pub)
        print(f"\n🎭 New Validator Wallet Created!")
        print(f"   Address: {addr}")
        print(f"   Private Key: {priv}\n")
        return
    
    validator = SmartValidator(
        private_key=args.private_key,
        main_node_url=args.main_node,
        router_url=args.router
    )
    
    print(f"\n🔷 Validator: {validator.address}")
    print(f"   Balance: {validator.get_balance()} Calicos")
    
    if args.stake:
        validator.stake(args.stake)
    
    if args.daemon:
        validator.run()
    else:
        print("\n📌 Commands:")
        print("   stake <amount>    - Stake coins")
        print("   balance           - Check balance")
        print("   send <to> <amount> - Send coins")
        print("   batch             - Submit batch")
        print("   quit              - Exit")
        
        while True:
            try:
                cmd = input("\n> ").strip().split()
                if not cmd:
                    continue
                
                if cmd[0] == "quit":
                    break
                elif cmd[0] == "stake" and len(cmd) > 1:
                    validator.stake(float(cmd[1]))
                elif cmd[0] == "balance":
                    print(f"Balance: {validator.get_balance()} Calicos")
                elif cmd[0] == "send" and len(cmd) > 2:
                    priv = input("Enter sender's private key: ").strip()
                    recipient = cmd[1]
                    amount = float(cmd[2])
                    validator.broadcast_transaction(validator.address, recipient, amount, priv)
                elif cmd[0] == "batch":
                    validator.submit_batch()
                else:
                    print("Unknown command")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
    
    print("\n👋 Goodbye!")


if __name__ == "__main__":
    main()