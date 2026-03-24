"""
Wrath of Cali Blockchain - Main Node
The primary block producer that receives batches from validators
"""
import os
import json
import time
import threading
import hashlib
from typing import Dict, List, Any, Optional
from dataclasses import asdict
from flask import Flask, request, jsonify
from flask_cors import CORS
from core import Block, Transaction, Batch, BlockchainState, sha256
from crypto import generate_keypair, get_address, sign, verify_signature
from economics import (
    EconomicController, StakingRewards, GovernanceWeighting, 
    AntiWhaleMechanisms, BLOCKS_PER_ERA
)
from p2p import (
    P2PNetwork, SlashingManager, GovernanceManager, 
    load_genesis, DEFAULT_P2P_PORT
)
from roles import (
    RoleManager, InvisibleWalletManager, ValidatorSignatureManager,
    ConflictResolver, Role, Permission
)
from nft import (
    NFTManager, MultiSigManager, EventManager, ContractRegistry,
    TransactionIndexer, LightClient, EventType
)
from wallet_lib import (
    Mnemonic, HDWallet, WalletManager, WalletClient, WalletType,
    WalletBackup, TransactionBuilder, WalletUI
)
from wallet_recovery import (
    RecoveryManager, RecoveryMethod, CloudBackup
)
from passkey import PasskeyManager, SimulatedPasskey, PasskeyRecovery
from oauth import GoogleOAuthManager, SimulatedGoogleLogin

# Configuration
MAIN_NODE_URL = "http://localhost:5001"
MINIMUM_STAKE = 1000  # Minimum Calicos to be a validator
MINIMUM_STAKE = 1000  # Minimum Calicos to be a validator
BLOCK_TIME = 1  # 1 second block times
MAX_BATCHES_PER_BLOCK = 100
MAX_TRANSACTIONS_PER_BATCH = 1000

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Blockchain data
chain: List[Block] = []
state = BlockchainState()
pending_transactions: List[Dict] = []
pending_batches: List[Batch] = []
current_validator_key = None
current_validator_addr = None

# Economic controller
economics = EconomicController()
blocks_this_era = 0

# P2P, Slashing, and Governance
genesis_config = load_genesis()
p2p_network = P2PNetwork("main_node", DEFAULT_P2P_PORT)
slashing = SlashingManager(genesis_config.get("chain_params", {}).get("slashing_params", {}))
governance = GovernanceManager()

# Role & Permission Managers
role_manager = RoleManager()
wallet_manager = InvisibleWalletManager()
validator_sigs = ValidatorSignatureManager(required_signatures=1)
conflict_resolver = ConflictResolver(validator_sigs)

# NFT, Multi-sig, Events, Contracts, Indexer
nft_manager = NFTManager()
multisig_manager = MultiSigManager()
event_manager = EventManager()
contract_registry = ContractRegistry()
tx_indexer = TransactionIndexer()
light_client = LightClient()

# Wallet Infrastructure
wallet_manager = WalletManager()
wallet_client = WalletClient(MAIN_NODE_URL)
recovery_manager = RecoveryManager()
cloud_backup = CloudBackup()
passkey_manager = PasskeyManager()
oauth_manager = GoogleOAuthManager()


def init_genesis():
    """Initialize genesis block with initial balances"""
    global current_validator_key, current_validator_addr
    
    # Generate validator key
    current_validator_key, pub = generate_keypair()
    current_validator_addr = get_address(pub)
    
    # Initial balances - 100M total supply
    initial_balances = {
        current_validator_addr: 100_000_000,  # All to validator initially
    }
    
    genesis = Block.create_genesis(initial_balances, current_validator_addr)
    chain.append(genesis)
    
    # Initialize state from genesis
    for tx in genesis.transactions:
        state.add_balance(tx["recipient"], tx["amount"])
    
    print(f"Genesis block created: {genesis.hash}")
    print(f"Validator address: {current_validator_addr}")


def create_block() -> Block:
    """Create a new block with pending batches"""
    prev_block = chain[-1]
    height = prev_block.height + 1
    
    # Get up to MAX_BATCHES_PER_BLOCK batches
    batches_to_include = pending_batches[:MAX_BATCHES_PER_BLOCK]
    batch_hashes = [b.batch_hash for b in batches_to_include]
    
    # Collect all transactions from batches
    all_transactions = []
    for batch in batches_to_include:
        for tx_hash in batch.transactions:
            # Find the transaction in pending_transactions
            for tx in pending_transactions:
                if tx.get("hash") == tx_hash:
                    all_transactions.append(tx)
                    break
    
    # Calculate merkle root
    if all_transactions:
        merkle = sha256(",".join([t["hash"] for t in all_transactions]))
    else:
        merkle = sha256("")
    
    block = Block(
        height=height,
        previous_hash=prev_block.hash,
        timestamp=time.time(),
        validator=current_validator_addr,
        batch_hashes=batch_hashes,
        transactions=all_transactions,
        merkle_root=merkle
    )
    
    # Remove used batches and transactions
    used_batch_hashes = set(batch_hashes)
    pending_batches[:] = [b for b in pending_batches if b.batch_hash not in used_batch_hashes]
    
    used_tx_hashes = set(t["hash"] for t in all_transactions)
    pending_transactions[:] = [t for t in pending_transactions if t.get("hash") not in used_tx_hashes]
    
    # Apply transactions to state
    for tx in all_transactions:
        apply_transaction(tx)
    
    # Process block economics
    global blocks_this_era
    blocks_this_era += 1
    
    # Check for era change
    if blocks_this_era >= BLOCKS_PER_ERA:
        era_result = economics.process_era_change()
        blocks_this_era = 0
        print(f"🔄 Era {era_result['new_era']} started! New emission: {era_result['new_emission']:.2f}")
    
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
            # Fee goes to validator (simplified - could go to fee pool)
            return True
    
    elif tx_type == "STAKE":
        sender = tx.get("sender")
        amount = tx.get("amount", 0)
        
        if state.stake(sender, amount):
            # Add to validators if not already
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
            state.validators[sender]["staked"] = state.stakes.get(sender, 0)
            return True
    
    elif tx_type == "GENESIS":
        # Already handled in genesis creation
        return True
    
    return False


def block_producer_loop():
    """Background thread that produces blocks every second"""
    while True:
        time.sleep(BLOCK_TIME)
        if pending_batches or pending_transactions:
            block = create_block()
            print(f"Block #{block.height} created: {block.hash} ({len(block.transactions)} txs)")


