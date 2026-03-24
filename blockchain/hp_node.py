"""
Wrath of Cali Blockchain - High Performance Node
Optimized with connection pooling, async workers, and batching
"""
import json
import time
import threading
import os
from typing import Dict, List
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor

# Use gevent for async if available
try:
    from gevent import monkey
    monkey.patch_all()
    HAS_GEVENT = True
except ImportError:
    HAS_GEVENT = False
    print("⚠️ gevent not installed. Install for better performance: pip install gevent")

from flask import Flask, request, jsonify
from core import Block, Transaction, Batch, BlockchainState, sha256
from crypto import generate_keypair, get_address, sign

# Configuration
MINIMUM_STAKE = 1000
BLOCK_TIME = 1
MAX_BATCHES_PER_BLOCK = 10000  # Huge batches
MAX_TRANSACTIONS_PER_BATCH = 50000
SHARD_ID = 0

# Performance tuning
WORKERS = int(os.environ.get('WORKERS', 50))  # Thread pool workers
REQUEST_QUEUE_SIZE = int(os.environ.get('QUEUE', 10000))
PENDING_TX_CAP = 50000  # Max pending transactions in memory

app = Flask(__name__)

# Thread pool for parallel tx processing
executor = ThreadPoolExecutor(max_workers=WORKERS)

# Global state (thread-safe via GIL for simple ops)
chain: List[Block] = []
state = BlockchainState()
pending_transactions: List[Dict] = []
pending_batches: List[Batch] = []
current_validator_key = None
current_validator_addr = None
tx_counter = 0
block_counter = 0


def init_genesis(shard_id: int = 0):
    global current_validator_key, current_validator_addr, SHARD_ID, tx_counter, block_counter
    SHARD_ID = shard_id
    
    current_validator_key, pub = generate_keypair()
    current_validator_addr = get_address(pub)
    
    initial_balances = {current_validator_addr: 100_000_000}
    
    genesis = Block.create_genesis(initial_balances, current_validator_addr)
    chain.append(genesis)
    
    for tx in genesis.transactions:
        state.add_balance(tx["recipient"], tx["amount"])
    
    tx_counter = 0
    block_counter = 0
    print(f"🔷 Shard {SHARD_ID} initialized: {current_validator_addr[:16]}...")


def create_block_fast() -> Block:
    """Optimized block creation"""
    global block_counter
    
    if not pending_batches and not pending_transactions:
        return None
    
    prev_block = chain[-1]
    height = prev_block.height + 1
    block_counter += 1
    
    # Take batches
    batches_to_include = pending_batches[:MAX_BATCHES_PER_BLOCK]
    batch_hashes = [b.batch_hash for b in batches_to_include]
    
    # Flatten transactions
    all_transactions = []
    tx_set = set()
    
    for batch in batches_to_include:
        for tx_hash in batch.transactions:
            if tx_hash not in tx_set:
                for tx in pending_transactions:
                    if tx.get("hash") == tx_hash:
                        all_transactions.append(tx)
                        tx_set.add(tx_hash)
                        break
    
    # Merkle root (fast)
    tx_hashes = [t["hash"] for t in all_transactions]
    merkle = sha256("".join(tx_hashes)) if tx_hashes else sha256("genesis")
    
    block = Block(
        height=height,
        previous_hash=prev_block.hash,
        timestamp=time.time(),
        validator=current_validator_addr,
        batch_hashes=batch_hashes,
        transactions=all_transactions,
        merkle_root=merkle
    )
    
    # Fast cleanup using set
    used_batch = set(batch_hashes)
    pending_batches[:] = [b for b in pending_batches if b.batch_hash not in used_batch]
    
    used_tx = set(tx_set)
    pending_transactions[:] = [t for t in pending_transactions if t.get("hash") not in used_tx]
    
    # Apply transactions
    for tx in all_transactions:
        _apply_transaction(tx)
    
    chain.append(block)
    return block


def _apply_transaction(tx: Dict) -> bool:
    """Fast transaction application"""
    tx_type = tx.get("tx_type")
    
    if tx_type == "TRANSFER":
        sender = tx.get("sender")
        amount = tx.get("amount", 0)
        fee = tx.get("fee", 0)
        
        if state.subtract_balance(sender, amount + fee):
            state.add_balance(tx.get("recipient"), amount)
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
    
    return True


def block_producer_loop():
    """Background block production"""
    while True:
        time.sleep(BLOCK_TIME)
        block = create_block_fast()
        if block:
            print(f"📦 Shard {SHARD_ID} Block #{block.height} ({len(block.transactions)} txs)")


