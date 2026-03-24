# Wrath of Cali Blockchain - Infinite Scaling SPEC

## The Infinite Scaling Architecture

**Key insight:** As more validators join, transaction volume is split across them. More nodes = more TPS.

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
           ▲                 ▲                 ▲                 ▲
    [Validators]      [Validators]      [Validators]      [Validators]
           │                 │                 │                 │
      (Shard A)         (Shard B)        (Shard C)        (Shard ...)

TPS = Validators × BatchesPerValidator × TxsPerBatch
```

## Scaling Rules

1. **Validators** join and subscribe to a shard (by address range or hash)
2. **Each shard** handles its portion independently
3. **Cross-shard transactions** handled via atomic commits between shards
4. **Add shards** by deploying more main nodes - no code changes needed

## Parameters (Tunable)

```python
MAX_VALIDATORS_PER_SHARD = 1000     # Max validators feeding one main node
MAX_BATCHES_PER_BLOCK = 100          # Batches per block
MAX_TRANSACTIONS_PER_BATCH = 1000    # Transactions per batch
BLOCK_TIME = 1                       # 1 second

# Theoretical max per shard:
# 1000 validators × 1 batch/sec × 1000 txs/batch = 1M TPS/shard

# With 10 shards: 10M TPS
# With 100 shards: 100M TPS (infinite!)
```

## New Components

### 1. Shard Router
- Routes transactions to correct main node based on recipient address
- Simple hash-based routing: `shard = hash(address) % num_shards`

### 2. Main Node (Shard-Aware)
- Each main node is responsible for a shard
- Reports its shard ID and load to discovery service

### 3. Discovery Service
- Keeps track of active main nodes and their shards
- Validators query to find their target main node

### 4. Cross-Shard Transactions
- If sender and recipient are on different shards:
  - Step 1: Lock on sender's shard
  - Step 2: Credit on recipient's shard  
  - Step 3: Debit on sender's shard
  - Step 4: Release lock
- Atomic - all or nothing

## API Extensions

```
GET  /shards              - List all active shards
GET  /shard/<id>         - Get shard status (load, tx count, validators)
POST /register/shard     - Register a new main node
GET  /validators/<shard>  - Get validators for a shard
```

## Load Balancing

- Validators automatically distribute to least-loaded shard
- Main nodes report load every 5 seconds
- Router redirects new validators to lowest-load shard

## Failure Handling

- If a main node goes down, its validators reconnect to other shards
- Chain state can be reconstructed from remaining nodes
- Watchtower nodes monitor all shards for finality