# API Endpoints

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({"status": "ok", "height": len(chain)})


@app.route('/chain', methods=['GET'])
def get_chain():
    """Get chain summary"""
    return jsonify({
        "blocks": len(chain),
        "height": len(chain) - 1 if chain else 0,
        "total_supply": 100000000,
        "validator": current_validator_addr
    })


@app.route('/block/<int:height>', methods=['GET'])
def get_block(height: int):
    """Get block by height"""
    if 0 <= height < len(chain):
        return jsonify(chain[height].to_dict())
    return jsonify({"error": "Block not found"}), 404


@app.route('/block/latest', methods=['GET'])
def get_latest_block():
    """Get latest block"""
    return jsonify(chain[-1].to_dict())


@app.route('/transaction/<tx_hash>', methods=['GET'])
def get_transaction(tx_hash: str):
    """Get transaction by hash"""
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
    """Get balance of an address"""
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
    """Broadcast a new transaction"""
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
    
    # Basic validation
    if tx.tx_type == "TRANSFER":
        balance = state.get_balance(tx.sender)
        if balance < tx.amount + tx.fee:
            return jsonify({"error": "Insufficient balance"}), 400
    
    # Add to pending
    tx_dict = tx.to_dict()
    tx_dict["hash"] = tx.get_hash()
    pending_transactions.append(tx_dict)
    
    return jsonify({"status": "accepted", "hash": tx_dict["hash"]})


@app.route('/batch', methods=['POST'])
def submit_batch():
    """Validator submits a batch of transactions"""
    data = request.json
    
    validator = data.get("validator")
    tx_hashes = data.get("transactions", [])
    signature = data.get("signature")
    
    # Validate validator is staked
    if state.stakes.get(validator, 0) < MINIMUM_STAKE:
        return jsonify({"error": "Validator not staked enough"}), 400
    
    # Validate all transactions exist
    valid_hashes = set()
    for tx in pending_transactions:
        valid_hashes.add(tx.get("hash"))
    
    for h in tx_hashes:
        if h not in valid_hashes:
            return jsonify({"error": f"Transaction {h} not found"}), 400
    
    # Create and add batch
    batch = Batch(
        validator=validator,
        transactions=tx_hashes,
        batch_hash="",  # Will be computed
        timestamp=time.time(),
        signature=signature
    )
    batch.batch_hash = sha256(f"{batch.validator}:{','.join(tx_hashes)}:{batch.timestamp}")
    
    pending_batches.append(batch)
    
    # Update validator stats
    if validator in state.validators:
        state.validators[validator]["batches_submitted"] = \
            state.validators[validator].get("batches_submitted", 0) + 1
    
    return jsonify({"status": "accepted", "batch_hash": batch.batch_hash})


@app.route('/validators', methods=['GET'])
def get_validators():
    """Get list of active validators"""
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
    """Get pending transactions and batches"""
    return jsonify({
        "transactions": len(pending_transactions),
        "batches": len(pending_batches)
    })


@app.route('/faucet', methods=['POST'])
def faucet():
    """Get test funds from faucet"""
    data = request.json
    address = data.get("address")
    
    # Give 10000 Calicos from validator
    validator_addr = current_validator_addr
    
    if state.subtract_balance(validator_addr, 10000):
        state.add_balance(address, 10000)
        return jsonify({"status": "funded", "amount": 10000})
    return jsonify({"error": "Faucet empty"}), 500


@app.route('/wallet/create', methods=['POST'])
def create_wallet():
    """Create a new wallet"""
    priv, pub = generate_keypair()
    addr = get_address(pub)
    return jsonify({
        "address": addr,
        "private_key": priv,
        "public_key": pub
    })


@app.route('/wallet/transfer', methods=['POST'])
def create_transfer():
    """Create and broadcast a transfer transaction"""
    data = request.json
    sender = data.get("sender")
    private_key = data.get("private_key")
    recipient = data.get("recipient")
    amount = float(data.get("amount", 0))
    fee = float(data.get("fee", 0.01))
    
    # Check anti-whale tax on large holders
    sender_balance = state.get_balance(sender)
    whale_tax = AntiWhaleMechanisms.get_transfer_tax(sender_balance, amount)
    
    tx = Transaction.create_transfer(sender, recipient, amount, private_key, fee)
    tx_dict = tx.to_dict()
    tx_dict["hash"] = tx.get_hash()
    tx_dict["whale_tax"] = whale_tax
    
    # Validate balance (including whale tax)
    total_required = amount + fee + whale_tax
    if sender_balance < total_required:
        return jsonify({"error": "Insufficient balance"}), 400
    
    pending_transactions.append(tx_dict)
    return jsonify({"status": "accepted", "transaction": tx_dict, "whale_tax": whale_tax})


# ========== ECONOMIC ENDPOINTS ==========

@app.route('/economics/snapshot', methods=['GET'])
def get_economic_snapshot():
    """Get full economic state"""
    return jsonify(economics.get_full_economic_snapshot())


@app.route('/economics/emission', methods=['GET'])
def get_emission_info():
    """Get current emission info"""
    return jsonify(economics.emission.get_era_info())


@app.route('/economics/staking/apr/<address>', methods=['GET'])
def get_staking_apr(address: str):
    """Calculate staking APR for an address"""
    staked = state.stakes.get(address, 0)
    apr = StakingRewards.calculate_apr(staked)
    return jsonify({
        "address": address,
        "staked": staked,
        "apr": apr,
        "apr_percentage": apr * 100
    })


@app.route('/economics/governance/weight/<address>', methods=['GET'])
def get_governance_weight(address: str):
    """Get quadratic governance weight for an address"""
    staked = state.stakes.get(address, 0)
    weight = GovernanceWeighting.calculate_vote_weight(staked)
    return jsonify({
        "address": address,
        "staked": staked,
        "vote_weight": weight
    })


@app.route('/economics/whale/tax/<address>', methods=['GET'])
def get_whale_tax(address: str):
    """Check whale tax for an address"""
    balance = state.get_balance(address)
    tax = AntiWhaleMechanisms.calculate_whale_tax(balance)
    within_limit, msg = AntiWhaleMechanisms.check_holding_limit(balance)
    return jsonify({
        "address": address,
        "balance": balance,
        "whale_tax": tax,
        "within_limit": within_limit,
        "message": msg
    })


