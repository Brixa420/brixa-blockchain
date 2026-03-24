"""
NFT & Smart Contract Module
Implements: NFTs, smart contracts, multi-sig wallets, event system
"""
import json
import time
import hashlib
import secrets
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from crypto import sha256


# ========== NFT SYSTEM ==========
@dataclass
class NFT:
    """In-game NFT (item, achievement, character)"""
    token_id: str
    owner: str
    nft_type: str  # "item", "achievement", "character", "land", "pet"
    name: str
    description: str
    attributes: Dict  # Custom attributes (stats, rarity, etc.)
    uri: str = ""  # Metadata URI
    creator: str = ""
    created_at: float = field(default_factory=time.time)
    data: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "token_id": self.token_id,
            "owner": self.owner,
            "type": self.nft_type,
            "name": self.name,
            "description": self.description,
            "attributes": self.attributes,
            "uri": self.uri,
            "creator": self.creator,
            "created_at": self.created_at,
            "data": self.data
        }


class NFTManager:
    """Manages in-game NFTs"""
    
    def __init__(self):
        self.nfts: Dict[str, NFT] = {}  # token_id -> NFT
        self.owners: Dict[str, List[str]] = {}  # owner -> token_ids
        self.next_token_id = 1
    
    def mint(self, owner: str, nft_type: str, name: str, description: str = "",
             attributes: Dict = None, uri: str = "", creator: str = "", data: Dict = None) -> NFT:
        """Mint a new NFT"""
        token_id = f"NFT{self.next_token_id:06d}"
        self.next_token_id += 1
        
        nft = NFT(
            token_id=token_id,
            owner=owner,
            nft_type=nft_type,
            name=name,
            description=description,
            attributes=attributes or {},
            uri=uri,
            creator=creator or owner,
            data=data or {}
        )
        
        self.nfts[token_id] = nft
        
        if owner not in self.owners:
            self.owners[owner] = []
        self.owners[owner].append(token_id)
        
        return nft
    
    def transfer(self, token_id: str, from_addr: str, to_addr: str) -> bool:
        """Transfer NFT ownership"""
        if token_id not in self.nfts:
            return False
        
        nft = self.nfts[token_id]
        if nft.owner != from_addr:
            return False
        
        # Remove from old owner
        if from_addr in self.owners and token_id in self.owners[from_addr]:
            self.owners[from_addr].remove(token_id)
        
        # Add to new owner
        nft.owner = to_addr
        if to_addr not in self.owners:
            self.owners[to_addr] = []
        self.owners[to_addr].append(token_id)
        
        return True
    
    def get_nft(self, token_id: str) -> Optional[NFT]:
        """Get NFT by token ID"""
        return self.nfts.get(token_id)
    
    def get_owner_nfts(self, owner: str) -> List[Dict]:
        """Get all NFTs owned by an address"""
        if owner not in self.owners:
            return []
        return [self.nfts[tid].to_dict() for tid in self.owners[owner]]
    
    def get_by_type(self, nft_type: str) -> List[Dict]:
        """Get all NFTs of a type"""
        return [nft.to_dict() for nft in self.nfts.values() if nft.nft_type == nft_type]
    
    def burn(self, token_id: str, owner: str) -> bool:
        """Burn an NFT"""
        if token_id not in self.nfts:
            return False
        
        nft = self.nfts[token_id]
        if nft.owner != owner:
            return False
        
        del self.nfts[token_id]
        if owner in self.owners and token_id in self.owners[owner]:
            self.owners[owner].remove(token_id)
        
        return True


# ========== MULTI-SIG WALLET ==========
@dataclass
class MultiSigWallet:
    """Multi-signature wallet (party/guild shared)"""
    wallet_id: str
    name: str
    owners: List[str]  # List of owner addresses
    required_signatures: int  # Signatures needed to execute
    balance: float = 0
    created_at: float = field(default_factory=time.time)
    nonce: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "wallet_id": self.wallet_id,
            "name": self.name,
            "owners": self.owners,
            "required_signatures": self.required_signatures,
            "balance": self.balance,
            "created_at": self.created_at,
            "nonce": self.nonce
        }