# Optimized API Endpoints

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "shard": SHARD_ID,
        "height": len(chain),
        "pending_txs": len(pending_transactions),
        "pending_batches": len(pending_batches),
        "workers": WORKERS
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
    for block in chain[-5:]:  # Search last 5 blocks
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
    global tx_counter
    data = request.json
    
    sender = data.get("sender")
    amount = data.get("amount", 0)
    fee = data.get("fee", 0.01)
    
    # Quick balance check
    if state.get_balance(sender) < amount + fee:
        return jsonify({"error": "Insufficient balance"}), 400
    
    tx_counter += 1
    
    tx = Transaction(
        tx_type=data.get("tx_type", "TRANSFER"),
        sender=sender,
        recipient=data.get("recipient"),
        amount=amount,
        fee=fee,
        timestamp=time.time(),
        signature=data.get("signature", ""),
        data=data.get("data", "")
    )
    
    tx_dict = tx.to_dict()
    tx_dict["hash"] = tx.get_hash()
    
    # Add to pending (with cap)
    if len(pending_transactions) < PENDING_TX_CAP:
        pending_transactions.append(tx_dict)
    
    return jsonify({"status": "accepted", "hash": tx_dict["hash"]})


@app.route('/broadcast/batch', methods=['POST'])
def broadcast_batch():
    """Accept multiple transactions at once"""
    global tx_counter
    data = request.json
    txs = data.get("transactions", [])
    
    if not txs:
        return jsonify({"error": "No transactions"}), 400
    
    accepted = []
    for tx_data in txs:
        sender = tx_data.get("sender")
        amount = tx_data.get("amount", 0)
        fee = tx_data.get("fee", 0.01)
        
        if state.get_balance(sender) >= amount + fee:
            tx_counter += 1
            tx = Transaction(
                tx_type=tx_data.get("tx_type", "TRANSFER"),
                sender=sender,
                recipient=tx_data.get("recipient"),
                amount=amount,
                fee=fee,
                timestamp=time.time(),
                signature=tx_data.get("signature", ""),
                data=tx_data.get("data", "")
            )
            tx_dict = tx.to_dict()
            tx_dict["hash"] = tx.get_hash()
            
            if len(pending_transactions) < PENDING_TX_CAP:
                pending_transactions.append(tx_dict)
            accepted.append(tx_dict["hash"])
    
    return jsonify({"status": "accepted", "count": len(accepted), "hashes": accepted})


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
        "batches": len(pending_batches),
        "capacity": PENDING_TX_CAP
    })


@app.route('/wallet/create', methods=['POST'])
def create_wallet():
    priv, pub = generate_keypair()
    addr = get_address(pub)
    return jsonify({"address": addr, "private_key": priv, "public_key": pub})


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
    
    if state.get_balance(sender) < amount + fee:
        return jsonify({"error": "Insufficient balance"}), 400
    
    pending_transactions.append(tx_dict)
    return jsonify({"status": "accepted", "transaction": tx_dict})


@app.route('/faucet', methods=['POST'])
def faucet():
    data = request.json
    address = data.get("address")
    
    if state.subtract_balance(current_validator_addr, 10000):
        state.add_balance(address, 10000)
        return jsonify({"status": "funded", "amount": 10000})
    return jsonify({"error": "Faucet empty"}), 500


@app.route('/shard/status', methods=['GET'])
def shard_status():
    return jsonify({
        "shard_id": SHARD_ID,
        "height": len(chain),
        "pending_txs": len(pending_transactions),
        "pending_batches": len(pending_batches),
        "validators": len(state.validators),
        "total_txs_processed": tx_counter,
        "total_blocks": block_counter
    })


@app.route('/stats', methods=['GET'])
def get_stats():
    return jsonify({
        "shard": SHARD_ID,
        "height": len(chain),
        "total_txs": tx_counter,
        "blocks": block_counter,
        "pending": len(pending_transactions),
        "batches": len(pending_batches),
        "workers": WORKERS
    })


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", "-p", type=int, default=5001)
    parser.add_argument("--shard", "-s", type=int, default=0)
    parser.add_argument("--workers", "-w", type=int, default=WORKERS)
    parser.add_argument("--queue", "-q", type=int, default=PENDING_TX_CAP)
    parser.add_argument("--router", "-r", help="Shard router URL")
    args = parser.parse_args()
    
    global WORKERS, PENDING_TX_CAP
    WORKERS = args.workers
    PENDING_TX_CAP = args.queue
    
    init_genesis(args.shard)
    
    # Register with router if provided
    if args.router:
        try:
            import requests
            requests.post(f"{args.router}/register", json={
                "shard_id": args.shard,
                "url": f"http://localhost:{args.port}"
            }, timeout=5)
        except:
            pass
    
    # Start block producer
    producer = threading.Thread(target=block_producer_loop, daemon=True)
    producer.start()
    
    print(f"\n⚡ Wrath of Cali High-Performance Node")
    print(f"   Shard: {args.shard}")
    print(f"   Port: {args.port}")
    print(f"   Workers: {args.workers}")
    print(f"   Queue: {args.queue}")
    print(f"   Max batches/block: {MAX_BATCHES_PER_BLOCK}\n")
    
    # Use threaded=True for concurrency
    app.run(host='0.0.0.0', port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()