@app.route('/economics/sinks', methods=['GET'])
def get_sink_stats():
    """Get resource sink statistics"""
    return jsonify(economics.sinks.get_sink_stats())


# ========== SLASHING ENDPOINTS ==========

@app.route('/slashing/report', methods=['GET'])
def get_slashing_report():
    """Get slashing statistics"""
    return jsonify(slashing.get_slashing_report())


@app.route('/slashing/check/<validator>', methods=['GET'])
def check_validator_slashing(validator: str):
    """Check if a validator can unstake"""
    stake = state.stakes.get(validator, 0)
    can_unstake, msg = slashing.can_unstake(validator, stake)
    return jsonify({
        "validator": validator,
        "can_unstake": can_unstake,
        "slash_count": slashing.get_slash_count(validator),
        "message": msg
    })


# ========== GOVERNANCE ENDPOINTS ==========

@app.route('/governance/proposals', methods=['GET'])
def get_proposals():
    """Get all proposals"""
    status = request.args.get("status")
    return jsonify(governance.get_proposals(status))


@app.route('/governance/proposal/<proposal_id>', methods=['GET'])
def get_proposal(proposal_id: str):
    """Get a specific proposal"""
    prop = governance.get_proposal(proposal_id)
    if prop:
        return jsonify(prop)
    return jsonify({"error": "Proposal not found"}), 404


@app.route('/governance/proposal', methods=['POST'])
def create_proposal():
    """Create a new governance proposal"""
    data = request.json
    
    proposer = data.get("proposer")
    title = data.get("title")
    description = data.get("description")
    proposal_type = data.get("type", "parameter")
    voting_period = data.get("voting_period", 7 * 24 * 3600)
    
    prop = governance.create_proposal(
        proposer=proposer,
        title=title,
        description=description,
        proposal_type=proposal_type,
        voting_period=voting_period,
        data=data.get("data", {})
    )
    
    return jsonify({"status": "created", "proposal": prop.to_dict()})


@app.route('/governance/vote', methods=['POST'])
def vote_proposal():
    """Vote on a proposal"""
    data = request.json
    
    proposal_id = data.get("proposal_id")
    voter = data.get("voter")
    support = data.get("support", True)
    
    # Get voting weight
    staked = state.stakes.get(voter, 0)
    weight = GovernanceWeighting.calculate_vote_weight(staked)
    
    success, msg = governance.vote(proposal_id, voter, support, weight)
    
    if success:
        return jsonify({"status": "voted", "weight": weight})
    return jsonify({"error": msg}), 400


@app.route('/governance/execute/<proposal_id>', methods=['POST'])
def execute_proposal(proposal_id: str):
    """Execute a passed proposal"""
    total_staked = sum(state.stakes.values())
    success, msg = governance.execute_proposal(proposal_id, total_staked)
    
    if success:
        return jsonify({"status": "executed", "message": msg})
    return jsonify({"error": msg}), 400


@app.route('/governance/treasury', methods=['GET'])
def get_treasury():
    """Get treasury balance"""
    return jsonify({
        "balance": governance.treasury,
        "proposal_count": len(governance.proposals)
    })


# ========== PEERS ENDPOINTS ==========

@app.route('/peers', methods=['GET'])
def get_peers():
    """Get list of peers"""
    return jsonify({
        "peers": [p.to_dict() for p in p2p_network.peers.values()],
        "count": len(p2p_network.peers)
    })


@app.route('/peers/validators', methods=['GET'])
def get_validator_peers():
    """Get validator peers"""
    return jsonify({
        "validators": [p.to_dict() for p in p2p_network.get_validators()],
        "count": len(p2p_network.get_validators())
    })


# ========== GENESIS ENDPOINTS ==========

@app.route('/genesis', methods=['GET'])
def get_genesis():
    """Get genesis configuration"""
    return jsonify(genesis_config)


# ========== ROLE & PERMISSION ENDPOINTS ==========

@app.route('/roles/assign', methods=['POST'])
def assign_role():
    """Assign a role to an address"""
    data = request.json
    address = data.get("address")
    role = data.get("role", "player")
    
    success = role_manager.assign_role(address, role)
    if success:
        return jsonify({"status": "assigned", "role": role})
    return jsonify({"error": "Invalid role"}), 400


@app.route('/roles/user/<address>', methods=['GET'])
def get_user_role(address: str):
    """Get user's role and permissions"""
    return jsonify(role_manager.get_user_info(address))


@app.route('/roles/has_permission', methods=['GET'])
def check_permission():
    """Check if address has a permission"""
    address = request.args.get("address")
    permission = request.args.get("permission")
    
    has_it = role_manager.has_permission(address, permission)
    return jsonify({"address": address, "permission": permission, "has": has_it})


@app.route('/roles/freeze', methods=['POST'])
def freeze_user():
    """Freeze a user's permissions"""
    data = request.json
    address = data.get("address")
    
    success = role_manager.freeze_user(address)
    return jsonify({"status": "frozen" if success else "error"})


# ========== INVISIBLE WALLET ENDPOINTS ==========

@app.route('/wallet/stealth/create', methods=['POST'])
def create_stealth_wallet():
    """Create an invisible/stealth wallet"""
    data = request.json
    user_id = data.get("user_id")
    
    wallet = wallet_manager.generate_stealth_address(user_id)
    return jsonify({"wallet": wallet.to_dict()})


@app.route('/wallet/stealth/resolve', methods=['POST'])
def resolve_stealth_address():
    """Resolve stealth address to internal address"""
    data = request.json
    stealth_addr = data.get("stealth_address")
    
    internal = wallet_manager.get_internal_address(stealth_addr)
    if internal:
        return jsonify({"stealth_address": stealth_addr, "internal_address": internal})
    return jsonify({"error": "Unknown stealth address"}), 404


# ========== VALIDATOR SIGNATURE ENDPOINTS ==========

@app.route('/validator/register', methods=['POST'])
def register_validator():
    """Register validator's key for signing"""
    data = request.json
    address = data.get("address")
    private_key = data.get("private_key")
    
    validator_sigs.register_validator_key(address, private_key)
    
    # Also assign validator role
    role_manager.assign_role(address, "validator")
    
    return jsonify({"status": "registered"})


