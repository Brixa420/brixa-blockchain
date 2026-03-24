"""
Role-Based Permissions & Validator Signatures Module
Implements: invisible wallets, role-based access, validator-signed commits
"""
import hashlib
import secrets
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from crypto import generate_keypair, get_address, sign, verify_signature, sha256


# ========== ROLE DEFINITIONS ==========
class Role:
    """Role constants"""
    PLAYER = "player"
    VALIDATOR = "validator"
    AI_NODE = "ai_node"
    ADMIN = "admin"


# ========== PERMISSION FLAGS ==========
class Permission:
    """Permission flags"""
    # Player permissions
    CAN_TRANSFER = "can_transfer"
    CAN_STAKE = "can_stake"
    CAN_VOTE = "can_vote"
    CAN_PARTY = "can_party"
    
    # Validator permissions
    CAN_VALIDATE = "can_validate"
    CAN_SIGN_BLOCKS = "can_sign_blocks"
    CAN_SUBMIT_BATCHES = "can_submit_batches"
    CANSlash_REPORT = "can_slash"
    
    # AI Node permissions
    CAN_SPAWN = "can_spawn"
    CAN_MEMORIZE = "can_memorize"
    CAN_NARRATE = "can_narrate"
    
    # Admin permissions
    CAN_UPGRADE = "can_upgrade"
    CAN_FREEZE = "can_freeze"
    CAN_MINT = "can_mint"


# Role to permissions mapping
ROLE_PERMISSIONS = {
    Role.PLAYER: [
        Permission.CAN_TRANSFER,
        Permission.CAN_STAKE,
        Permission.CAN_VOTE,
        Permission.CAN_PARTY,
    ],
    Role.VALIDATOR: [
        Permission.CAN_TRANSFER,
        Permission.CAN_STAKE,
        Permission.CAN_VOTE,
        Permission.CAN_VALIDATE,
        Permission.CAN_SIGN_BLOCKS,
        Permission.CAN_SUBMIT_BATCHES,
        Permission.CANSlash_REPORT,
    ],
    Role.AI_NODE: [
        Permission.CAN_TRANSFER,
        Permission.CAN_VALIDATE,
        Permission.CAN_SPAWN,
        Permission.CAN_MEMORIZE,
        Permission.CAN_NARRATE,
    ],
    Role.ADMIN: [
        Permission.CAN_TRANSFER,
        Permission.CAN_STAKE,
        Permission.CAN_VOTE,
        Permission.CAN_VALIDATE,
        Permission.CAN_SIGN_BLOCKS,
        Permission.CAN_SUBMIT_BATCHES,
        Permission.CANSlash_REPORT,
        Permission.CAN_UPGRADE,
        Permission.CAN_FREEZE,
        Permission.CAN_MINT,
    ],
}


# ========== INVISIBLE WALLET ==========
@dataclass
class InvisibleWallet:
    """Privacy-preserving wallet with stealth addresses"""
    view_key: str           # Can see incoming txns
    spend_key: str          # Can spend funds
    stealth_address: str    # Public address (derived)
    internal_address: str   # Full viewing capability
    created_at: float = field(default_factory=time.time)
    is_frozen: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "view_key": self.view_key,
            "spend_key": self.spend_key,
            "stealth_address": self.stealth_address,
            "internal_address": self.internal_address,
            "created_at": self.created_at,
            "is_frozen": self.is_frozen
        }


