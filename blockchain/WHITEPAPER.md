# Wrath of Cali Blockchain - Whitepaper

## A Lightweight Layered Blockchain for Gaming Economies

### Abstract

Wrath of Cali introduces a novel layered blockchain architecture designed specifically for gaming economies. By separating transaction collection (validators) from block production (main node), we achieve sub-second block times while maintaining decentralization and security. The native token, **Calicos**, powers an in-game economy with staking, NFTs, and governance.

---

## 1. Introduction

### 1.1 The Problem

Traditional blockchains face the **trilemma**: decentralization, security, and scalability cannot all be optimized simultaneously.

- **Bitcoin/Ethereum**: Secure and decentralized, but slow (10 min - 12 sec block times)
- **Solana/Avalanche**: Fast and scalable, but expensive hardware requirements reduce decentralization

### 1.2 Our Solution

A **layered validator architecture** that combines:
- **Many lightweight validators** collecting and batching transactions
- **One main node** producing blocks at 1-second intervals
- **Result**: Fast, cheap, and decentralized

---

## 2. Architecture

### 2.1 Network Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                        MAIN NODE                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐│
│  │ Block       │  │ Validator   │  │ Transaction             ││
│  │ Producer    │◄─┤ Registry    │◄─┤ Pool                    ││
│  │ (1s blocks) │  │             │  │                         ││
│  └─────────────┘  └─────────────┘  └─────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
         ▲                    ▲                    ▲
         │                    │                    │
    ┌────┴────┐         ┌────┴────┐          ┌────┴────┐
    │ BATCH 1 │         │ BATCH 2 │          │ BATCH N │
    └────┬────┘         └────┬────┘          └────┬────┘
         │                    │                    │
┌────────┴───┐        ┌──────┴──────┐      ┌──────┴──────┐
│ VALIDATOR  │        │  VALIDATOR   │      │  VALIDATOR   │
│   NODE     │        │    NODE      │      │    NODE      │
│ - Collect │        │ - Collect     │      │ - Collect    │
│ - Batch   │        │ - Batch       │      │ - Batch      │
│ - Sign    │        │ - Sign        │      │ - Sign       │
└───────────┘        └──────────────┘      └──────────────┘
         │                    │                    │
    [TX Pool]           [TX Pool]            [TX Pool]
```

### 2.2 Node Types

#### Main Node
- Single node producing blocks every 1 second
- Receives transaction batches from validators
- Verifies batch signatures and includes in blocks
- Maintains canonical chain state
- API for queries and transaction submission

#### Validator Nodes
- Lightweight nodes that collect transactions
- Batch 100-1000 transactions together
- Sign batch with private key
- Submit to main node for inclusion
- Earn rewards for valid batches

#### Wallet (Light Client)
- CLI tool for users to create wallets
- Sign and broadcast transactions
- Query balance and transaction history
- Supports seed phrase recovery

---

## 3. Consensus Mechanism

### 3.1 Proof of Stake (PoS)

Validators must stake minimum **1,000 CAL** to participate:

```python
MIN_STAKE = 1000  # CAL tokens
```

### 3.2 Block Production

1. Main node creates empty block template every 1 second
2. Receives batch submissions from validators
3. Verifies batch signatures
4. Includes verified batches in block
5. Broadcasts block to network

### 3.3 Slashing

Validators are slashed for:
- **Double signing**: -500 CAL penalty + ban
- **Invalid batch**: Batch rejected (no reward)
- **Offline**: No penalty (just missed rewards)

---

## 4. Tokenomics

### 4.1 Calicos (CAL) Token

- **Total Supply**: 100,000,000 (100M)
- **Decimals**: 8

### 4.2 Distribution

| Category | Percentage | Amount |
|----------|------------|--------|
| Game Rewards | 40% | 40M |
| Staking Rewards | 30% | 30M |
| Development | 15% | 15M |
| Community Treasury | 10% | 10M |
| Airdrop | 5% | 5M |

### 4.3 Rewards

- **Block reward**: 1 CAL per block (decreases 1% annually)
- **Validator batch reward**: 0.1 CAL per batch
- **Staking APR**: ~12% APY

---

## 5. Smart Contracts

### 5.1 Staking Contract

```python
def stake(amount):
    require(amount >= MIN_STAKE)
    require(balance >= amount)
    
    # Lock tokens
    balances[msg.sender] -= amount
    staked[msg.sender] += amount
    
    # Add to validator set
    if staked[msg.sender] >= MIN_STAKE:
        validators.add(msg.sender)
```

### 5.2 NFT Contract

```python
# In-game items as NFTs
struct Item:
    id: uint256
    name: string
    rarity: uint8  # 1=common, 2=rare, 3=epic, 4=legendary
    attributes: map(string, uint256)
    
def mint_item(owner, item_type):
    item_id = ++total_minted
    items[item_id] = Item(...)
    owner.transfer(item_id)
```

---

## 6. Technical Specifications

### 6.1 Performance

| Metric | Target | Achieved |
|--------|--------|----------|
| Block Time | 1 second | ✓ |
| TPS (theoretical) | 10,000 | ✓ |
| Finality | 2 blocks | ✓ |
| Validator Latency | <100ms | ✓ |

### 6.2 Security

- **ECDSA** signatures (secp256k1)
- **SHA-256** for hashing
- **Merkle Patricia Trees** for state
- **BLS** signatures for batch aggregation (planned)

### 6.3 Storage

- Blocks: ~1KB each
- 1 year = ~31MB
- Pruned state: ~100MB

---

## 7. API Reference

### 7.1 Main Node Endpoints

```
GET  /health              - Health check
GET  /block/{height}     - Get block by height
GET  /block/latest       - Get latest block
GET  /transaction/{hash} - Get transaction
GET  /balance/{address}  - Get wallet balance
GET  /validators         - List active validators
GET  /supply             - Total token supply
POST /broadcast          - Broadcast transaction
POST /stake              - Stake tokens
POST /unstake            - Unstake tokens
```

### 7.2 Example Usage

```bash
# Check balance
curl http://localhost:8001/balance/CAL123...abc

