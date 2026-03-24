"""
Wrath of Cali Blockchain - Sharded Main Node
A single shard that can be scaled horizontally
"""
import json
import time
import threading
from typing import Dict, List, Optional
from dataclasses import asdict
from flask import Flask, request, jsonify
from core import Block, Transaction, Batch, BlockchainState, sha256
from crypto import generate_keypair, get_address, sign
import requests

# Configuration
MINIMUM_STAKE = 1000
BLOCK_TIME = 1
MAX_BATCHES_PER_BLOCK = 1000
MAX_TRANSACTIONS_PER_BATCH = 10000  # Increased for high throughput
SHARD_ID = 0  # Set via --shard flag

app = Flask(__name__)

# Global state
chain: List[Block] = []
state = BlockchainState()
pending_transactions: List[Dict] = []
pending_batches: List[Batch] = []
current_validator_key = None
current_validator_addr = None
shard_router_url = None  # For multi-shard coordination


def init_genesis(shard_id: int = 0):
    """Initialize genesis block"""
    global current_validator_key, current_validator_addr, SHARD_ID
    SHARD_ID = shard_id
    
    current_validator_key, pub = generate_keypair()
    current_validator_addr = get_address(pub)
    
    # Initial balances
    initial_balances = {
        current_validator_addr: 100_000_000,
    }
    
    genesis = Block.create_genesis(initial_balances, current_validator_addr)
    chain.append(genesis)
    
    for tx in genesis.transactions:
        state.add_balance(tx["recipient"], tx["amount"])
    
    print(f"Genesis block created: {genesis.hash}")
    print(f"Shard {SHARD_ID} - Validator: {current_validator_addr}")


def create_block() -> Block:
    """Create a new block with pending batches"""
    prev_block = chain[-1]
    height = prev_block.height + 1
    
    batches_to_include = pending_batches[:MAX_BATCHES_PER_BLOCK]
    batch_hashes = [b.batch_hash for b in batches_to_include]
    
    all_transactions = []
    for batch in batches_to_include:
        for tx_hash in batch.transactions:
            for tx in pending_transactions:
                if tx.get("hash") == tx_hash:
                    all_transactions.append(tx)
                    break
    
    merkle = sha256(",".join([t["hash"] for t in all_transactions])) if all_transactions else sha256("")
    
    block = Block(
        height=height,
        previous_hash=prev_block.hash,
        timestamp=time.time(),
        validator=current_validator_addr,
        batch_hashes=batch_hashes,
        transactions=all_transactions,
        merkle_root=merkle
    )
    
    # Cleanup
    used_batch_hashes = set(batch_hashes)
    pending_batches[:] = [b for b in pending_batches if b.batch_hash not in used_batch_hashes]
    
    used_tx_hashes = set(t["hash"] for t in all_transactions)
    pending_transactions[:] = [t for t in pending_transactions if t.get("hash") not in used_tx_hashes]
    
    for tx in all_transactions:
        apply_transaction(tx)
    
    chain.append(block)
    return block


def apply_transaction(tx: Dict) -> bool:
    """Apply transaction to state"""
    tx_type = tx.get("tx_type")
    
    if tx_type == "TRANSFER":
        sender = tx.get("sender")
        recipient = tx.get("recipient")
        amount = tx.get("amount", 0)
        fee = tx.get("fee", 0)
        
        if state.subtract_balance(sender, amount + fee):
            state.add_balance(recipient, amount)
            return True
    
    elif tx_type == "STAKE":
        sender = tx.get("sender")
        amount = tx.get("amount", 0)
        
        if state.stake(sender, amount):
            if sender not in state.validators:
                state.validators[sender] = {
                    "address": sender,
                    "staked": amount,
                    "joined": time.time(),
                    "batches_submitted": 0
                }
            else:
                state.validators[sender]["staked"] += amount
            return True
    
    elif tx_type == "UNSTAKE":
        sender = tx.get("sender")
        amount = tx.get("amount", 0)
        
        if state.unstake(sender, amount):
            return True
    
    return True  # Genesis transactions


def block_producer_loop():
    """Background block production"""
    while True:
        time.sleep(BLOCK_TIME)
        if pending_batches or pending_transactions:
            block = create_block()
            print(f"Shard {SHARD_ID} - Block #{block.height} ({len(block.transactions)} txs)")


# API Endpoints

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "shard": SHARD_ID,
        "height": len(chain),
        "pending_txs": len(pending_transactions),
        "pending_batches": len(pending_batches)
    })


@app.route('/block/<int:height>', methods=['GET'])
def get_block(height: int):
    if 0 <= height < len(chain):
        return jsonify(chain[height].to_dict())
    return jsonify({"error": "Block not found"}), 404


@app.route('/block/latest', methods=['GET'])
def get_latest_block():
    return jsonify(chain[-1].to_dict())


@app.route('/transaction/<tx_hash>', methods=['GET'])
def get_transaction(tx_hash: str):
    for block in chain:
        for tx in block.transactions:
            if tx.get("hash") == tx_hash:
                return jsonify(tx)
    for tx in pending_transactions:
        if tx.get("hash") == tx_hash:
            return jsonify(tx)
    return jsonify({"error": "Transaction not found"}), 404


@app.route('/balance/<address>', methods=['GET'])
def get_balance(address: str):
    balance = state.get_balance(address)
    staked = state.stakes.get(address, 0)
    return jsonify({
        "address": address,
        "balance": balance,
        "staked": staked,
        "total": balance + staked
    })


