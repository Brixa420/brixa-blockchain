"""
Wrath of Cali Blockchain - Shard Router
Coordinates multiple shards for infinite horizontal scaling
"""
import hashlib
import time
import threading
from typing import Dict, List, Optional
from dataclasses import dataclass
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Configuration
DEFAULT_SHARDS = 4
HEARTBEAT_INTERVAL = 5  # seconds

# Shard registry
shards: Dict[int, Dict] = {}
shard_lock = threading.Lock()


def get_shard_for_address(address: str, num_shards: int = None) -> int:
    """Get shard ID for an address using consistent hashing"""
    if num_shards is None:
        num_shards = len(shards) or DEFAULT_SHARDS
    h = int(hashlib.sha256(address.encode()).hexdigest()[:8], 16)
    return h % num_shards


def get_shard_url(shard_id: int) -> Optional[str]:
    """Get URL for a shard"""
    with shard_lock:
        return shards.get(shard_id, {}).get("url")


def get_least_loaded_shard() -> Optional[int]:
    """Get shard with lowest load"""
    with shard_lock:
        if not shards:
            return None
        return min(shards.keys(), key=lambda s: shards[s].get("load", 0))


def update_shard_load(shard_id: int, load: float):
    """Update a shard's load"""
    with shard_lock:
        if shard_id in shards:
            shards[shard_id]["load"] = load
            shards[shard_id]["last_heartbeat"] = time.time()


def register_shard(shard_id: int, url: str):
    """Register a new shard"""
    with shard_lock:
        shards[shard_id] = {
            "url": url,
            "load": 0,
            "registered": time.time(),
            "last_heartbeat": time.time(),
            "height": 0
        }
        print(f"📛 Registered Shard {shard_id} -> {url}")


def unregister_dead_shards():
    """Remove shards that haven't heartbeated"""
    now = time.time()
    with shard_lock:
        dead = [s for s, info in shards.items() 
                if now - info.get("last_heartbeat", 0) > HEARTBEAT_INTERVAL * 3]
        for s in dead:
            del shards[s]
            print(f"💀 Unregistered dead Shard {s}")


def heartbeat_loop():
    """Monitor shard health"""
    while True:
        time.sleep(HEARTBEAT_INTERVAL)
        
        # Check for dead shards
        unregister_dead_shards()
        
        # Query shard statuses
        with shard_lock:
            for shard_id, info in shards.items():
                try:
                    resp = requests.get(f"{info['url']}/shard/status", timeout=3)
                    data = resp.json()
                    update_shard_load(shard_id, data.get("pending_txs", 0))
                    shards[shard_id]["height"] = data.get("height", 0)
                except:
                    pass


# API Endpoints

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "shards": len(shards),
        "shard_list": [{"id": s, "url": i["url"], "load": i.get("load", 0)} 
                       for s, i in shards.items()]
    })


@app.route('/register', methods=['POST'])
def register():
    """Register a shard"""
    data = request.json
    shard_id = data.get("shard_id")
    url = data.get("url")
    
    if shard_id is None or not url:
        return jsonify({"error": "shard_id and url required"}), 400
    
    register_shard(shard_id, url)
    return jsonify({"status": "registered", "shard_id": shard_id})


@app.route('/unregister/<int:shard_id>', methods=['POST'])
def unregister(shard_id: int):
    """Unregister a shard"""
    with shard_lock:
        if shard_id in shards:
            del shards[shard_id]
            return jsonify({"status": "unregistered"})
    return jsonify({"error": "Shard not found"}), 404


@app.route('/shards', methods=['GET'])
def list_shards():
    """List all active shards"""
    with shard_lock:
        return jsonify([
            {
                "id": s,
                "url": info["url"],
                "load": info.get("load", 0),
                "height": info.get("height", 0),
                "age": time.time() - info.get("registered", 0)
            }
            for s, info in shards.items()
        ])


@app.route('/shard/<int:shard_id>', methods=['GET'])
def get_shard(shard_id: int):
    """Get specific shard info"""
    with shard_lock:
        if shard_id in shards:
            return jsonify(shards[shard_id])
    return jsonify({"error": "Shard not found"}), 404


@app.route('/route/<address>', methods=['GET'])
def route_to_shard(address: str):
    """Get the shard for an address"""
    num_shards = len(shards) or DEFAULT_SHARDS
    shard_id = get_shard_for_address(address, num_shards)
    url = get_shard_url(shard_id)
    
    if url:
        return jsonify({
            "address": address,
            "shard_id": shard_id,
            "url": url,
            "load": shards.get(shard_id, {}).get("load", 0)
        })
    
    return jsonify({"error": "No shards available"}), 503


@app.route('/route', methods=['POST'])
def route_transaction():
    """Route a transaction to the correct shard"""
    data = request.json
    recipient = data.get("recipient")
    
    if not recipient:
        return jsonify({"error": "recipient required"}), 400
    
    num_shards = len(shards) or DEFAULT_SHARDS
    shard_id = get_shard_for_address(recipient, num_shards)
    url = get_shard_url(shard_id)
    
    if url:
        try:
            resp = requests.post(f"{url}/broadcast", json=data, timeout=10)
            result = resp.json()
            result["shard_id"] = shard_id
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 502
    
    return jsonify({"error": "No shards available"}), 503


@app.route('/shard/join', methods=['POST'])
def join_least_loaded():
    """Get the least loaded shard for a new validator"""
    shard_id = get_least_loaded_shard()
    if shard_id is None:
        return jsonify({"error": "No shards available"}), 503
    
    url = get_shard_url(shard_id)
    return jsonify({
        "shard_id": shard_id,
        "url": url,
        "load": shards.get(shard_id, {}).get("load", 0)
    })


@app.route('/stats', methods=['GET'])
def get_stats():
    """Get overall network stats"""
    with shard_lock:
        total_load = sum(s.get("load", 0) for s in shards.values())
        total_height = max((s.get("height", 0) for s in shards.values()), default=0)
        
        return jsonify({
            "shards": len(shards),
            "total_pending_txs": total_load,
            "max_height": total_height,
            "avg_load": total_load / len(shards) if shards else 0
        })


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Shard Router")
    parser.add_argument("--port", "-p", type=int, default=6000)
    parser.add_argument("--shards", "-n", type=int, default=DEFAULT_SHARDS)
    args = parser.parse_args()
    
    # Start heartbeat monitor
    monitor = threading.Thread(target=heartbeat_loop, daemon=True)
    monitor.start()
    
    print(f"\n🌐 Wrath of Cali Shard Router")
    print(f"   Listening on: http://localhost:{args.port}")
    print(f"   Default shards: {args.shards}\n")
    
    app.run(host='0.0.0.0', port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()