@app.route('/validator/sign_block', methods=['POST'])
def sign_block():
    """Validator signs a block"""
    data = request.json
    validator = data.get("validator")
    block_hash = data.get("block_hash")
    height = data.get("height")
    private_key = data.get("private_key")
    
    try:
        sig = validator_sigs.sign_block(validator, block_hash, height, private_key)
        return jsonify({"signature": sig.to_dict()})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route('/validator/signatures/<int:height>', methods=['GET'])
def get_block_signatures(height: int):
    """Get signatures for a block"""
    return jsonify({
        "height": height,
        "signatures": validator_sigs.get_block_signatures(height),
        "has_quorum": validator_sigs.has_quorum(height)
    })


@app.route('/validator/commit/create', methods=['POST'])
def create_commit():
    """Create a validator-confirmed commit"""
    data = request.json
    content_hash = data.get("content_hash")
    content_type = data.get("content_type", "world_update")
    required = data.get("required_validators")
    
    commit = validator_sigs.create_commit(content_hash, content_type, required)
    return jsonify({"commit": commit.to_dict()})


@app.route('/validator/commit/sign', methods=['POST'])
def sign_commit():
    """Add validator signature to commit"""
    data = request.json
    commit_id = data.get("commit_id")
    validator = data.get("validator")
    private_key = data.get("private_key")
    
    success = validator_sigs.sign_commit(commit_id, validator, private_key)
    if success:
        return jsonify({"status": "signed"})
    return jsonify({"error": "Failed to sign"}), 400


@app.route('/validator/commit/<commit_id>', methods=['GET'])
def get_commit(commit_id: str):
    """Get commit status"""
    commit = validator_sigs.get_commit(commit_id)
    if commit:
        return jsonify(commit.to_dict())
    return jsonify({"error": "Commit not found"}), 404


@app.route('/validator/commit/execute/<commit_id>', methods=['POST'])
def execute_commit(commit_id: str):
    """Execute a commit with quorum"""
    success = validator_sigs.execute_commit(commit_id)
    if success:
        return jsonify({"status": "executed"})
    return jsonify({"error": "Not enough signatures"}), 400


# ========== CONFLICT RESOLUTION ENDPOINTS ==========

@app.route('/dispute/create', methods=['POST'])
def create_dispute():
    """Create a dispute for validator voting"""
    data = request.json
    disputant = data.get("disputant")
    claim = data.get("claim")
    evidence = data.get("evidence", "")
    
    dispute_id = conflict_resolver.create_dispute(disputant, claim, evidence)
    return jsonify({"dispute_id": dispute_id})


@app.route('/dispute/vote', methods=['POST'])
def vote_dispute():
    """Vote on a dispute"""
    data = request.json
    dispute_id = data.get("dispute_id")
    validator = data.get("validator")
    vote = data.get("vote", True)
    weight = data.get("weight", 1)
    
    success = conflict_resolver.vote_on_dispute(dispute_id, validator, vote, weight)
    return jsonify({"status": "voted" if success else "error"})


@app.route('/dispute/resolve/<dispute_id>', methods=['POST'])
def resolve_dispute(dispute_id: str):
    """Resolve a dispute"""
    result = conflict_resolver.resolve_dispute(dispute_id)
    if result:
        return jsonify(result)
    return jsonify({"error": "Dispute not found"}), 404


@app.route('/dispute/pending', methods=['GET'])
def get_pending_disputes():
    """Get pending disputes"""
    return jsonify({"disputes": conflict_resolver.get_pending_disputes()})


# ========== NFT ENDPOINTS ==========

@app.route('/nft/mint', methods=['POST'])
def mint_nft():
    """Mint a new NFT"""
    data = request.json
    owner = data.get("owner")
    nft_type = data.get("type", "item")
    name = data.get("name")
    description = data.get("description", "")
    attributes = data.get("attributes", {})
    
    nft = nft_manager.mint(owner, nft_type, name, description, attributes)
    event_manager.emit(EventType.NFT_MINTED, {"token_id": nft.token_id, "owner": owner, "name": name})
    
    return jsonify({"nft": nft.to_dict()})


@app.route('/nft/<token_id>', methods=['GET'])
def get_nft(token_id: str):
    """Get NFT by token ID"""
    nft = nft_manager.get_nft(token_id)
    if nft:
        return jsonify(nft.to_dict())
    return jsonify({"error": "NFT not found"}), 404


@app.route('/nft/owner/<address>', methods=['GET'])
def get_owner_nfts(address: str):
    """Get all NFTs owned by address"""
    return jsonify({"nfts": nft_manager.get_owner_nfts(address)})


@app.route('/nft/transfer', methods=['POST'])
def transfer_nft():
    """Transfer NFT ownership"""
    data = request.json
    token_id = data.get("token_id")
    from_addr = data.get("from")
    to_addr = data.get("to")
    
    success = nft_manager.transfer(token_id, from_addr, to_addr)
    if success:
        event_manager.emit(EventType.NFT_TRANSFERRED, {"token_id": token_id, "from": from_addr, "to": to_addr})
        return jsonify({"status": "transferred"})
    return jsonify({"error": "Transfer failed"}), 400


@app.route('/nft/type/<nft_type>', methods=['GET'])
def get_nfts_by_type(nft_type: str):
    """Get all NFTs of a type"""
    return jsonify({"nfts": nft_manager.get_by_type(nft_type)})


# ========== MULTI-SIG ENDPOINTS ==========

@app.route('/multisig/create', methods=['POST'])
def create_multisig():
    """Create a multi-sig wallet"""
    data = request.json
    name = data.get("name")
    owners = data.get("owners", [])
    required = data.get("required", 2)
    
    wallet = multisig_manager.create_wallet(name, owners, required)
    event_manager.emit(EventType.WALLET_CREATED, {"wallet_id": wallet.wallet_id, "name": name})
    
    return jsonify({"wallet": wallet.to_dict()})


@app.route('/multisig/<wallet_id>', methods=['GET'])
def get_multisig(wallet_id: str):
    """Get multi-sig wallet"""
    wallet = multisig_manager.get_wallet(wallet_id)
    if wallet:
        return jsonify(wallet.to_dict())
    return jsonify({"error": "Wallet not found"}), 404