@app.route('/broadcast', methods=['POST'])
def broadcast_transaction():
    data = request.json
    
    tx = Transaction(
        tx_type=data.get("tx_type", "TRANSFER"),
        sender=data.get("sender"),
        recipient=data.get("recipient"),
        amount=data.get("amount", 0),
        fee=data.get("fee", 0.01),
        timestamp=time.time(),
        signature=data.get("signature", ""),
        data=data.get("data", "")
    )
    
    balance = state.get_balance(tx.sender)
    if balance < tx.amount + tx.fee:
        return jsonify({"error": "Insufficient balance"}), 400
    
    tx_dict = tx.to_dict()
    tx_dict["hash"] = tx.get_hash()
    pending_transactions.append(tx_dict)
    
    return jsonify({"status": "accepted", "hash": tx_dict["hash"]})


@app.route('/batch', methods=['POST'])
def submit_batch():
    data = request.json
    
    validator = data.get("validator")
    tx_hashes = data.get("transactions", [])
    signature = data.get("signature")
    
    if state.stakes.get(validator, 0) < MINIMUM_STAKE:
        return jsonify({"error": "Validator not staked enough"}), 400
    
    valid_hashes = set(tx["hash"] for tx in pending_transactions)
    for h in tx_hashes:
        if h not in valid_hashes:
            return jsonify({"error": f"Transaction {h} not found"}), 400
    
    batch = Batch(
        validator=validator,
        transactions=tx_hashes,
        batch_hash="",
        timestamp=time.time(),
        signature=signature
    )
    batch.batch_hash = sha256(f"{batch.validator}:{','.join(tx_hashes)}:{batch.timestamp}")
    
    pending_batches.append(batch)
    
    if validator in state.validators:
        state.validators[validator]["batches_submitted"] = \
            state.validators[validator].get("batches_submitted", 0) + 1
    
    return jsonify({"status": "accepted", "batch_hash": batch.batch_hash})


@app.route('/validators', methods=['GET'])
def get_validators():
    validators = []
    for addr, info in state.validators.items():
        validators.append({
            "address": addr,
            "staked": state.stakes.get(addr, 0),
            "batches_submitted": info.get("batches_submitted", 0)
        })
    return jsonify(validators)


@app.route('/pending', methods=['GET'])
def get_pending():
    return jsonify({
        "transactions": len(pending_transactions),
        "batches": len(pending_batches)
    })


@app.route('/wallet/create', methods=['POST'])
def create_wallet():
    priv, pub = generate_keypair()
    addr = get_address(pub)
    return jsonify({
        "address": addr,
        "private_key": priv,
        "public_key": pub
    })


@app.route('/wallet/transfer', methods=['POST'])
def create_transfer():
    data = request.json
    sender = data.get("sender")
    private_key = data.get("private_key")
    recipient = data.get("recipient")
    amount = float(data.get("amount", 0))
    fee = float(data.get("fee", 0.01))
    
    tx = Transaction.create_transfer(sender, recipient, amount, private_key, fee)
    tx_dict = tx.to_dict()
    tx_dict["hash"] = tx.get_hash()
    
    balance = state.get_balance(sender)
    if balance < amount + fee:
        return jsonify({"error": "Insufficient balance"}), 400
    
    pending_transactions.append(tx_dict)
    return jsonify({"status": "accepted", "transaction": tx_dict})


@app.route('/faucet', methods=['POST'])
def faucet():
    data = request.json
    address = data.get("address")
    
    validator_addr = current_validator_addr
    
    if state.subtract_balance(validator_addr, 10000):
        state.add_balance(address, 10000)
        return jsonify({"status": "funded", "amount": 10000})
    return jsonify({"error": "Faucet empty"}), 500


# Multi-shard coordination endpoints

@app.route('/shard/register', methods=['POST'])
def register_shard():
    """Register this shard with the router"""
    global shard_router_url
    data = request.json
    shard_router_url = data.get("router_url")
    
    if shard_router_url:
        try:
            requests.post(f"{shard_router_url}/register", json={
                "shard_id": SHARD_ID,
                "url": f"http://localhost:{app.config.get('PORT', 5000)}"
            }, timeout=5)
        except:
            pass
    
    return jsonify({"status": "registered", "shard": SHARD_ID})


@app.route('/shard/status', methods=['GET'])
def shard_status():
    """Get shard status for load balancing"""
    return jsonify({
        "shard_id": SHARD_ID,
        "height": len(chain),
        "pending_txs": len(pending_transactions),
        "pending_batches": len(pending_batches),
        "validators": len(state.validators)
    })


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", "-p", type=int, default=5001)
    parser.add_argument("--shard", "-s", type=int, default=0)
    parser.add_argument("--router", "-r", help="Shard router URL")
    args = parser.parse_args()
    
    app.config['PORT'] = args.port
    
    init_genesis(args.shard)
    
    # Register with router
    if args.router:
        global shard_router_url
        shard_router_url = args.router
        try:
            requests.post(f"{args.router}/register", json={
                "shard_id": args.shard,
                "url": f"http://localhost:{args.port}"
            }, timeout=5)
        except Exception as e:
            print(f"Could not register with router: {e}")
    
    # Start block producer
    producer = threading.Thread(target=block_producer_loop, daemon=True)
    producer.start()
    
    print(f"\n🌟 Wrath of Cali Blockchain - Shard {args.shard}")
    print(f"   Block time: {BLOCK_TIME}s")
    print(f"   API: http://localhost:{args.port}")
    print(f"   Max batches/block: {MAX_BATCHES_PER_BLOCK}")
    print(f"   Max txs/batch: {MAX_TRANSACTIONS_PER_BATCH}\n")
    
    app.run(host='0.0.0.0', port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()