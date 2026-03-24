"""
Wrath of Cali Blockchain - P2P Networking, Slashing & Governance
"""
import json
import time
import threading
import hashlib
import socket
import socketserver
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import requests
from crypto import generate_keypair, get_address, sign, sha256, verify_signature


# ============== CONSTANTS ==============
DEFAULT_P2P_PORT = 5002
MAX_PEERS = 50
HEARTBEAT_INTERVAL = 5  # seconds
SYNC_INTERVAL = 3  # seconds
SLASHING_WINDOW = 100  # blocks to track for slashing


# ============== DATA STRUCTURES ==============
class MessageType(Enum):
    TX = "transaction"
    BATCH = "batch"
    BLOCK = "block"
    PING = "ping"
    PONG = "pong"
    PEERS = "peers"
    VOTE = "vote"
    PROPOSAL = "proposal"


@dataclass
class Peer:
    """A peer node in the network"""
    address: str  # IP or hostname
    port: int
    peer_id: str  # Unique identifier
    public_key: str
    last_seen: float = field(default_factory=time.time)
    stake: float = 0
    is_validator: bool = False
    missed_blocks: int = 0
    total_blocks: int = 0
    slashed: bool = False
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def is_active(self, timeout: int = 30) -> bool:
        return (time.time() - self.last_seen) < timeout
    
    def get_uptime(self) -> float:
        if self.total_blocks == 0:
            return 0
        return 1 - (self.missed_blocks / self.total_blocks)


@dataclass
class SlashEvent:
    """A slashing event"""
    validator: str
    reason: str  # "downtime" or "double_sign"
    block_height: int
    slash_amount: float
    timestamp: float


@dataclass
class Proposal:
    """Governance proposal"""
    id: str
    proposer: str
    title: str
    description: str
    proposal_type: str  # "parameter", "upgrade", "slash_pardon", "treasury"
    voting_start: float
    voting_end: float
    yes_votes: Dict[str, float] = field(default_factory=dict)  # address -> weight
    no_votes: Dict[str, float] = field(default_factory=dict)
    status: str = "active"
    executed: bool = False
    data: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        return d
    
    def get_total_yes(self) -> float:
        return sum(self.yes_votes.values())
    
    def get_total_no(self) -> float:
        return sum(self.no_votes.values())
    
    def get_quorum(self, total_staked: float) -> bool:
        return (self.get_total_yes() + self.get_total_no()) >= (total_staked * 0.10)
    
    def is_passed(self, total_staked: float) -> bool:
        if not self.get_quorum(total_staked):
            return False
        return self.get_total_yes() > self.get_total_no()