@app.route('/multisig/<wallet_id>/fund', methods=['POST'])
def fund_multisig():
    """Add funds to multi-sig"""
    data = request.json
    wallet_id = data.get("wallet_id")
    amount = data.get("amount", 0)
    
    success = multisig_manager.add_funds(wallet_id, amount)
    if success:
        return jsonify({"status": "funded", "balance": multisig_manager.get_wallet(wallet_id).balance})
    return jsonify({"error": "Wallet not found"}), 404


@app.route('/multisig/<wallet_id>/tx/create', methods=['POST'])
def create_multisig_tx():
    """Create a multi-sig transaction"""
    data = request.json
    wallet_id = data.get("wallet_id")
    to = data.get("to")
    amount = data.get("amount", 0)
    creator = data.get("creator")
    
    tx = multisig_manager.create_transaction(wallet_id, to, amount, creator)
    if tx:
        return jsonify({"transaction": tx.to_dict()})
    return jsonify({"error": "Failed to create transaction"}), 400


@app.route('/multisig/tx/<tx_id>/sign', methods=['POST'])
def sign_multisig_tx():
    """Sign a multi-sig transaction"""
    data = request.json
    tx_id = data.get("tx_id")
    signer = data.get("signer")
    signature = data.get("signature")
    
    success = multisig_manager.sign_transaction(tx_id, signer, signature)
    return jsonify({"status": "signed" if success else "error"})


@app.route('/multisig/tx/<tx_id>/execute', methods=['POST'])
def execute_multisig_tx(tx_id: str):
    """Execute a multi-sig transaction"""
    success = multisig_manager.execute_transaction(tx_id)
    return jsonify({"status": "executed" if success else "error"})


@app.route('/multisig/<wallet_id>/pending', methods=['GET'])
def get_multisig_pending(wallet_id: str):
    """Get pending transactions for wallet"""
    return jsonify({"transactions": multisig_manager.get_pending_txs(wallet_id)})


# ========== EVENT SYSTEM ENDPOINTS ==========

@app.route('/events/webhook', methods=['POST'])
def register_webhook():
    """Register a webhook"""
    data = request.json
    url = data.get("url")
    event_types = data.get("events")
    
    event_manager.register_webhook(url, event_types)
    return jsonify({"status": "registered"})


@app.route('/events/webhook', methods=['DELETE'])
def remove_webhook():
    """Remove a webhook"""
    url = request.args.get("url")
    event_manager.remove_webhook(url)
    return jsonify({"status": "removed"})


@app.route('/events/history', methods=['GET'])
def get_event_history():
    """Get event history"""
    event_type = request.args.get("type")
    limit = int(request.args.get("limit", 100))
    return jsonify({"events": event_manager.get_event_history(event_type, limit)})


# ========== SMART CONTRACT ENDPOINTS ==========

@app.route('/contract/deploy', methods=['POST'])
def deploy_contract():
    """Deploy a smart contract"""
    data = request.json
    owner = data.get("owner")
    code = data.get("code")
    initial_state = data.get("initial_state", {})
    
    contract = contract_registry.deploy(owner, code, initial_state)
    return jsonify({"contract": contract.to_dict()})


@app.route('/contract/<contract_id>', methods=['GET'])
def get_contract(contract_id: str):
    """Get contract info"""
    contract = contract_registry.get_contract(contract_id)
    if contract:
        return jsonify(contract.to_dict())
    return jsonify({"error": "Contract not found"}), 404


@app.route('/contract/<contract_id>/call', methods=['POST'])
def call_contract(contract_id: str):
    """Call a contract function"""
    data = request.json
    function = data.get("function")
    args = data.get("args", {})
    
    result = contract_registry.call(contract_id, function, args)
    return jsonify({"result": result})


@app.route('/contracts', methods=['GET'])
def list_contracts():
    """List all contracts"""
    return jsonify({"contracts": contract_registry.get_all_contracts()})


# ========== TRANSACTION INDEXER ENDPOINTS ==========

@app.route('/search', methods=['GET'])
def search_transactions():
    """Search transactions"""
    sender = request.args.get("sender")
    recipient = request.args.get("recipient")
    tx_type = request.args.get("type")
    min_amount = float(request.args.get("min_amount", 0))
    max_amount = request.args.get("max_amount")
    if max_amount:
        max_amount = float(max_amount)
    limit = int(request.args.get("limit", 50))
    
    results = tx_indexer.search(sender, recipient, tx_type, min_amount, max_amount, limit)
    return jsonify({"results": results, "count": len(results)})


@app.route('/index/tx', methods=['POST'])
def index_transaction():
    """Manually index a transaction"""
    data = request.json
    tx_indexer.index(data)
    return jsonify({"status": "indexed"})


# ========== LIGHT CLIENT ENDPOINTS ==========

@app.route('/light/sync', methods=['POST'])
def light_sync():
    """Sync light client state"""
    data = request.json
    block_hash = data.get("block_hash")
    block_height = data.get("block_height")
    timestamp = data.get("timestamp")
    total_supply = data.get("total_supply")
    validator_set = data.get("validator_set", [])
    
    light_client.sync(block_hash, block_height, timestamp, total_supply, validator_set)
    return jsonify({"status": "synced"})


@app.route('/light/state', methods=['GET'])
def light_state():
    """Get light client state"""
    state = light_client.get_state()
    if state:
        return jsonify(state)
    return jsonify({"error": "Not synced"}), 404


@app.route('/light/verify', methods=['POST'])
def light_verify():
    """Verify transaction with proof"""
    data = request.json
    tx = data.get("transaction")
    proof = data.get("proof", [])
    
    valid = light_client.verify_transaction(tx, proof)
    return jsonify({"valid": valid})


# ========== WALLET API ENDPOINTS ==========

@app.route('/wallet/mnemonic', methods=['GET'])
def generate_mnemonic():
    """Generate a new mnemonic phrase"""
    word_count = int(request.args.get("words", 12))
    mnemonic = Mnemonic.generate(word_count)
    return jsonify({"mnemonic": mnemonic})


@app.route('/wallet/create', methods=['POST'])
def create_wallet_account():
    """Create a new wallet account"""
    data = request.json
    name = data.get("name", "New Wallet")
    wallet_type = data.get("type", WalletType.HOT)
    mnemonic = data.get("mnemonic")
    
    wallet = wallet_manager.create_wallet(name, wallet_type, mnemonic)
    return jsonify({"wallet": wallet.to_dict()})


@app.route('/wallet/list', methods=['GET'])
def list_wallets():
    """List all wallets"""
    wallet_type = request.args.get("type")
    return jsonify({"wallets": wallet_manager.list_wallets(wallet_type)})