@dataclass
class MultiSigTransaction:
    """Pending multi-sig transaction"""
    tx_id: str
    wallet_id: str
    to: str
    amount: float
    signatures: List[str]  # List of signatures
    created_by: str
    created_at: float = field(default_factory=time.time)
    executed: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "tx_id": self.tx_id,
            "wallet_id": self.wallet_id,
            "to": self.to,
            "amount": self.amount,
            "signatures": self.signatures,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "executed": self.executed
        }


class MultiSigManager:
    """Manages multi-signature wallets"""
    
    def __init__(self):
        self.wallets: Dict[str, MultiSigWallet] = {}
        self.pending_txs: Dict[str, MultiSigTransaction] = {}
    
    def create_wallet(self, name: str, owners: List[str], required: int) -> MultiSigWallet:
        """Create a multi-sig wallet"""
        if required > len(owners):
            raise ValueError("Required signatures cannot exceed owners")
        
        wallet_id = f"MSIG{secrets.token_hex(8)}"
        
        wallet = MultiSigWallet(
            wallet_id=wallet_id,
            name=name,
            owners=owners,
            required_signatures=required
        )
        
        self.wallets[wallet_id] = wallet
        return wallet
    
    def get_wallet(self, wallet_id: str) -> Optional[MultiSigWallet]:
        """Get wallet by ID"""
        return self.wallets.get(wallet_id)
    
    def add_funds(self, wallet_id: str, amount: float) -> bool:
        """Add funds to multi-sig wallet"""
        if wallet_id not in self.wallets:
            return False
        self.wallets[wallet_id].balance += amount
        return True
    
    def create_transaction(self, wallet_id: str, to: str, amount: float, creator: str) -> Optional[MultiSigTransaction]:
        """Create a pending transaction"""
        if wallet_id not in self.wallets:
            return None
        
        wallet = self.wallets[wallet_id]
        if creator not in wallet.owners:
            return None
        
        tx_id = f"TX{secrets.token_hex(8)}"
        
        tx = MultiSigTransaction(
            tx_id=tx_id,
            wallet_id=wallet_id,
            to=to,
            amount=amount,
            signatures=[],
            created_by=creator
        )
        
        self.pending_txs[tx_id] = tx
        return tx
    
    def sign_transaction(self, tx_id: str, signer: str, signature: str) -> bool:
        """Add signature to transaction"""
        if tx_id not in self.pending_txs:
            return False
        
        tx = self.pending_txs[tx_id]
        wallet = self.wallets[tx.wallet_id]
        
        if signer not in wallet.owners:
            return False
        
        # Check not already signed
        for s in tx.signatures:
            if s.startswith(signer + ":"):
                return False
        
        tx.signatures.append(f"{signer}:{signature}")
        return True
    
    def execute_transaction(self, tx_id: str) -> bool:
        """Execute a transaction if enough signatures"""
        if tx_id not in self.pending_txs:
            return False
        
        tx = self.pending_txs[tx_id]
        wallet = self.wallets[tx.wallet_id]
        
        if len(tx.signatures) < wallet.required_signatures:
            return False
        
        if wallet.balance < tx.amount:
            return False
        
        # Execute
        wallet.balance -= tx.amount
        tx.executed = True
        wallet.nonce += 1
        
        return True
    
    def get_pending_txs(self, wallet_id: str = None) -> List[Dict]:
        """Get pending transactions"""
        txs = self.pending_txs.values()
        if wallet_id:
            txs = [t for t in txs if t.wallet_id == wallet_id]
        return [t.to_dict() for t in txs if not t.executed]


# ========== EVENT SYSTEM ==========
class EventType:
    """Event type constants"""
    BLOCK_MINED = "block_mined"
    TRANSACTION = "transaction"
    NFT_MINTED = "nft_minted"
    NFT_TRANSFERRED = "nft_transferred"
    PROPOSAL_CREATED = "proposal_created"
    PROPOSAL_PASSED = "proposal_passed"
    VALIDATOR_JOINED = "validator_joined"
    VALIDATOR_SLASHED = "validator_slashed"
    STAKING_CHANGE = "staking_change"
    WALLET_CREATED = "wallet_created"


@dataclass
class WebhookEvent:
    """Event for webhook delivery"""
    event_type: str
    data: Dict
    timestamp: float = field(default_factory=time.time)
    delivered: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp,
            "delivered": self.delivered
        }