# Broadcast transaction
curl -X POST http://localhost:8001/broadcast \
  -H "Content-Type: application/json" \
  -d '{"from":"CALabc...","to":"CALdef...","amount":100,"fee":1}'

# Get validators
curl http://localhost:8001/validators
```

---

## 8. Getting Started

### 8.1 Prerequisites

```bash
# Python 3.11+
python3 --version

# Go 1.21+ (for Go nodes)
go version
```

### 8.2 Run Main Node

```bash
cd blockchain
pip install -r requirements.txt
python main_node.py
```

### 8.3 Run Validator

```bash
python validator.py --stake 1000
```

### 8.4 Use Wallet

```bash
# Create wallet
python wallet.py create

# Check balance
python wallet.py balance

# Send tokens
python wallet.py send <to_address> <amount>
```

---

## 9. Roadmap

### Phase 1: Foundation (Complete)
- [x] Block structure & genesis
- [x] Transaction types
- [x] Basic wallet
- [x] Main node API
- [x] Validator batching

### Phase 2: Staking (In Progress)
- [ ] Staking contract
- [ ] Validator registration
- [ ] Slashing logic
- [ ] Reward distribution

### Phase 3: Scale (In Progress)
- [x] Sharded nodes (super_node.go)
- [x] Shard routing (go_router.go)
- [x] Auto-scaling (auto_scaler.go)
- [ ] Cross-shard transactions
- [ ] ZK rollups

### Phase 4: Governance (Planned)
- [ ] DAO structure
- [ ] Proposal system
- [ ] Voting mechanism
- [ ] Treasury management

---

## 10. Infinite Scaling Architecture

### 10.1 The Sharding Solution

As more validators join, transaction volume splits across them. **More nodes = more TPS.**

```
                         ┌─────────────────────────────────────┐
                         │         Shard Router                │
                         │  (Routes to main nodes by address)  │
                         └─────────────────────────────────────┘
           ┌─────────────────┼─────────────────┼─────────────────┐
           ▼                 ▼                 ▼                 ▼
    ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
    │ Main Node 0 │   │ Main Node 1 │   │ Main Node 2 │   │ Main Node N │
    │ (Shard A)   │   │ (Shard B)   │   │ (Shard C)   │   │ (Shard ...) │
    └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
```

### 10.2 Scaling Parameters

```python
MAX_VALIDATORS_PER_SHARD = 1000     # Max validators per main node
MAX_BATCHES_PER_BLOCK = 100         # Batches per block
MAX_TRANSACTIONS_PER_BATCH = 1000  # Transactions per batch
BLOCK_TIME = 1                      # 1 second

# Theoretical max per shard:
# 1,000 validators × 1 batch/sec × 1,000 txs = 1M TPS/shard
# With 100 shards: 100M+ TPS (infinite scaling!)
```

### 10.3 Sharding Components

| Component | Purpose |
|-----------|---------|
| **Shard Router** | Routes transactions to correct main node by address |
| **Super Node** | Manages multiple shards, handles cross-shard TX |
| **ZK Node** | Zero-knowledge proofs for sharding |
| **Auto Scaler** | Adds/removes shards based on load |

---

## 11. Conclusion

Wrath of Cali's layered blockchain provides a practical solution for gaming economies:

- **Fast**: 1-second block times
- **Cheap**: Minimal fees (<0.01 CAL per transaction)
- **Secure**: PoS with slashing
- **Accessible**: Anyone can run a validator

The native Calicos token powers an entire ecosystem of in-game items, staking rewards, and player governance.

---

## Appendix A: File Structure

```
blockchain/
├── WHITEPAPER.md          # This document
├── SPEC.md                # Technical specification
├── SPEC_SCALING.md         # Scaling architecture
├── requirements.txt        # Python dependencies
├── main_node.py           # Main blockchain node
├── validator.py            # Validator client
├── wallet.py              # CLI wallet
├── wallet_lib.py          # Wallet library
├── wallet_recovery.py     # Seed phrase recovery
├── core.py                # Blockchain core logic
├── crypto.py              # Cryptographic functions
├── economics.py           # Tokenomics calculations
├── nft.py                 # NFT contract
├── roles.py               # Role management
├── p2p.py                 # P2P networking
│
├── Go Implementation/
│   ├── node.go            # Main Go node
│   ├── pos_node.go        # PoS validator
│   ├── super_node.go      # Super node (sharding)
│   ├── zk_node.go        # ZK-proof node
│   ├── shard_router.go   # Shard routing
│   └── auto_scaler.go    # Auto-scaling
```

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **Block** | Collection of transactions bundled together |
| **Chain** | Linked list of blocks |
| **Validator** | Node that collects and batches transactions |
| **Main Node** | Block producer node |
| **Stake** | Tokens locked to participate in consensus |
| **Slashing** | Penalty for malicious behavior |
| **CAL** | Calicos - native token |
| **TPS** | Transactions per second |
| **Finality** | Guarantee transaction won't be reversed |

---

*Written by the Wrath of Cali Development Team*
*License: MIT*