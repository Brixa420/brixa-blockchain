"""
Wrath of Cali Blockchain - Shard Router
Routes transactions to the correct shard based on address
"""
import hashlib
from typing import Dict, List, Optional


class ShardRouter:
    """Routes transactions to correct shard"""
    
    def __init__(self, num_shards: int = 4):
        self.num_shards = num_shards
        self.shards: Dict[int, Dict] = {}
        
    def get_shard(self, address: str) -> int:
        """Get shard index for an address"""
        h = int(hashlib.sha256(address.encode()).hexdigest()[:8], 16)
        return h % self.num_shards
    
    def register_shard(self, shard_id: int, main_node_url: str, load: float = 0):
        """Register a main node for a shard"""
        self.shards[shard_id] = {
            "url": main_node_url,
            "load": load,
            "validators": 0,
            "tx_count": 0
        }
    
    def update_load(self, shard_id: int, load: float):
        """Update shard load"""
        if shard_id in self.shards:
            self.shards[shard_id]["load"] = load
    
    def get_least_loaded_shard(self) -> int:
        """Get the shard with lowest load for new validators"""
        if not self.shards:
            return 0
        return min(self.shards.keys(), key=lambda s: self.shards[s]["load"])
    
    def get_shard_url(self, address: str) -> str:
        """Get the main node URL for an address"""
        shard = self.get_shard(address)
        if shard in self.shards:
            return self.shards[shard]["url"]
        return None
    
    def add_validator(self, shard_id: int):
        """Add a validator to shard count"""
        if shard_id in self.shards:
            self.shards[shard_id]["validators"] += 1
    
    def remove_validator(self, shard_id: int):
        """Remove a validator from shard count"""
        if shard_id in self.shards:
            self.shards[shard_id]["validators"] = max(0, self.shards[shard_id]["validators"] - 1)
    
    def get_status(self) -> Dict:
        """Get router status"""
        return {
            "num_shards": self.num_shards,
            "shards": self.shards
        }


# Singleton instance
router = ShardRouter(num_shards=4)


if __name__ == "__main__":
    # Test routing
    router.register_shard(0, "http://localhost:5001", 0)
    router.register_shard(1, "http://localhost:5002", 0)
    router.register_shard(2, "http://localhost:5003", 0)
    router.register_shard(3, "http://localhost:5004", 0)
    
    # Generate test addresses
    test_addrs = [f"test_addr_{i}" for i in range(10)]
    
    print("Address -> Shard routing:")
    for addr in test_addrs:
        shard = router.get_shard(addr)
        print(f"  {addr[:20]}... -> Shard {shard}")
    
    print(f"\nLeast loaded shard: {router.get_least_loaded_shard()}")
    print(f"\nStatus: {router.get_status()}")