class InvisibleWalletManager:
    """
    Manages invisible/stealth wallets for privacy
    Uses cryptographic stealth address generation
    """
    
    def __init__(self):
        self.stealth_addresses: Dict[str, str] = {}  # stealth_addr -> internal_addr
        self.internal_wallets: Dict[str, InvisibleWallet] = {}  # internal_addr -> wallet
    
    def generate_stealth_address(self, user_id: str = None) -> InvisibleWallet:
        """
        Generate a new stealth/invisible wallet
        Uses a random view key and spend key derivation
        """
        # Generate random keys
        view_private, view_pub = generate_keypair()
        spend_private, spend_pub = generate_keypair()
        
        # Generate stealth address (public, shareable)
        # This is a hash of the view public key + spend public key
        stealth_data = f"{view_pub}:{spend_pub}:{secrets.token_hex(8)}"
        stealth_address = "0x" + sha256(stealth_data)[:40]
        
        # Internal address includes full key material (for spending)
        internal_address = get_address(spend_pub)
        
        # Create stealth address mapping
        self.stealth_addresses[stealth_address] = internal_address
        
        wallet = InvisibleWallet(
            view_key=view_private,
            spend_key=spend_private,
            stealth_address=stealth_address,
            internal_address=internal_address
        )
        
        self.internal_wallets[internal_address] = wallet
        
        return wallet
    
    def get_internal_address(self, stealth_address: str) -> Optional[str]:
        """Get internal address from stealth address"""
        return self.stealth_addresses.get(stealth_address)
    
    def get_wallet(self, internal_address: str) -> Optional[InvisibleWallet]:
        """Get wallet by internal address"""
        return self.internal_wallets.get(internal_address)
    
    def is_stealth_address(self, address: str) -> bool:
        """Check if address is a stealth address"""
        return address in self.stealth_addresses
    
    def freeze_wallet(self, internal_address: str) -> bool:
        """Freeze a wallet (admin function)"""
        if internal_address in self.internal_wallets:
            self.internal_wallets[internal_address].is_frozen = True
            return True
        return False
    
    def unfreeze_wallet(self, internal_address: str) -> bool:
        """Unfreeze a wallet (admin function)"""
        if internal_address in self.internal_wallets:
            self.internal_wallets[internal_address].is_frozen = False
            return True
        return False


# ========== ROLE-BASED ACCESS CONTROL ==========
@dataclass
class UserPermissions:
    """User's role and permissions"""
    address: str
    role: str
    permissions: List[str]
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    frozen: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "address": self.address,
            "role": self.role,
            "permissions": self.permissions,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "frozen": self.frozen
        }


class RoleManager:
    """
    Manages role-based permissions for players, validators, and AI nodes
    """
    
    def __init__(self):
        self.users: Dict[str, UserPermissions] = {}
        self.role_requests: List[Dict] = []  # Pending role requests
    
    def assign_role(self, address: str, role: str) -> bool:
        """Assign a role to an address"""
        if role not in ROLE_PERMISSIONS:
            return False
        
        permissions = ROLE_PERMISSIONS[role].copy()
        
        self.users[address] = UserPermissions(
            address=address,
            role=role,
            permissions=permissions
        )
        
        return True
    
    def get_role(self, address: str) -> Optional[str]:
        """Get role for an address"""
        if address in self.users:
            return self.users[address].role
        return None
    
    def get_permissions(self, address: str) -> List[str]:
        """Get permissions for an address"""
        if address in self.users:
            return self.users[address].permissions
        # Default to no role - basic player permissions
        return []
    
    def has_permission(self, address: str, permission: str) -> bool:
        """Check if address has a specific permission"""
        if address in self.users:
            user = self.users[address]
            if user.frozen:
                return False
            return permission in user.permissions
        # Default players have limited permissions
        return permission in ROLE_PERMISSIONS.get(Role.PLAYER, [])
    
    def upgrade_role(self, address: str, new_role: str) -> bool:
        """Upgrade a user's role (requires governance approval in real impl)"""
        return self.assign_role(address, new_role)
    
    def freeze_user(self, address: str) -> bool:
        """Freeze a user's permissions"""
        if address in self.users:
            self.users[address].frozen = True
            return True
        return False
    
    def unfreeze_user(self, address: str) -> bool:
        """Unfreeze a user's permissions"""
        if address in self.users:
            self.users[address].frozen = False
            return True
        return False
    
    def get_users_by_role(self, role: str) -> List[UserPermissions]:
        """Get all users with a specific role"""
        return [u for u in self.users.values() if u.role == role]
    
    def request_role(self, address: str, requested_role: str, reason: str = "") -> Dict:
        """Request a role upgrade"""
        current_role = self.get_role(address) or "none"
        request = {
            "address": address,
            "current_role": current_role,
            "requested_role": requested_role,
            "reason": reason,
            "timestamp": time.time(),
            "status": "pending"
        }
        self.role_requests.append(request)
        return request
    
    def get_user_info(self, address: str) -> Optional[Dict]:
        """Get full user info"""
        if address in self.users:
            return self.users[address].to_dict()
        
        # Return default player info
        return {
            "address": address,
            "role": Role.PLAYER,
            "permissions": ROLE_PERMISSIONS[Role.PLAYER],
            "created_at": time.time(),
            "last_active": time.time(),
            "frozen": False
        }


