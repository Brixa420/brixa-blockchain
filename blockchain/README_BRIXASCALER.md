# BrixaScaler - Final Architecture

## Three Layers

| Layer | Component | Throughput | Status |
|-------|-----------|------------|--------|
| **1** | Batching (Merkle) | 5-17M TPS | ✅ |
| **2** | Verification (Periodic ZK) | 14K TPS | ✅ |
| **3** | Settlement (external L2) | ~65 TPS | ⚠️ |

> **Note:** 10-shard runs show ±19% variance (11.9M - 20.6M). Sub-linear scaling due to coordination overhead (28% efficiency at 10 shards).

## Periodic ZK Configuration

```javascript
{
    batchSize: 4,           // txs per Merkle batch
    zkPeriod: 1000,         // batches between ZK proofs
    proveTime: 284,         // ms per ZK proof
    verifyTime: 210         // ms per ZK verify
}
```

## How It Works

1. **Fast path:** Hash verification for every batch (16.5M → 500K effective)
2. **Slow path:** ZK proof every 1000 batches (cryptographic finality)
3. **Amortization:** 1 ZK proof covers 1000 batches = 4000 transactions

## Effective TPS (Honest)

| Mode | TPS | Notes |
|------|-----|-------|
| Single thread | 5-6M | Baseline |
| 10 threads | 11.9M - 20.6M | ±19% variance |
| With hash verify | ~500K | Hash-only fast path |
| With periodic ZK | ~14K | 1 proof / 1000 batches |
| Settlement | ~65 TPS | External chain bottleneck |

**Scaling efficiency:** 10 threads = 2.8x speedup (28% efficiency), not 10x

## Bottleneck Analysis

The real bottleneck is now **Layer 3 (Settlement)** at ~65 TPS, not Layer 2.

To improve beyond 65 TPS:
- Use faster L2 (Arbitrum, Solana, EigenDA)
- Your own settlement chain
- Multi-chain parallel settlement