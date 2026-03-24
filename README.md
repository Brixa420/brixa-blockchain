# Wrath of Cali Blockchain

> ⚠️ **Warning: This is experimental and untested code.** 
> Do not use for production or with real funds. Use at your own risk.
> 
> **Note:** This is NOT a real, functioning blockchain. All values ( TPS, tokenomics, etc.) 
> are placeholders to demonstrate the infinite TPS architecture concept.

**Created by Laura Wolf (Brixa420)** - 2026

A lightweight layered blockchain for gaming economies with **infinite TPS scaling**.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-yellow.svg)
![Go](https://img.shields.io/badge/go-1.21+-blue.svg)

## Features

- ⚡ **1-second block times** - Fast block production
- 🚀 **Infinite TPS Scaling** - Horizontal sharding for unlimited throughput
- 🔒 **Proof of Stake** - Secure validator consensus
- 💰 **Native Token (CAL)** - In-game cryptocurrency
- 🎮 **Gaming-Optimized** - Designed for game economies
- 🌐 **Layered Architecture** - Scalable validator network
- 📱 **Lightweight** - Run on minimal hardware

## Performance

| Configuration | TPS |
|--------------|-----|
| Single Shard | 1,000,000 |
| 10 Shards | 10,000,000 |
| 100 Shards | 100,000,000+ |

**TPS = Validators × BatchesPerBlock × TxsPerBatch**

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       TPS SCALING                               │
│   More Validators = More TPS   |   More Shards = More TPS     │
└─────────────────────────────────────────────────────────────────┘

         ┌─────────────────────────────────────┐
         │         Shard Router                 │
         │  (Routes to main nodes by address)  │
         └─────────────────────────────────────┘
                   ▲           ▲           ▲
          ┌────────┴───┐ ┌─────┴─────┐ ┌───┴────────┐
          │ Main Node  │ │ Main Node │ │ Main Node  │
          │  (Shard 0) │ │ (Shard 1) │ │ (Shard N)  │
          └─────────────┘ └───────────┘ └────────────┘
                ▲               ▲              ▲
           [Validators]    [Validators]   [Validators]
           (parallel block production on each shard)
```

### How It Works

1. **Address-Based Routing**: `shard_id = hash(address) % total_shards`
2. **Parallel Block Production**: Each shard produces blocks independently
3. **Cross-Shard TX**: Lock/Proof/Verify protocol for multi-shard transactions
4. **Auto-Scaling**: Network adds shards when queue depth > 10,000

## Quick Start

### Python Implementation

```bash
# Clone the repository
git clone https://github.com/wrath-of-cali/blockchain.git
cd blockchain

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run main node
python main_node.py

# In another terminal - run validator
python validator.py --stake 1000
```

### Go Implementation (Faster)

```bash
# Build Go node
cd blockchain
go build -o node node.go

# Run
./node --mode main  # Main node
./node --mode validator --stake 1000  # Validator
```

### Run with Sharding (Infinite TPS)

```bash
# Start shard router (load balancer)
./go_router

# Launch multiple main nodes (shards)
./launch_shards.sh --count 10  # Start 10 shards

# Auto-scaling enabled
./auto_scaler  # Monitors and adds shards as needed
```

### Scale to 100M+ TPS

```bash
# Deploy 100 shards for maximum throughput
./launch_shards.sh --count 100 --auto-scale
```

## Documentation

- [Whitepaper](./blockchain/WHITEPAPER.md) - Full technical details
- [Specification](./blockchain/SPEC.md) - Architecture overview
- [Scaling Spec](./blockchain/SPEC_SCALING.md) - Sharding design

## API Endpoints

```bash
# Health check
curl http://localhost:8001/health

# Get block
curl http://localhost:8001/block/0

# Check balance
curl http://localhost:8001/balance/CAL...

# Broadcast transaction
curl -X POST http://localhost:8001/broadcast \
  -H "Content-Type: application/json" \
  -d '{"from":"...","to":"...","amount":100}'

# List validators
curl http://localhost:8001/validators
```

## Architecture

```
┌─────────────────────────────────────┐
│           Main Node                 │
│  - Block producer (1s interval)     │
│  - Verifies validator batches      │
└─────────────────────────────────────┘
         ▲              ▲
         │              │
    [Batch]        [Batch]
         │              │
┌────────┴──┐    ┌──────┴─────┐
│Validator │    │ Validator  │
│  Node    │    │   Node     │
└──────────┘    └────────────┘
```

## Tokenomics

- **Total Supply**: 100M CAL
- **Block Reward**: 1 CAL (1% annual decrease)
- **Minimum Stake**: 1,000 CAL
- **Staking APR**: ~12%

## Supported Languages

| Language | Files | Status |
|----------|-------|--------|
| Python | core.py, validator.py, wallet.py | Stable |
| Go | node.go, pos_node.go | Stable |
| JavaScript/TypeScript | Coming soon | Planned |

## Contributing

1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Submit a PR

## License

MIT License - see LICENSE file for details.

---

Built with ❤️ by the Wrath of Cali Team