# ========== VALIDATOR SIGNATURES ==========
@dataclass
class BlockSignature:
    """Validator signature on a block"""
    validator: str
    block_hash: str
    signature: str
    timestamp: float
    height: int
    
    def to_dict(self) -> Dict:
        return {
            "validator": self.validator,
            "block_hash": self.block_hash,
            "signature": self.signature,
            "timestamp": self.timestamp,
            "height": self.height
        }


@dataclass
class SignedCommit:
    """Validator-confirmed commit (for world updates)"""
    commit_id: str
    validator_signatures: List[Dict]  # List of {validator, signature}
    required_signatures: int
    content_hash: str
    content_type: str  # "block", "world_update", "state_commit"
    created_at: float
    executed: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "commit_id": self.commit_id,
            "validator_signatures": self.validator_signatures,
            "required_signatures": self.required_signatures,
            "content_hash": self.content_hash,
            "content_type": self.content_type,
            "created_at": self.created_at,
            "executed": self.executed
        }


class ValidatorSignatureManager:
    """
    Manages validator signatures for blocks and world updates
    Implements validator-confirmed commit model
    """
    
    def __init__(self, required_signatures: int = 1):
        self.required_signatures = required_signatures
        self.block_signatures: Dict[int, List[BlockSignature]] = {}  # height -> signatures
        self.commits: Dict[str, SignedCommit] = {}  # commit_id -> commit
        self.validator_keys: Dict[str, str] = {}  # address -> private_key
    
    def register_validator_key(self, address: str, private_key: str):
        """Register validator's private key for signing"""
        self.validator_keys[address] = private_key
    
    def sign_block(self, validator: str, block_hash: str, height: int, private_key: str) -> BlockSignature:
        """Validator signs a block"""
        if validator not in self.validator_keys:
            raise ValueError(f"Validator {validator} not registered")
        
        # Sign the block hash
        signature = sign(private_key, f"{block_hash}:{height}")
        
        sig = BlockSignature(
            validator=validator,
            block_hash=block_hash,
            signature=signature,
            timestamp=time.time(),
            height=height
        )
        
        if height not in self.block_signatures:
            self.block_signatures[height] = []
        
        self.block_signatures[height].append(sig)
        
        return sig
    
    def verify_block_signature(self, height: int, validator: str) -> bool:
        """Verify a validator has signed a block"""
        if height not in self.block_signatures:
            return False
        
        for sig in self.block_signatures[height]:
            if sig.validator == validator:
                return True
        return False
    
    def get_block_signatures(self, height: int) -> List[Dict]:
        """Get all signatures for a block"""
        if height in self.block_signatures:
            return [s.to_dict() for s in self.block_signatures[height]]
        return []
    
    def has_quorum(self, height: int) -> bool:
        """Check if block has enough signatures for quorum"""
        if height not in self.block_signatures:
            return False
        return len(self.block_signatures[height]) >= self.required_signatures
    
    def create_commit(self, content_hash: str, content_type: str, required_validators: int = None) -> SignedCommit:
        """Create a new commit requiring validator signatures"""
        if required_validators is None:
            required_validators = self.required_signatures
        
        commit_id = sha256(f"{content_hash}:{time.time()}:{secrets.token_hex(8)}")
        
        commit = SignedCommit(
            commit_id=commit_id,
            validator_signatures=[],
            required_signatures=required_validators,
            content_hash=content_hash,
            content_type=content_type,
            created_at=time.time()
        )
        
        self.commits[commit_id] = commit
        return commit
    
    def sign_commit(self, commit_id: str, validator: str, private_key: str) -> bool:
        """Add validator signature to a commit"""
        if commit_id not in self.commits:
            return False
        
        if validator not in self.validator_keys:
            return False
        
        commit = self.commits[commit_id]
        
        # Check if already signed
        for s in commit.validator_signatures:
            if s["validator"] == validator:
                return False
        
        # Sign the commit
        signature = sign(private_key, f"{commit.commit_id}:{commit.content_hash}")
        
        commit.validator_signatures.append({
            "validator": validator,
            "signature": signature,
            "timestamp": time.time()
        })
        
        return True
    
    def can_execute_commit(self, commit_id: str) -> bool:
        """Check if commit has enough signatures to execute"""
        if commit_id not in self.commits:
            return False
        
        commit = self.commits[commit_id]
        return len(commit.validator_signatures) >= commit.required_signatures
    
    def execute_commit(self, commit_id: str) -> bool:
        """Execute a commit that has reached quorum"""
        if not self.can_execute_commit(commit_id):
            return False
        
        commit = self.commits[commit_id]
        commit.executed = True
        return True
    
    def get_commit(self, commit_id: str) -> Optional[SignedCommit]:
        """Get a commit by ID"""
        return self.commits.get(commit_id)
    
    def get_pending_commits(self) -> List[Dict]:
        """Get all pending commits"""
        return [c.to_dict() for c in self.commits.values() if not c.executed]


