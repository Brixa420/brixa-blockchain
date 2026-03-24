# Wrath of Cali Blockchain - SPEC

## Overview
A lightweight, fast blockchain for Wrath of Cali's in-game economy. Solves the blockchain trilemma using a layered validator architecture.

## The Solution (Laura's Innovation)
- **Validators**: Many lightweight nodes that batch transactions
- **Main Node**: Receives batches, verifies, adds to blockchain
- **Result**: Decentralization + Security + Scalability

## Goals
- 1 second block times
- Lightweight (like Bitcoin, simple but secure)
- In-game currency: Calicos
- Integrated with Wrath of Cali

## Architecture

```
┌─────────────────────────────────────────┐
│              Main Node                   │
│  - Verifies batches from validators      │
│  - Creates blocks (1s interval)          │
│  - Maintains canonical chain            │
└─────────────────────────────────────────┘
         ▲                        ▲
         │                        │
    [Batch 1]               [Batch N]
         │                        │
┌────────┴──┐              ┌───────┴──────┐
│ Validator │              │  Validator   │
│   Node    │              │    Node      │
│ - Collect │              │ - Collect    │
│ - Batch   │              │ - Batch      │
│ - Submit  │              │ - Submit     │
└───────────┘              └──────────────┘
```

## Core Components

### 1. Block Structure
- Block header (hash, prev hash, timestamp, validator signature)
- Transaction batch merkle root
- Block number/height

### 2. Transaction Types
- `TRANSFER` - Send Calicos between wallets
- `STAKE` - Lock coins to become validator
- `UNSTAKE` - Unlock staked coins
- `BATCH_SUBMIT` - Validator submits transaction batch

### 3. Validator Protocol
- Anyone can run a validator node
- Must stake minimum coins to participate
- Collects transactions, creates batch
- Submits batch to main node
- Main node includes batch in block

### 4. Consensus
- Main node is block producer
- Validators confirm blocks
- Slashing for invalid batches

### 5. Currency: Calicos
- Total supply: 100,000,000 (100M)
- Initial distribution: Game rewards, staking rewards

## Technical Specs
- **Block time**: 1 second
- **Max transactions per block**: 10,000 (from batches)
- **Validator batch size**: 100-1000 transactions
- **Minimum stake**: 1000 Calicos

## API Endpoints (Main Node)
- `GET /block/{height}` - Get block
- `GET /transaction/{hash}` - Get transaction
- `GET /balance/{address}` - Get wallet balance
- `POST /broadcast` - Broadcast transaction
- `GET /validators` - List active validators

## File Structure
```
blockchain/
├── SPEC.md
├── main_node.py      # Main blockchain node
├── validator.py      # Validator client
├── wallet.py         # CLI wallet
├── blockchain.json   # Chain data (or sqlite)
└── requirements.txt
```

## Implementation Priority
1. Basic blockchain structure + block creation
2. Transaction handling
3. Validator node + batching
4. Wallet CLI
5. Integration with game