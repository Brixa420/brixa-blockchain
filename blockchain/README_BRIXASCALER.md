# BrixaScaler - Final Architecture

## ⚠️ REAL BENCHMARKED NUMBERS ⚠️

| Layer | TPS | Status | How Tested |
|-------|-----|--------|------------|
| **1** | Batching (Merkle) | 5-17M | ✅ Real Go benchmark |
| **2** | Periodic ZK | ~7,000 | ✅ Real Circom+snarkjs |
| **3** | Settlement | ~65 | ⚠️ External chain |

## Three Layers

| Layer | Component | Throughput |
|-------|-----------|------------|
| **1** | Batching (Merkle SHA256) | 5-17M TPS |
| **2** | Verification (Periodic ZK) | ~7,000 TPS |
| **3** | Settlement (external L2) | ~65 TPS |

## Real Benchmark Data

### Batching Layer
```
Shards= 1, Workers= 1 → Mean=   5.7M TPS
Shards= 4, Workers= 4 → Mean=  12.4M TPS  
Shards=10, Workers=10 → Mean=  14.2M TPS (σ=3.2M, Range: 11.9M - 20.6M)
```

**Variance:** ±19% on 10-shard runs
**Efficiency:** 10 shards = 2.5x speedup (not 10x)

### ZK Layer (Real, Not Stubbed)
```
Proof generation: ~565ms per proof
Verification:     ~188ms per proof
Throughput:       ~7,000 TPS (with period=1000)
```

**This is real Circom circuit + snarkjs, not simulated.**

## Configuration

```javascript
{
    batchSize: 4,           // txs per batch
    zkPeriod: 1000,        // batches per ZK proof
    proveTime: 565,        // ms per ZK proof (real)
    verifyTime: 188        // ms per verify (real)
}
```

## How It Works

1. **Fast path:** Hash verification for every batch
2. **Slow path:** ZK proof every 1000 batches (cryptographic finality)
3. **Amortization:** 1 ZK proof covers 1000 batches = 4000 transactions

## Honest TPS Summary

| Mode | TPS | Real/Fake |
|------|-----|-----------|
| Single thread batching | 5-6M | ✅ Real |
| 10-thread batching | 11.9M-20.6M | ✅ Real (high variance) |
| Hash-only verify | 5-17M | ✅ Real |
| Periodic ZK (simulated) | 14K | ❌ Fake |
| **Periodic ZK (real)** | **~7K** | ✅ Real |
| Continuous ZK | ~14 | ✅ Real (too slow) |
| Settlement | ~65 | ⚠️ External |

## Bottleneck Analysis

The real bottleneck is now **Layer 3 (Settlement)** at ~65 TPS.

To improve beyond 65 TPS:
- Use faster L2 (Arbitrum, Solana, EigenDA)
- Your own settlement chain
- Multi-chain parallel settlement

## Files

- `periodic_zk.go` - Go implementation with HTTP endpoints
- `bench/stats_bench.go` - Batching benchmark code
- `bench/circuits/` - Circom circuits + snarkjs