# ========== CONFLICT RESOLUTION ==========
class ConflictResolver:
    """
    Resolves conflicts via DPoS validator voting
    """
    
    def __init__(self, signature_manager: ValidatorSignatureManager):
        self.signature_manager = signature_manager
        self.disputes: Dict[str, Dict] = {}
    
    def create_dispute(self, disputant: str, claim: str, evidence: str) -> str:
        """Create a new dispute"""
        dispute_id = sha256(f"{disputant}:{claim}:{time.time()}")
        
        self.disputes[dispute_id] = {
            "dispute_id": dispute_id,
            "disputant": disputant,
            "claim": claim,
            "evidence": evidence,
            "votes": [],
            "resolved": False,
            "created_at": time.time()
        }
        
        return dispute_id
    
    def vote_on_dispute(self, dispute_id: str, validator: str, vote: bool, weight: int = 1) -> bool:
        """Vote on a dispute (validators only)"""
        if dispute_id not in self.disputes:
            return False
        
        dispute = self.disputes[dispute_id]
        
        # Check if already voted
        for v in dispute["votes"]:
            if v["validator"] == validator:
                return False
        
        dispute["votes"].append({
            "validator": validator,
            "vote": vote,
            "weight": weight,
            "timestamp": time.time()
        })
        
        return True
    
    def resolve_dispute(self, dispute_id: str) -> Optional[Dict]:
        """Resolve a dispute by majority vote"""
        if dispute_id not in self.disputes:
            return None
        
        dispute = self.disputes[dispute_id]
        
        if dispute["resolved"]:
            return dispute
        
        # Count votes
        yes_weight = sum(v["weight"] for v in dispute["votes"] if v["vote"])
        no_weight = sum(v["weight"] for v in dispute["votes"] if not v["vote"])
        
        dispute["yes_votes"] = yes_weight
        dispute["no_votes"] = no_weight
        dispute["resolved"] = True
        dispute["outcome"] = "approved" if yes_weight > no_weight else "rejected"
        dispute["resolved_at"] = time.time()
        
        return dispute
    
    def get_dispute(self, dispute_id: str) -> Optional[Dict]:
        """Get dispute by ID"""
        return self.disputes.get(dispute_id)
    
    def get_pending_disputes(self) -> List[Dict]:
        """Get all unresolved disputes"""
        return [d for d in self.disputes.values() if not d["resolved"]]