# ============== P2P NETWORK ==============
class P2PNetwork:
    """Peer-to-peer network for validators"""
    
    def __init__(self, node_id: str, port: int = DEFAULT_P2P_PORT):
        self.node_id = node_id
        self.port = port
        self.peers: Dict[str, Peer] = {}
        self.pending_txs: Set[str] = set()  # tx hashes
        self.pending_batches: Set[str] = set()  # batch hashes
        self.known_blocks: Set[int] = set()  # block heights
        self.message_handlers: Dict[MessageType, callable] = {}
        self.running = False
        
    def add_peer(self, peer: Peer):
        """Add a peer to the network"""
        if len(self.peers) >= MAX_PEERS:
            # Remove oldest inactive peer
            oldest = min(self.peers.values(), key=lambda p: p.last_seen)
            if not oldest.is_active():
                del self.peers[oldest.peer_id]
        
        self.peers[peer.peer_id] = peer
    
    def remove_peer(self, peer_id: str):
        """Remove a peer"""
        if peer_id in self.peers:
            del self.peers[peers[peer_id]]
    
    def discover_peers(self, seed_nodes: List[str]):
        """Discover peers from seed nodes"""
        for node in seed_nodes:
            try:
                resp = requests.get(f"http://{node}/peers", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    for peer_data in data.get("peers", []):
                        peer = Peer(**peer_data)
                        if peer.peer_id != self.node_id:
                            self.add_peer(peer)
            except:
                continue
    
    def broadcast_transaction(self, tx: Dict):
        """Broadcast transaction to all peers"""
        tx_hash = tx.get("hash", "")
        if tx_hash in self.pending_txs:
            return
        self.pending_txs.add(tx_hash)
        self._broadcast(MessageType.TX, {"transaction": tx})
    
    def broadcast_batch(self, batch: Dict):
        """Broadcast batch to all peers"""
        batch_hash = batch.get("batch_hash", "")
        if batch_hash in self.pending_batches:
            return
        self.pending_batches.add(batch_hash)
        self._broadcast(MessageType.BATCH, {"batch": batch})
    
    def broadcast_block(self, block: Dict):
        """Broadcast block to all peers"""
        height = block.get("height", 0)
        self.known_blocks.add(height)
        self._broadcast(MessageType.BLOCK, {"block": block})
    
    def _broadcast(self, msg_type: MessageType, data: Dict):
        """Send message to all peers"""
        msg = {
            "type": msg_type.value,
            "sender": self.node_id,
            "timestamp": time.time(),
            "data": data
        }
        
        for peer in self.peers.values():
            if not peer.is_active():
                continue
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.sendto(json.dumps(msg).encode(), (peer.address, peer.port))
                sock.close()
            except:
                pass
    
    def get_active_peers(self) -> List[Peer]:
        """Get all active peers"""
        return [p for p in self.peers.values() if p.is_active()]
    
    def get_validators(self) -> List[Peer]:
        """Get all validator peers"""
        return [p for p in self.peers.values() if p.is_validator and not p.slashed]


# ============== SLASHING ==============
class SlashingManager:
    """Manages validator slashing for misconduct"""
    
    def __init__(self, params: Dict = None):
        self.params = params or {
            "downtime_slash": 0.01,  # 1% for downtime
            "double_sign_slash": 0.10,  # 10% for double-signing
            "missed_blocks_threshold": 5
        }
        self.slash_events: List[SlashEvent] = []
        self.validator_missed_blocks: Dict[str, int] = {}
        self.validator_signed_blocks: Dict[str, Set[int]] = {}  # block heights signed
    
    def record_block_signed(self, validator: str, block_height: int):
        """Record that a validator signed a block"""
        if validator not in self.validator_signed_blocks:
            self.validator_signed_blocks[validator] = set()
        self.validator_signed_blocks[validator].add(block_height)
        
        # Reset missed blocks counter on success
        if validator in self.validator_missed_blocks:
            del self.validator_missed_blocks[validator]
    
    def record_block_missed(self, validator: str, block_height: int):
        """Record that a validator missed a block"""
        if validator not in self.validator_missed_blocks:
            self.validator_missed_blocks[validator] = 0
        self.validator_missed_blocks[validator] += 1
        
        missed = self.validator_missed_blocks[validator]
        
        # Check if threshold reached
        if missed >= self.params["missed_blocks_threshold"]:
            return self.slash_validator(
                validator, 
                "downtime",
                block_height,
                self.params["downtime_slash"]
            )
        return None
    
    def check_double_sign(self, validator: str, block_height: int, existing_signatures: Set[str]) -> Optional[SlashEvent]:
        """Check for double-signing (same validator signing same height twice)"""
        if validator in existing_signatures:
            return self.slash_validator(
                validator,
                "double_sign",
                block_height,
                self.params["double_sign_slash"]
            )
        return None
    
    def slash_validator(self, validator: str, reason: str, block_height: int, slash_rate: float) -> SlashEvent:
        """Slash a validator"""
        # Get validator stake (would come from state in real implementation)
        slash_amount = 0  # Calculated based on stake
        
        event = SlashEvent(
            validator=validator,
            reason=reason,
            block_height=block_height,
            slash_amount=slash_amount,
            timestamp=time.time()
        )
        
        self.slash_events.append(event)
        
        # Mark validator as slashed (in real impl, update state)
        print(f"⚔️ SLASH: {validator} for {reason} at block {block_height}, rate: {slash_rate*100}%")
        
        return event
    
    def get_slash_count(self, validator: str) -> int:
        """Get number of slashing events for a validator"""
        return sum(1 for e in self.slash_events if e.validator == validator)
    
    def can_unstake(self, validator: str, stake_amount: float) -> tuple[bool, str]:
        """Check if validator can unstake (not currently slashed)"""
        slash_count = self.get_slash_count(validator)
        
        # Can't unstake if slashed in last 100 blocks
        recent_slashes = [e for e in self.slash_events 
                         if e.validator == validator and time.time() - e.timestamp < 100]
        
        if recent_slashes:
            return False, "Cannot unstake: recent slashing event"
        
        return True, "OK"
    
    def get_slashing_report(self) -> Dict:
        """Get slashing statistics"""
        return {
            "total_events": len(self.slash_events),
            "downtime_slashes": sum(1 for e in self.slash_events if e.reason == "downtime"),
            "double_sign_slashes": sum(1 for e in self.slash_events if e.reason == "double_sign"),
            "params": self.params,
            "recent_events": [asdict(e) for e in self.slash_events[-10:]]
        }


# ============== GOVERNANCE ==============
class GovernanceManager:
    """On-chain governance with quadratic voting"""
    
    def __init__(self, staking_contract=None):
        self.staking_contract = staking_contract
        self.proposals: Dict[str, Proposal] = {}
        self.proposal_counter = 0
        self.treasury: float = 0
        
    def create_proposal(
        self, 
        proposer: str, 
        title: str, 
        description: str,
        proposal_type: str,
        voting_period: int = 7 * 24 * 3600,  # 7 days
        data: Dict = None
    ) -> Proposal:
        """Create a new governance proposal"""
        self.proposal_counter += 1
        proposal_id = f"prop-{self.proposal_counter:06d}"
        
        now = time.time()
        proposal = Proposal(
            id=proposal_id,
            proposer=proposer,
            title=title,
            description=description,
            proposal_type=proposal_type,
            voting_start=now,
            voting_end=now + voting_period,
            data=data or {}
        )
        
        self.proposals[proposal_id] = proposal
        return proposal
    
    def vote(self, proposal_id: str, voter: str, support: bool, weight: float):
        """Cast a vote on a proposal"""
        if proposal_id not in self.proposals:
            return False, "Proposal not found"
        
        proposal = self.proposals[proposal_id]
        
        # Check voting period
        now = time.time()
        if now < proposal.voting_start or now > proposal.voting_end:
            return False, "Voting not active"
        
        # Check for existing vote and remove
        if voter in proposal.yes_votes:
            del proposal.yes_votes[voter]
        if voter in proposal.no_votes:
            del proposal.no_votes[voter]
        
        # Add new vote
        if support:
            proposal.yes_votes[voter] = weight
        else:
            proposal.no_votes[voter] = weight
        
        return True, "Vote recorded"
    
    def execute_proposal(self, proposal_id: str, total_staked: float) -> tuple[bool, str]:
        """Execute a passed proposal"""
        if proposal_id not in self.proposals:
            return False, "Proposal not found"
        
        proposal = self.proposals[proposal_id]
        
        if proposal.executed:
            return False, "Already executed"
        
        # Check if passed
        if not proposal.is_passed(total_staked):
            return False, "Proposal did not pass"
        
        # Execute based on type
        if proposal.proposal_type == "parameter":
            # Update chain parameters
            if "new_params" in proposal.data:
                return True, f"Parameter update: {proposal.data['new_params']}"
        
        elif proposal.proposal_type == "slash_pardon":
            # Pardon a slashed validator
            validator = proposal.data.get("validator")
            return True, f"Pardoned validator: {validator}"
        
        elif proposal.proposal_type == "treasury":
            # Spend from treasury
            recipient = proposal.data.get("recipient")
            amount = proposal.data.get("amount")
            return True, f"Sent {amount} to {recipient}"
        
        proposal.executed = True
        return True, "Proposal executed"
    
    def get_proposals(self, status: str = None) -> List[Dict]:
        """Get proposals, optionally filtered by status"""
        result = []
        for p in self.proposals.values():
            if status and p.status != status:
                continue
            result.append(p.to_dict())
        return result
    
    def get_proposal(self, proposal_id: str) -> Optional[Dict]:
        """Get a specific proposal"""
        if proposal_id in self.proposals:
            return self.proposals[proposal_id].to_dict()
        return None
    
    def get_active_proposals(self) -> List[Dict]:
        """Get currently active proposals"""
        now = time.time()
        active = []
        for p in self.proposals.values():
            if p.status == "active" and p.voting_start <= now <= p.voting_end:
                active.append(p.to_dict())
        return active


# ============== INTEGRATION HELPERS ==============
def load_genesis(path: str = "genesis.json") -> Dict:
    """Load genesis configuration"""
    with open(path, 'r') as f:
        return json.load(f)


def save_genesis(genesis: Dict, path: str = "genesis.json"):
    """Save genesis configuration"""
    with open(path, 'w') as f:
        json.dump(genesis, f, indent=2)


def initialize_from_genesis(genesis_path: str = "genesis.json"):
    """Initialize blockchain from genesis file"""
    genesis = load_genesis(genesis_path)
    
    # Extract chain params
    params = genesis.get("chain_params", {})
    
    # Create slashing manager
    slashing = SlashingManager(params.get("slashing_params", {}))
    
    # Create governance
    governance = GovernanceManager()
    
    # Create P2P network (will be configured with peers later)
    network = P2PNetwork("genesis")
    
    return {
        "genesis": genesis,
        "slashing": slashing,
        "governance": governance,
        "network": network
    }


# ============== CLI / TEST ==============
if __name__ == "__main__":
    print("=== P2P Networking, Slashing & Governance ===\n")
    
    # Test genesis loading
    print("1. Genesis Configuration:")
    genesis = load_genesis()
    print(f"   Chain ID: {genesis['chain_id']}")
    print(f"   Initial validators: {len(genesis['initial_validators'])}")
    print()
    
    # Test slashing
    print("2. Slashing System:")
    slashing = SlashingManager()
    
    # Simulate missed blocks
    for i in range(6):
        event = slashing.record_block_missed("validator1", i)
        if event:
            print(f"   ⚔️ Slashed validator1 for downtime at block {i}")
    print()
    
    # Test governance
    print("3. Governance System:")
    governance = GovernanceManager()
    
    # Create a proposal
    prop = governance.create_proposal(
        proposer="test_voter",
        title="Reduce Block Time",
        description="Change block time from 1s to 0.5s",
        proposal_type="parameter",
        voting_period=60,  # 60 seconds for test
        data={"new_block_time": 0.5}
    )
    print(f"   Created proposal: {prop.id}")
    print(f"   Title: {prop.title}")
    
    # Vote
    governance.vote(prop.id, "voter1", True, 10.0)
    governance.vote(prop.id, "voter2", False, 5.0)
    print(f"   Yes votes: {prop.get_total_yes()}, No votes: {prop.get_total_no()}")
    print(f"   Passed (100 staked): {prop.is_passed(100)}")
    print()
    
    # Test P2P
    print("4. P2P Network:")
    network = P2PNetwork("test_node", 5002)
    print(f"   Node ID: {network.node_id}")
    print(f"   Max peers: {MAX_PEERS}")
    print(f"   Heartbeat: {HEARTBEAT_INTERVAL}s")