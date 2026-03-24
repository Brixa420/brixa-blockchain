"""
Wrath of Cali Blockchain - Validator Node
Collects transactions and submits batches to the main node
"""
import json
import time
import threading
import requests
from typing import Dict, List, Any, Optional
from crypto import generate_keypair, get_address, sign, sha256
from core import Transaction

# Configuration
MAIN_NODE_URL = "http://localhost:5000"
BATCH_SIZE = 100  # Transactions per batch
BATCH_INTERVAL = 2  # Seconds between batch submissions
MIN_STAKE = 1000  # Minimum to stake


class Validator:
    def __init__(self, private_key: str = None, main_node_url: str = MAIN_NODE_URL):
        self.main_node_url = main_node_url
        
        if private_key:
            self.private_key = private_key
            # Derive public key and address
            import hashlib
            self.public_key = sha256(private_key)
            self.address = get_address(self.public_key)
        else:
            # Generate new wallet
            self.private_key, self.public_key = generate_keypair()
            self.address = get_address(self.public_key)
        
        self.pending_local_transactions: List[Dict] = []
        self.running = False
        
    def get_balance(self) -> float:
        """Get balance from main node"""
        try:
            resp = requests.get(f"{self.main_node_url}/balance/{self.address}", timeout=5)
            data = resp.json()
            return data.get("balance", 0)
        except:
            return 0
    
    def get_staked(self) -> float:
        """Get staked amount from main node"""
        try:
            resp = requests.get(f"{self.main_node_url}/balance/{self.address}", timeout=5)
            data = resp.json()
            return data.get("staked", 0)
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
        
        # Create stake transaction
        tx_data = {
            "tx_type": "STAKE",
            "sender": self.address,
            "recipient": self.address,
            "amount": amount,
            "fee": 0.01,
            "signature": sign(f"{self.address}:{amount}", self.private_key)
        }
        
        try:
            resp = requests.post(f"{self.main_node_url}/broadcast", json=tx_data, timeout=5)
            result = resp.json()
            if result.get("status") == "accepted":
                print(f"✅ Staked {amount} Calicos!")
                return True
            else:
                print(f"❌ Stake failed: {result.get('error')}")
                return False
        except Exception as e:
            print(f"❌ Error staking: {e}")
            return False
    
    def add_transaction(self, sender: str, recipient: str, amount: float, private_key: str, fee: float = 0.01):
        """Add a transaction to local pool"""
        tx = Transaction.create_transfer(sender, recipient, amount, private_key, fee)
        tx_dict = tx.to_dict()
        tx_dict["hash"] = tx.get_hash()
        self.pending_local_transactions.append(tx_dict)
        print(f"📝 Added transaction: {tx_dict['hash'][:16]}... ({len(self.pending_local_transactions)} pending)")
    
    def submit_batch(self) -> bool:
        """Submit a batch of transactions to main node"""
        if not self.pending_local_transactions:
            return False
        
        # Get transactions to include
        tx_hashes = [tx["hash"] for tx in self.pending_local_transactions[:BATCH_SIZE]]
        
        # Create batch
        batch_data = f"{self.address}:{','.join(tx_hashes)}:{time.time()}"
        batch_signature = sign(batch_data, self.private_key)
        
        batch_payload = {
            "validator": self.address,
            "transactions": tx_hashes,
            "signature": batch_signature
        }
        
        try:
            resp = requests.post(f"{self.main_node_url}/batch", json=batch_payload, timeout=10)
            result = resp.json()
            
            if result.get("status") == "accepted":
                print(f"📦 Submitted batch: {result.get('batch_hash')[:16]}... ({len(tx_hashes)} txs)")
                # Remove submitted transactions
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
    
    def broadcast_transaction(self, sender: str, recipient: str, amount: float, private_key: str, fee: float = 0.01):
        """Broadcast a transaction directly to main node"""
        tx = Transaction.create_transfer(sender, recipient, amount, private_key, fee)
        tx_dict = tx.to_dict()
        tx_dict["hash"] = tx.get_hash()
        
        try:
            # First add to local pool
            self.pending_local_transactions.append(tx_dict)
            
            # Broadcast to main node
            resp = requests.post(f"{self.main_node_url}/broadcast", json=tx_dict, timeout=5)
            result = resp.json()
            
            if result.get("status") == "accepted":
                print(f"✅ Broadcast transaction: {tx_dict['hash'][:16]}...")
                return True
            else:
                print(f"❌ Transaction rejected: {result.get('error')}")
                return False
        except Exception as e:
            print(f"❌ Error broadcasting: {e}")
            return False
    
    def run(self, batch_interval: int = BATCH_INTERVAL):
        """Run the validator"""
        self.running = True
        print(f"\n🔷 Validator started: {self.address}")
        print(f"   Main node: {self.main_node_url}")
        
        while self.running:
            time.sleep(batch_interval)
            
            # Check if we have enough transactions for a batch
            if len(self.pending_local_transactions) >= 10:  # Submit if at least 10
                self.submit_batch()
            
            # Also check if there are pending transactions on main node
            try:
                resp = requests.get(f"{self.main_node_url}/pending", timeout=5)
                pending = resp.json()
                if pending.get("batches", 0) > 0:
                    # Other validators are working!
                    pass
            except:
                pass
        
        print("🛑 Validator stopped")
    
    def stop(self):
        """Stop the validator"""
        self.running = False


def create_validator_wallet(main_node_url: str = MAIN_NODE_URL):
    """Create a new validator wallet"""
    priv, pub = generate_keypair()
    addr = get_address(pub)
    
    print(f"\n🎭 New Validator Wallet Created!")
    print(f"   Address: {addr}")
    print(f"   Private Key: {priv}")
    print(f"\n⚠️  SAVE YOUR PRIVATE KEY - IT CANNOT BE RECOVERED!")
    print(f"   Minimum stake required: {MIN_STAKE} Calicos\n")
    
    return priv, pub, addr


def main():
    """CLI for validator"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Wrath of Cali Validator Node")
    parser.add_argument("--private-key", "-k", help="Private key")
    parser.add_argument("--stake", "-s", type=float, help="Amount to stake on startup")
    parser.add_argument("--main-node", "-m", default=MAIN_NODE_URL, help="Main node URL")
    parser.add_argument("--create-wallet", "-c", action="store_true", help="Create new wallet")
    parser.add_argument("--interval", "-i", type=int, default=BATCH_INTERVAL, help="Batch interval (seconds)")
    parser.add_argument("--daemon", "-d", action="store_true", help="Run as daemon")
    
    args = parser.parse_args()
    
    if args.create_wallet:
        create_validator_wallet(args.main_node)
        return
    
    if args.private_key:
        validator = Validator(args.private_key, args.main_node)
    else:
        validator = Validator(main_node_url=args.main_node)
    
    print(f"\n🔷 Validator: {validator.address}")
    
    # Check balance
    balance = validator.get_balance()
    print(f"   Balance: {balance} Calicos")
    
    if args.stake:
        print(f"   Staking {args.stake} Calicos...")
        validator.stake(args.stake)
    
    if args.daemon:
        validator.run(args.interval)
    else:
        # Interactive mode
        print("\n📌 Commands:")
        print("   stake <amount>    - Stake coins")
        print("   balance            - Check balance")
        print("   send <to> <amount> - Send coins")
        print("   batch              - Submit batch now")
        print("   quit               - Exit")
        
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
                    print(f"Staked: {validator.get_staked()} Calicos")
                elif cmd[0] == "send" and len(cmd) > 2:
                    # Need sender's private key - prompt
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