"""
Wrath of Cali Blockchain - Wallet CLI
Simple CLI for managing wallets and transactions
"""
import json
import time
import requests
from crypto import generate_keypair, get_address, sign, sha256
from core import Transaction

# Configuration
MAIN_NODE_URL = "http://localhost:5000"


def save_wallet(address: str, private_key: str, public_key: str):
    """Save wallet to file"""
    wallet_file = f"wallet_{address[:8]}.json"
    data = {
        "address": address,
        "private_key": private_key,
        "public_key": public_key,
        "created": time.time()
    }
    with open(wallet_file, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"💾 Wallet saved to: {wallet_file}")


def load_wallet(filename: str):
    """Load wallet from file"""
    with open(filename, 'r') as f:
        return json.load(f)


def get_balance(address: str) -> dict:
    """Get balance from main node"""
    try:
        resp = requests.get(f"{MAIN_NODE_URL}/balance/{address}", timeout=5)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def broadcast_transaction(tx_dict: dict) -> dict:
    """Broadcast transaction to main node"""
    try:
        resp = requests.post(f"{MAIN_NODE_URL}/broadcast", json=tx_dict, timeout=10)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def create_transfer_tx(sender: str, recipient: str, amount: float, private_key: str, fee: float = 0.01) -> dict:
    """Create a transfer transaction"""
    tx = Transaction.create_transfer(sender, recipient, amount, private_key, fee)
    tx_dict = tx.to_dict()
    tx_dict["hash"] = tx.get_hash()
    return tx_dict


def main():
    """Wallet CLI"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Wrath of Cali Wallet")
    parser.add_argument("--main-node", "-m", default=MAIN_NODE_URL, help="Main node URL")
    parser.add_argument("--create", "-c", action="store_true", help="Create new wallet")
    parser.add_argument("--load", "-l", help="Load wallet from file")
    parser.add_argument("--balance", "-b", help="Check balance of address")
    parser.add_argument("--send", nargs=3, metavar=("TO", "AMOUNT", "FEE"), help="Send coins")
    parser.add_argument("--from", dest="from_addr", help="Sender address (for send)")
    parser.add_argument("--privkey", help="Private key (for send)")
    
    args = parser.parse_args()
    
    # Global override
    MAIN_NODE_URL = args.main_node
    
    if args.create:
        priv, pub = generate_keypair()
        addr = get_address(pub)
        
        print(f"\n🎭 New Wallet Created!")
        print(f"   Address: {addr}")
        print(f"   Private Key: {priv}")
        print(f"   Public Key: {pub}")
        print(f"\n⚠️  SAVE YOUR PRIVATE KEY - IT CANNOT BE RECOVERED!\n")
        
        # Ask to save
        save = input("Save wallet to file? (y/n): ").strip().lower()
        if save == 'y':
            save_wallet(addr, priv, pub)
        
        return
    
    if args.balance:
        balance = get_balance(args.balance)
        if "error" in balance:
            print(f"❌ Error: {balance['error']}")
        else:
            print(f"\n💰 Wallet: {args.balance}")
            print(f"   Balance: {balance.get('balance', 0)} Calicos")
            print(f"   Staked:  {balance.get('staked', 0)} Calicos")
            print(f"   Total:   {balance.get('total', 0)} Calicos\n")
        return
    
    if args.load:
        try:
            wallet = load_wallet(args.load)
            print(f"📂 Loaded wallet: {wallet['address']}")
            
            balance = get_balance(wallet['address'])
            print(f"   Balance: {balance.get('balance', 0)} Calicos")
            print(f"   Staked:  {balance.get('staked', 0)} Calicos")
        except Exception as e:
            print(f"❌ Error loading wallet: {e}")
        return
    
    if args.send:
        if not args.from_addr or not args.privkey:
            print("❌ Need --from and --privkey for send")
            return
        
        recipient = args.send[0]
        amount = float(args.send[1])
        fee = float(args.send[2]) if args.send[2] else 0.01
        
        print(f"\n📤 Sending {amount} Calicos to {recipient}")
        print(f"   From: {args.from_addr}")
        print(f"   Fee: {fee}")
        
        # Check balance first
        bal = get_balance(args.from_addr)
        available = bal.get('balance', 0)
        print(f"   Available: {available}")
        
        if available < amount + fee:
            print("❌ Insufficient balance!")
            return
        
        # Create and broadcast
        tx = create_transfer_tx(args.from_addr, recipient, amount, args.privkey, fee)
        result = broadcast_transaction(tx)
        
        if result.get("status") == "accepted":
            print(f"✅ Transaction broadcasted!")
            print(f"   Hash: {tx['hash']}")
        else:
            print(f"❌ Failed: {result.get('error')}")
        return
    
    # Default: show help
    parser.print_help()
    print("\n📌 Examples:")
    print("   python wallet.py --create                    # Create new wallet")
    print("   python wallet.py --balance <address>       # Check balance")
    print("   python wallet.py --load wallet_xxxx.json   # Load wallet")
    print("   python wallet.py --send <to> <amt> <fee> --from <addr> --privkey <key>")


if __name__ == "__main__":
    main()