class EventManager:
    """Manages events and webhooks"""
    
    def __init__(self):
        self.webhooks: Dict[str, str] = {}  # url -> event_types (comma-separated)
        self.event_history: List[WebhookEvent] = []
        self.handlers: Dict[str, List[Callable]] = {}  # In-process handlers
    
    def register_webhook(self, url: str, event_types: List[str] = None):
        """Register a webhook URL"""
        if event_types is None:
            event_types = ["*"]  # All events
        self.webhooks[url] = ",".join(event_types)
    
    def remove_webhook(self, url: str):
        """Remove a webhook"""
        if url in self.webhooks:
            del self.webhooks[url]
    
    def register_handler(self, event_type: str, handler: Callable):
        """Register an in-process event handler"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
    
    def emit(self, event_type: str, data: Dict):
        """Emit an event"""
        event = WebhookEvent(event_type=event_type, data=data)
        self.event_history.append(event)
        
        # Call in-process handlers
        if event_type in self.handlers:
            for handler in self.handlers[event_type]:
                try:
                    handler(data)
                except Exception as e:
                    print(f"Handler error: {e}")
        
        # Also call "*" handlers
        if "*" in self.handlers:
            for handler in self.handlers["*"]:
                try:
                    handler(event_type, data)
                except Exception:
                    pass
        
        return event
    
    def get_webhooks_for_event(self, event_type: str) -> List[str]:
        """Get webhooks subscribed to an event"""
        matching = []
        for url, types in self.webhooks.items():
            if types == "*" or event_type in types.split(","):
                matching.append(url)
        return matching
    
    def get_event_history(self, event_type: str = None, limit: int = 100) -> List[Dict]:
        """Get event history"""
        events = self.event_history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return [e.to_dict() for e in events[-limit:]]


# ========== SMART CONTRACTS (BASIC) ==========
@dataclass
class SmartContract:
    """Simple smart contract"""
    contract_id: str
    owner: str
    code: str  # Simple script
    state: Dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "contract_id": self.contract_id,
            "owner": self.owner,
            "code": self.code,
            "state": self.state,
            "created_at": self.created_at
        }


class ContractRegistry:
    """Simple smart contract execution"""
    
    def __init__(self):
        self.contracts: Dict[str, SmartContract] = {}
    
    def deploy(self, owner: str, code: str, initial_state: Dict = None) -> SmartContract:
        """Deploy a new contract"""
        contract_id = f"CONTRACT{secrets.token_hex(8)}"
        
        contract = SmartContract(
            contract_id=contract_id,
            owner=owner,
            code=code,
            state=initial_state or {}
        )
        
        self.contracts[contract_id] = contract
        return contract
    
    def call(self, contract_id: str, function: str, args: Dict = None) -> Optional[Any]:
        """Execute a contract function"""
        if contract_id not in self.contracts:
            return None
        
        contract = self.contracts[contract_id]
        args = args or {}
        
        # Simple function dispatcher
        if function == "get":
            return contract.state.get(args.get("key"))
        elif function == "set":
            key = args.get("key")
            value = args.get("value")
            contract.state[key] = value
            return value
        elif function == "increment":
            key = args.get("key")
            contract.state[key] = contract.state.get(key, 0) + args.get("amount", 1)
            return contract.state[key]
        elif function == "transfer_ownership":
            new_owner = args.get("owner")
            contract.owner = new_owner
            return new_owner
        
        return None
    
    def get_contract(self, contract_id: str) -> Optional[SmartContract]:
        """Get contract by ID"""
        return self.contracts.get(contract_id)
    
    def get_all_contracts(self) -> List[Dict]:
        """Get all contracts"""
        return [c.to_dict() for c in self.contracts.values()]


# ========== TRANSACTION INDEXER ==========
class TransactionIndexer:
    """Indexes transactions for searching"""
    
    def __init__(self):
        self.by_sender: Dict[str, List[str]] = {}  # sender -> tx_hashes
        self.by_recipient: Dict[str, List[str]] = {}  # recipient -> tx_hashes
        self.by_type: Dict[str, List[str]] = {}  # tx_type -> tx_hashes
        self.by_amount: List[tuple] = []  # (amount, tx_hash)
        self.all_txs: Dict[str, Dict] = {}  # tx_hash -> tx_data
    
    def index(self, tx: Dict):
        """Index a transaction"""
        tx_hash = tx.get("hash")
        if not tx_hash:
            return
        
        self.all_txs[tx_hash] = tx
        
        # Index by sender
        sender = tx.get("sender")
        if sender:
            if sender not in self.by_sender:
                self.by_sender[sender] = []
            self.by_sender[sender].append(tx_hash)
        
        # Index by recipient
        recipient = tx.get("recipient")
        if recipient:
            if recipient not in self.by_recipient:
                self.by_recipient[recipient] = []
            self.by_recipient[recipient].append(tx_hash)
        
        # Index by type
        tx_type = tx.get("tx_type", "TRANSFER")
        if tx_type not in self.by_type:
            self.by_type[tx_type] = []
        self.by_type[tx_type].append(tx_hash)
        
        # Index by amount
        amount = tx.get("amount", 0)
        if amount > 0:
            self.by_amount.append((amount, tx_hash))
    
    def search_by_sender(self, sender: str, limit: int = 50) -> List[Dict]:
        """Search transactions by sender"""
        hashes = self.by_sender.get(sender, [])[-limit:]
        return [self.all_txs[h] for h in hashes if h in self.all_txs]
    
    def search_by_recipient(self, recipient: str, limit: int = 50) -> List[Dict]:
        """Search transactions by recipient"""
        hashes = self.by_recipient.get(recipient, [])[-limit:]
        return [self.all_txs[h] for h in hashes if h in self.all_txs]
    
    def search_by_type(self, tx_type: str, limit: int = 50) -> List[Dict]:
        """Search transactions by type"""
        hashes = self.by_type.get(tx_type, [])[-limit:]
        return [self.all_txs[h] for h in hashes if h in self.all_txs]
    
    def search_by_amount(self, min_amount: float = 0, max_amount: float = None, limit: int = 50) -> List[Dict]:
        """Search transactions by amount range"""
        results = [(a, h) for a, h in self.by_amount if a >= min_amount]
        if max_amount:
            results = [(a, h) for a, h in results if a <= max_amount]
        results.sort(reverse=True)
        results = results[:limit]
        return [self.all_txs[h] for _, h in results if h in self.all_txs]
    
    def search(self, sender: str = None, recipient: str = None, tx_type: str = None, 
               min_amount: float = 0, max_amount: float = None, limit: int = 50) -> List[Dict]:
        """Full-text search across all fields"""
        results = set()
        
        if sender:
            results.update(self.by_sender.get(sender, []))
        if recipient:
            results.update(self.by_recipient.get(recipient, []))
        if tx_type:
            results.update(self.by_type.get(tx_type, []))
        
        # Filter by amount
        if min_amount > 0 or max_amount:
            filtered = []
            for h in results:
                tx = self.all_txs.get(h, {})
                amt = tx.get("amount", 0)
                if amt >= min_amount:
                    if max_amount is None or amt <= max_amount:
                        filtered.append(h)
            results = set(filtered)
        
        results = list(results)[:limit]
        return [self.all_txs[h] for h in results if h in self.all_txs]


# ========== LIGHT CLIENT ==========
@dataclass
class LightClientState:
    """Simplified state for light clients"""
    block_hash: str
    block_height: int
    timestamp: float
    total_supply: float
    validator_set_hash: str
    
    def to_dict(self) -> Dict:
        return {
            "block_hash": self.block_hash,
            "block_height": self.block_height,
            "timestamp": self.timestamp,
            "total_supply": self.total_supply,
            "validator_set_hash": self.validator_set_hash
        }


class LightClient:
    """Light client for mobile/restricted devices"""
    
    def __init__(self):
        self.state: Optional[LightClientState] = None
        self.trusted_hash: str = ""
    
    def sync(self, block_hash: str, block_height: int, timestamp: float, 
             total_supply: float, validator_set: List[str]):
        """Sync from full node"""
        validator_hash = sha256(",".join(sorted(validator_set)))
        
        self.state = LightClientState(
            block_hash=block_hash,
            block_height=block_height,
            timestamp=timestamp,
            total_supply=total_supply,
            validator_set_hash=validator_hash
        )
        self.trusted_hash = block_hash
    
    def verify_transaction(self, tx: Dict, proof: List[str]) -> bool:
        """Verify transaction with merkle proof"""
        if not self.state:
            return False
        
        # Simplified - in real impl would verify merkle proof
        return len(proof) > 0
    
    def get_state(self) -> Optional[Dict]:
        """Get current synced state"""
        if self.state:
            return self.state.to_dict()
        return None