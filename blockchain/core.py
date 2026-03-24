"""
Wrath of Cali Blockchain - Core Data Structures
"""
import json
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field
from crypto import sha256, hash160, generate_keypair, get_address, sign


@dataclass
class Transaction:
    """A single transaction"""
    tx_type: str          # TRANSFER, STAKE, UNSTAKE, BATCH_SUBMIT
    sender: str           # Sender address
    recipient: str        # Recipient address (or stake address for staking)
    amount: float         # Amount of Calicos
    fee: float            # Transaction fee
    timestamp: float      # When created
    signature: str        # Digital signature
    data: str = ""        # Additional data (optional)
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        return d
    
    @staticmethod
    def create_transfer(sender: str, recipient: str, amount: float, private_key: str, fee: float = 0.01) -> 'Transaction':
        """Create a transfer transaction"""
        timestamp = time.time()
        tx_data = f"{sender}:{recipient}:{amount}:{fee}:{timestamp}"
        signature = sign(tx_data, private_key)
        
        return Transaction(
            tx_type="TRANSFER",
            sender=sender,
            recipient=recipient,
            amount=amount,
            fee=fee,
            timestamp=timestamp,
            signature=signature
        )
    
    def get_hash(self) -> str:
        """Get transaction hash"""
        data = f"{self.tx_type}:{self.sender}:{self.recipient}:{self.amount}:{self.fee}:{self.timestamp}"
        return sha256(data)
    
    def is_valid(self, state: Dict) -> bool:
        """Validate transaction"""
        # Check sender has enough balance
        if self.tx_type == "TRANSFER":
            balance = state.get("balances", {}).get(self.sender, 0)
            if balance < self.amount + self.fee:
                return False
        
        # Check signature (simplified)
        # In production, use proper EC signature verification
        return True


@dataclass
class Batch:
    """A batch of transactions from a validator"""
    validator: str        # Validator address
    transactions: List[str]  # List of tx hashes
    batch_hash: str       # Hash of this batch
    timestamp: float      # When created
    signature: str        # Validator signature
    
    @staticmethod
    def create(validator: str, tx_hashes: List[str], private_key: str) -> 'Batch':
        batch_data = f"{validator}:{','.join(tx_hashes)}:{time.time()}"
        batch_hash = sha256(batch_data)
        signature = sign(batch_data, private_key)
        
        return Batch(
            validator=validator,
            transactions=tx_hashes,
            batch_hash=batch_hash,
            timestamp=time.time(),
            signature=signature
        )


@dataclass
class Block:
    """A block in the blockchain"""
    height: int           # Block number
    previous_hash: str    # Hash of previous block
    timestamp: float      # When created
    validator: str        # Who created this block
    batch_hashes: List[str]  # Hashes of included batches
    transactions: List[Dict]  # Full transactions (for easy lookup)
    merkle_root: str      # Merkle root of transactions
    hash: str = ""        # This block's hash
    
    def __post_init__(self):
        if not self.hash:
            self.hash = self.compute_hash()
    
    def compute_hash(self) -> str:
        """Compute block hash"""
        data = f"{self.height}:{self.previous_hash}:{self.timestamp}:{self.validator}:{self.merkle_root}"
        return sha256(data)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @staticmethod
    def create_genesis(initial_balances: Dict[str, float], validator_address: str) -> 'Block':
        """Create the genesis block"""
        # Create initial transfer transactions for initial balances
        transactions = []
        for address, balance in initial_balances.items():
            if balance > 0:
                tx = {
                    "tx_type": "GENESIS",
                    "sender": "SYSTEM",
                    "recipient": address,
                    "amount": balance,
                    "fee": 0,
                    "timestamp": 0,
                    "signature": "genesis",
                    "data": "Genesis block"
                }
                tx["hash"] = sha256(f"{tx['tx_type']}:{tx['sender']}:{tx['recipient']}:{tx['amount']}")
                transactions.append(tx)
        
        merkle = sha256(",".join([t["hash"] for t in transactions]))
        
        return Block(
            height=0,
            previous_hash="0" * 64,
            timestamp=0,
            validator=validator_address,
            batch_hashes=[],
            transactions=transactions,
            merkle_root=merkle
        )


class BlockchainState:
    """In-memory state for the blockchain"""
    
    def __init__(self):
        self.balances: Dict[str, float] = {}
        self.stakes: Dict[str, float] = {}  # validator -> staked amount
        self.validators: Dict[str, Dict] = {}  # address -> validator info
        self.nonce: Dict[str, int] = {}  # For replay protection
    
    def get_balance(self, address: str) -> float:
        return self.balances.get(address, 0)
    
    def add_balance(self, address: str, amount: float):
        self.balances[address] = self.balances.get(address, 0) + amount
    
    def subtract_balance(self, address: str, amount: float) -> bool:
        current = self.balances.get(address, 0)
        if current >= amount:
            self.balances[address] = current - amount
            return True
        return False
    
    def stake(self, address: str, amount: float) -> bool:
        if self.subtract_balance(address, amount):
            self.stakes[address] = self.stakes.get(address, 0) + amount
            return True
        return False
    
    def unstake(self, address: str, amount: float) -> bool:
        current = self.stakes.get(address, 0)
        if current >= amount:
            self.stakes[address] = current - amount
            self.add_balance(address, amount)
            return True
        return False
    
    def to_dict(self) -> Dict:
        return {
            "balances": self.balances,
            "stakes": self.stakes,
            "validators": self.validators,
            "nonce": self.nonce
        }
    
    @staticmethod
    def from_dict(d: Dict) -> 'BlockchainState':
        state = BlockchainState()
        state.balances = d.get("balances", {})
        state.stakes = d.get("stakes", {})
        state.validators = d.get("validators", {})
        state.nonce = d.get("nonce", {})
        return state


if __name__ == "__main__":
    # Test
    from crypto import generate_keypair, get_address
    
    # Generate addresses
    addr1_priv, addr1_pub = generate_keypair()
    addr1 = get_address(addr1_pub)
    addr2_priv, addr2_pub = generate_keypair()
    addr2 = get_address(addr2_pub)
    
    print(f"Address 1: {addr1}")
    print(f"Address 2: {addr2}")
    
    # Create genesis
    genesis = Block.create_genesis({addr1: 1000, addr2: 500}, addr1)
    print(f"\nGenesis Block: {genesis.hash}")
    print(f"Height: {genesis.height}")