@app.route('/wallet/<wallet_id>', methods=['GET'])
def get_wallet(wallet_id: str):
    """Get wallet details"""
    wallet = wallet_manager.get_wallet(wallet_id)
    if wallet:
        return jsonify(wallet.to_dict())
    return jsonify({"error": "Wallet not found"}), 404


@app.route('/wallet/<wallet_id>/address', methods=['POST'])
def add_wallet_address(wallet_id: str):
    """Add new address to wallet"""
    addr = wallet_manager.add_address(wallet_id)
    if addr:
        return jsonify({"address": addr})
    return jsonify({"error": "Wallet not found"}), 404


@app.route('/wallet/dashboard/<wallet_id>', methods=['GET'])
def wallet_dashboard(wallet_id: str):
    """Get wallet dashboard"""
    wallet = wallet_manager.get_wallet(wallet_id)
    if not wallet:
        return jsonify({"error": "Wallet not found"}), 404
    
    dashboard = WalletUI.dashboard(wallet, wallet_client)
    return jsonify(dashboard)


@app.route('/wallet/addresses/<wallet_id>', methods=['GET'])
def list_wallet_addresses(wallet_id: str):
    """List all addresses with QR data"""
    wallet = wallet_manager.get_wallet(wallet_id)
    if not wallet:
        return jsonify({"error": "Wallet not found"}), 404
    
    return jsonify({"addresses": WalletUI.address_list(wallet)})


@app.route('/wallet/send', methods=['POST'])
def wallet_send():
    """Send from wallet"""
    data = request.json
    wallet_id = data.get("wallet_id")
    to = data.get("to")
    amount = float(data.get("amount", 0))
    private_key = data.get("private_key")
    fee = float(data.get("fee", 0.01))
    
    wallet = wallet_manager.get_wallet(wallet_id)
    if not wallet:
        return jsonify({"error": "Wallet not found"}), 404
    
    from_addr = wallet.addresses[0] if wallet.addresses else None
    if not from_addr:
        return jsonify({"error": "No address in wallet"}), 400
    
    result = wallet_client.send(from_addr, to, amount, private_key, fee)
    return jsonify(result)


@app.route('/wallet/stake', methods=['POST'])
def wallet_stake():
    """Stake from wallet"""
    data = request.json
    wallet_id = data.get("wallet_id")
    amount = float(data.get("amount", 0))
    private_key = data.get("private_key")
    
    wallet = wallet_manager.get_wallet(wallet_id)
    if not wallet:
        return jsonify({"error": "Wallet not found"}), 404
    
    from_addr = wallet.addresses[0] if wallet.addresses else None
    result = wallet_client.stake(from_addr, amount, private_key)
    return jsonify(result)


@app.route('/wallet/history/<wallet_id>', methods=['GET'])
def wallet_history(wallet_id: str):
    """Get transaction history"""
    wallet = wallet_manager.get_wallet(wallet_id)
    if not wallet:
        return jsonify({"error": "Wallet not found"}), 404
    
    limit = int(request.args.get("limit", 50))
    all_history = []
    
    for addr in wallet.addresses:
        history = wallet_client.get_history(addr, limit)
        all_history.extend(history)
    
    return jsonify({"history": all_history[:limit]})


@app.route('/wallet/backup/<wallet_id>', methods=['GET'])
def backup_wallet(wallet_id: str):
    """Export wallet backup"""
    wallet = wallet_manager.get_wallet(wallet_id)
    if not wallet:
        return jsonify({"error": "Wallet not found"}), 404
    
    # In real impl, would include private keys
    backup = WalletBackup.export_json(wallet, {})
    return jsonify(backup)


@app.route('/wallet/import', methods=['POST'])
def import_wallet():
    """Import wallet from backup"""
    data = request.json
    wallet_data = data.get("wallet")
    
    wallet = WalletBackup.import_json(wallet_data)
    wallet_manager.wallets[wallet.wallet_id] = wallet
    wallet_manager.save()
    
    return jsonify({"wallet": wallet.to_dict()})


@app.route('/wallet/nfts/<wallet_id>', methods=['GET'])
def wallet_nfts(wallet_id: str):
    """Get NFTs owned by wallet"""
    wallet = wallet_manager.get_wallet(wallet_id)
    if not wallet:
        return jsonify({"error": "Wallet not found"}), 404
    
    all_nfts = []
    for addr in wallet.addresses:
        nfts = wallet_client.get_nfts(addr)
        all_nfts.extend(nfts)
    
    return jsonify({"nfts": all_nfts})


# ========== RECOVERY API ENDPOINTS ==========

@app.route('/recovery/methods/<wallet_id>', methods=['GET'])
def get_recovery_methods(wallet_id: str):
    """Get available recovery methods"""
    methods = recovery_manager.get_methods(wallet_id)
    return jsonify({"wallet_id": wallet_id, "methods": methods})


@app.route('/recovery/mnemonic', methods=['POST'])
def add_mnemonic_recovery():
    """Add mnemonic recovery method"""
    data = request.json
    wallet_id = data.get("wallet_id")
    mnemonic = data.get("mnemonic")
    
    recovery_manager.add_mnemonic_recovery(wallet_id, mnemonic)
    
    # Also create cloud backup
    cloud_backup.create_backup(wallet_id, mnemonic)
    
    return jsonify({"status": "added", "method": "mnemonic"})


@app.route('/recovery/private_key', methods=['POST'])
def add_private_key_recovery():
    """Add private key recovery method"""
    data = request.json
    wallet_id = data.get("wallet_id")
    private_key = data.get("private_key")
    
    recovery_manager.add_private_key_recovery(wallet_id, private_key)
    return jsonify({"status": "added", "method": "private_key"})


@app.route('/recovery/keystore', methods=['POST'])
def add_keystore_recovery():
    """Add keystore recovery method"""
    data = request.json
    wallet_id = data.get("wallet_id")
    keystore = data.get("keystore")
    password = data.get("password")
    
    recovery_manager.add_keystore_recovery(wallet_id, keystore, password)
    return jsonify({"status": "added", "method": "keystore"})


@app.route('/recovery/email', methods=['POST'])
def add_email_recovery():
    """Add email/password recovery"""
    data = request.json
    wallet_id = data.get("wallet_id")
    email = data.get("email")
    password = data.get("password")
    
    recovery_manager.add_email_recovery(wallet_id, email, password)
    return jsonify({"status": "added", "method": "email_password"})


