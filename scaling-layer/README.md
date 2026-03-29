# BrixaScaler

## ⚠️ WARNING: PROOF OF CONCEPT ⚠️

**THIS IS NOT PRODUCTION SOFTWARE**

- Default mode: **DEMO_MODE=true** (logs transactions, does NOT actually send)
- For testing/development only
- Use `DEMO_MODE=false` to actually submit transactions
- **Author assumes NO LIABILITY for any losses**
- Use at **YOUR OWN RISK**

---

# BrixaScaler - Transaction Batching for Any Chain

<div align="center">

### 🔗 Any Chain | 📦 Batching | 🔐 ZK Proofs

*Horizontal scaling meets zero-knowledge cryptography*

</div>

---

## What It Does

BrixaScaler is a transaction batching middleware. It sits between your wallet/app and a blockchain, collecting multiple transactions into batches before submitting them to the chain.

**Result:** Batching multiplies throughput. The actual multiplier depends on ZK period.

## Real Benchmark Results

### Batching Layer (SHA256 Merkle)
| Configuration | TPS | Notes |
|---------------|-----|-------|
| Single thread | 5-6M | Baseline |
| 10 threads | 11.9M-20.6M | ±19% variance |

### With Periodic ZK Proofs
| Mode | TPS | Notes |
|------|-----|-------|
| Hash-only | 5-17M | No ZK, no security |
| Periodic ZK (1000) | ~7,000 | Real Circom + snarkjs |
| Continuous ZK | ~14 | 1 proof/batch (slow) |

### The Math
- Proof generation: ~565ms per proof (real benchmarked)
- Verification: ~188ms per proof (real benchmarked)
- With period=1000: 4000 tx / 0.565s = **7,079 TPS**

### Honest Comparison
| Chain | Base TPS | With BrixaScaler (real) |
|-------|----------|------------------------|
| Bitcoin | ~7 | ~7,000 |
| Ethereum | ~15-30 | ~7,000 |
| Polygon | ~7,000 | ~7,000 |
| Solana | ~3,000 | ~7,000 |

*The bottleneck is now the settlement layer (external chain), not our batcher.*

---

## The Tech

- **Sharded Architecture**: 10 parallel shards (not 1000 - sub-linear scaling)
- **Merkle Tree**: Batch verification via SHA256 (hardware accelerated)
- **ZK Proofs**: Circom circuit + snarkjs (real, ~565ms per proof)
- **Periodic ZK**: 1 proof per 1000 batches for amortized security
- **Multi-process**: Uses Node.js cluster for horizontal scaling

---

## Quick Start

```bash
# Clone
git clone https://github.com/Brixa420/vpn-for-tps.git
cd vpn-for-tps/scaling-layer/integration

# Run (demo mode - logs, doesn't send)
node brixaroll.js --rpc http://localhost:8545

# Or with real chain
node brixaroll.js --rpc https://eth.llamarpc.com
```

---

## Architecture

```
WALLET ──► 1000 TXS ──► BRIXAROLL
                            │
                            ▼
                   [batch into Merkle tree]
                            │
                            ▼
                   Generate ZK proof (periodic)
                            │
                            ▼
                   Submit to L1 (settlement)
```

## Scaling Efficiency

| Shards | Expected | Actual | Efficiency |
|--------|----------|--------|------------|
| 1 | 5.5M | 5.5M | 100% |
| 4 | 22M | 15M | 68% |
| 10 | 55M | 17M | 31% |

**Note:** Sub-linear scaling due to coordination overhead. 10 shards is not 10x faster.

---

## Known Limitations

1. **ZK proof generation** is CPU-intensive (~565ms per proof)
2. **Settlement bottleneck** - external chain TPS limits final throughput
3. **Variance** - high variance in benchmarks (±19% on 10-shard runs)
4. **Not infinite** - architecture has practical limits

---

## Files

- `integration/brixaroll.js` - Main batching node
- `integration/merkle-worker.js` - Parallel Merkle tree builder
- `integration/zk-prover.js` - ZK proof generator
- `bench/circuits/` - Circom circuits for ZK