@app.route('/recovery/social', methods=['POST'])
def add_social_recovery():
    """Add social recovery"""
    data = request.json
    wallet_id = data.get("wallet_id")
    contacts = data.get("trusted_contacts", [])
    threshold = data.get("threshold", 2)
    
    recovery_manager.add_social_recovery(wallet_id, contacts, threshold)
    return jsonify({"status": "added", "method": "social", "threshold": threshold})


@app.route('/recovery/questions', methods=['POST'])
def add_questions_recovery():
    """Add security questions recovery"""
    data = request.json
    wallet_id = data.get("wallet_id")
    questions = data.get("questions", [])
    
    recovery_manager.add_question_recovery(wallet_id, questions)
    return jsonify({"status": "added", "method": "questions"})


@app.route('/recovery/paper', methods=['POST'])
def create_paper_wallet():
    """Create paper wallet for printing"""
    data = request.json
    private_key = data.get("private_key")
    
    paper = RecoveryManager.create_paper_wallet(private_key)
    return jsonify(paper)


@app.route('/recovery/attempt', methods=['POST'])
def attempt_recovery():
    """Attempt recovery using specified method"""
    data = request.json
    method = data.get("method")
    recovery_data = data.get("data", {})
    
    address = recovery_manager.attempt_recovery(method, recovery_data)
    
    if address:
        return jsonify({"status": "success", "address": address})
    return jsonify({"status": "failed", "error": "Recovery failed"}), 400


@app.route('/recovery/cloud/<wallet_id>', methods=['GET'])
def cloud_recover(wallet_id: str):
    """Recover from cloud backup"""
    secret = request.args.get("secret", "")
    result = cloud_backup.recover(wallet_id, secret)
    
    if result:
        return jsonify({"status": "success", "mnemonic": result.get("mnemonic")})
    return jsonify({"status": "failed", "error": "No backup found"}), 404


@app.route('/recovery/cloud', methods=['POST'])
def cloud_backup_wallet():
    """Create cloud backup"""
    data = request.json
    wallet_id = data.get("wallet_id")
    mnemonic = data.get("mnemonic")
    encrypted_keystore = data.get("keystore")
    
    backup = cloud_backup.create_backup(wallet_id, mnemonic, encrypted_keystore)
    return jsonify({"status": "backed_up", "wallet_id": wallet_id})


# ========== PASSKEY API ENDPOINTS ==========

@app.route('/passkey/register/start/<wallet_id>', methods=['POST'])
def passkey_register_start(wallet_id: str):
    """Start passkey registration"""
    data = request.json or {}
    username = data.get("username", "user")
    
    result = passkey_manager.start_registration(wallet_id, username)
    return jsonify(result)


@app.route('/passkey/register/complete/<wallet_id>', methods=['POST'])
def passkey_register_complete(wallet_id: str):
    """Complete passkey registration"""
    data = request.json
    credential_data = data.get("credential", {})
    
    success = passkey_manager.complete_registration(wallet_id, credential_data)
    
    if success:
        # Also add as recovery method
        from wallet_recovery import RecoveryMethod
        recovery_manager.add_method(wallet_id, RecoveryMethod.CUSTOM_QUESTIONS, {"passkey": True})
    
    return jsonify({"status": "registered" if success else "failed"})


@app.route('/passkey/auth/start/<wallet_id>', methods=['POST'])
def passkey_auth_start(wallet_id: str):
    """Start passkey authentication"""
    result = passkey_manager.start_authentication(wallet_id)
    return jsonify(result)


@app.route('/passkey/auth/complete/<wallet_id>', methods=['POST'])
def passkey_auth_complete(wallet_id: str):
    """Complete passkey authentication"""
    data = request.json
    credential_data = data.get("credential", {})
    
    success = passkey_manager.complete_authentication(wallet_id, credential_data)
    
    return jsonify({"status": "authenticated" if success else "failed"})


@app.route('/passkey/list/<wallet_id>', methods=['GET'])
def list_passkeys(wallet_id: str):
    """List passkeys for wallet"""
    keys = passkey_manager.list_passkeys(wallet_id)
    return jsonify({"wallet_id": wallet_id, "passkeys": keys})


@app.route('/passkey/remove/<wallet_id>', methods=['DELETE'])
def remove_passkey(wallet_id: str):
    """Remove a passkey"""
    credential_id = request.args.get("credential_id")
    
    success = passkey_manager.remove_passkey(wallet_id, credential_id)
    return jsonify({"status": "removed" if success else "not_found"})


@app.route('/passkey/simulate', methods=['POST'])
def simulate_passkey_device():
    """Simulate a passkey device (dev/testing)"""
    data = request.json
    device_name = data.get("device_name", "Test Device")
    wallet_id = data.get("wallet_id")
    
    result = PasskeyRecovery.create_recovery_passkey(wallet_id or "unknown", device_name)
    return jsonify(result)


@app.route('/passkey/recover', methods=['POST'])
def passkey_recover():
    """Recover wallet using passkey only"""
    data = request.json
    credential_data = data.get("credential")
    
    address = PasskeyRecovery.recover(credential_data)
    return jsonify({"status": "success", "address": address})


# ========== GOOGLE OAUTH API ENDPOINTS ==========

@app.route('/auth/google/url', methods=['GET'])
def google_auth_url():
    """Get Google OAuth URL"""
    wallet_id = request.args.get("wallet_id")
    redirect_uri = request.args.get("redirect_uri")
    
    result = oauth_manager.get_auth_url(wallet_id, redirect_uri)
    return jsonify(result)


@app.route('/auth/google/callback', methods=['GET'])
def google_callback():
    """Handle Google OAuth callback"""
    code = request.args.get("code")
    state = request.args.get("state")
    
    result = oauth_manager.exchange_code(code, state)
    
    if not result:
        return jsonify({"error": "Authentication failed"}), 400
    
    # Create wallet if needed
    wallet = wallet_manager.get_wallet(result.get("wallet_id", ""))
    if not wallet and result.get("userinfo"):
        # Create wallet from Google account
        email = result["userinfo"].get("email", "")
        wallet = wallet_manager.create_wallet(f"Google: {email}", WalletType.HOT)
    
    # Link Google account
    if wallet:
        address = wallet.addresses[0] if wallet.addresses else ""
        oauth_manager.link_google_account(
            wallet.wallet_id,
            result["userinfo"],
            address
        )
        
        # Create session
        session = oauth_manager.create_session(result["userinfo"]["id"])
        
        return jsonify({
            "status": "success",
            "session": session,
            "wallet_id": wallet.wallet_id,
            "address": address,
            "email": result["userinfo"].get("email")
        })
    
    return jsonify({"error": "Failed to create wallet"}), 500


@app.route('/auth/google/simulate', methods=['POST'])
def simulate_google_login():
    """Simulate Google login (dev mode)"""
    data = request.json
    email = data.get("email", "demo@demo.com")
    wallet_id = data.get("wallet_id")
    
    result = SimulatedGoogleLogin.simulate_login(email, wallet_id)
    
    if not result:
        return jsonify({"error": "Demo user not found"}), 404
    
    # Create or link wallet
    existing_wallet_id = oauth_manager.get_wallet_by_email(email)
    
    if existing_wallet_id:
        wallet = wallet_manager.get_wallet(existing_wallet_id)
        user = oauth_manager.login_with_google(result["id"])
    else:
        # Create new wallet
        wallet = wallet_manager.create_wallet(f"Google: {email}", WalletType.HOT)
        
        address = wallet.addresses[0] if wallet.addresses else ""
        oauth_manager.link_google_account(wallet.wallet_id, result, address)
        user = oauth_manager.login_with_google(result["id"])
    
    # Create session
    session = oauth_manager.create_session(result["id"])
    
    return jsonify({
        "status": "success",
        "session": session,
        "wallet_id": wallet.wallet_id,
        "address": wallet.addresses[0] if wallet.addresses else None,
        "email": email,
        "name": result.get("name")
    })


@app.route('/auth/session', methods=['GET'])
def validate_session():
    """Validate session token"""
    token = request.args.get("token")
    
    user = oauth_manager.validate_session(token)
    if user:
        return jsonify({
            "valid": True,
            "user": user.to_dict()
        })
    return jsonify({"valid": False}), 401


@app.route('/auth/logout', methods=['POST'])
def logout():
    """Logout session"""
    data = request.json
    token = data.get("token")
    
    success = oauth_manager.logout_session(token)
    return jsonify({"status": "logged_out" if success else "failed"})


@app.route('/auth/linked/<wallet_id>', methods=['GET'])
def get_linked_accounts(wallet_id: str):
    """Get linked Google accounts"""
    accounts = oauth_manager.get_linked_accounts(wallet_id)
    return jsonify({"wallet_id": wallet_id, "accounts": accounts})


@app.route('/auth/unlink/<wallet_id>', methods=['POST'])
def unlink_google(wallet_id: str):
    """Unlink Google account"""
    success = oauth_manager.unlink_google(wallet_id)
    return jsonify({"status": "unlinked" if success else "not_found"})


def main():
    """Start the main node"""
    init_genesis()
    
    # Start block producer thread
    producer = threading.Thread(target=block_producer_loop, daemon=True)
    producer.start()
    
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", "-p", type=int, default=6001)
    args = parser.parse_args()
    
    print(f"\n🌟 Wrath of Cali Blockchain Main Node")
    print(f"   Block time: {BLOCK_TIME}s")
    print(f"   Validator: {current_validator_addr}")
    print(f"   API: http://localhost:{args.port}\n")
    
    # Start Flask server
    app.run(host='0.0.0.0', port=args.port, debug=False, threaded=True)
    


# ========== DEV STUDIO ENDPOINTS ==========

@app.route('/project/files', methods=['GET'])
def list_project_files():
    """List project files"""
    import os
    base = '/Users/laura/.openclaw/workspace/wrath-of-cali'
    files = []
    for root, dirs, filenames in os.walk(base):
        dirs[:] = [d for d in dirs if d not in ['venv', 'node_modules', '.git', '__pycache__']]
        for f in filenames:
            if not f.startswith('.'):
                rel = os.path.relpath(os.path.join(root, f), base)
                files.append(rel)
    return jsonify({"files": files[:100], "count": len(files)})

@app.route('/project/status', methods=['GET'])
def project_status():
    """Get overall project status"""
    return jsonify({
        "game": {"status": "running", "port": 8888, "url": "http://localhost:8888"},
        "blockchain": {"status": "running", "port": 6001, "height": len(chain)},
        "dev_studio": {"status": "running", "port": 8000, "url": "http://localhost:8000/dev_studio.html"},
        "skills": {"count": 37, "path": ".claude/skills"},
        "agents": {"count": 48, "path": ".claude/agents"}
    })




# ========== AGENT SPAWNING ==========

@app.route('/agents/list', methods=['GET'])
def list_agents():
    """List available agents"""
    import os
    agents_dir = '/Users/laura/.openclaw/workspace/claude-code-game-studios/.claude/agents'
    agents = []
    if os.path.exists(agents_dir):
        for f in os.listdir(agents_dir):
            if f.endswith('.md'):
                agents.append(f.replace('.md', ''))
    
    skills_dir = '/Users/laura/.openclaw/workspace/claude-code-game-studios/.claude/skills'
    skills = []
    if os.path.exists(skills_dir):
        for f in os.listdir(skills_dir):
            if f.endswith('.md'):
                skills.append(f.replace('.md', ''))
    
    return jsonify({
        "agents": sorted(agents),
        "skills": sorted(skills),
        "agent_count": len(agents),
        "skill_count": len(skills)
    })

# ========== AGENT SPAWNER (moved before main) ==========
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

@app.route('/agent/spawn', methods=['POST'])
def spawn_agent_api():
    """Spawn an AI agent task"""
    from agent_spawner import spawn_agent_task, get_active_agents
    data = request.get_json()
    agent = data.get('agent', '')
    task = data.get('task', '')
    
    result = spawn_agent_task(agent, task)
    
    return jsonify({
        "status": "spawned",
        "agent": agent,
        "task": task,
        "session_id": result.get("session_id"),
        "message": f"Agent {agent} spawned for task: {task[:50]}..."
    })

@app.route('/agent/active', methods=['GET'])
def get_active_api():
    """Get active agents"""
    from agent_spawner import get_active_agents
    return jsonify({"agents": get_active_agents()})

def main():
    """Start the main node"""
    init_genesis()
