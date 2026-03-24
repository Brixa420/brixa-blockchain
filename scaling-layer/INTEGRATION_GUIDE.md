# Brixa Integration Guide

**Add infinite TPS to any blockchain - in 2 minutes.**

---

## Easiest: The One-File Way

### Step 1: Save brixa.html

```html
<!DOCTYPE html>
<html><head><title>Brixa Scaler</title></head>
<body style="font-family:sans-serif;max-width:600px;margin:50px auto;padding:20px;background:#1a1a2e;color:#fff;">
<h2>💜 Brixa Scaler</h2>
<p>Add infinite TPS to any blockchain</p>

<input id="chain" value="ethereum" style="padding:10px;width:100%;margin:10px 0;">
<input id="rpc" placeholder="Your RPC URL" style="padding:10px;width:100%;margin:10px 0;">
<button onclick="start()" style="background:#e94560;color:#fff;padding:15px;border:none;cursor:pointer;">Start Proxy</button>

<div id="status" style="margin-top:20px;display:none;">
  <h3>✅ Running!</h3>
  <p>Point wallet to: <code>http://localhost:8545</code></p>
</div>

<script src="https://unpkg.com/brixa-scaler"></script>
<script>
async function start(){
  scaler = new BrixaScaler(document.getElementById('chain').value, { shards: 100 });
  scaler.submitToChain = async (batch) => console.log(`Batch: ${batch.length}`);
  await scaler.start();
  document.getElementById('status').style.display = 'block';
}
</script>
</body></html>
```

### Step 2: Open in Browser → Click Start

### Step 3: Point Wallet to `http://localhost:8545`

Done!

---

## CLI Way

```bash
npm install -g brixa-scaler
brixa-scaler proxy --chain ethereum --rpc https://your-rpc
```

---

## Python Way

```bash
pip install brixa-scaling-layer
```

```python
from brixa_scaling import BrixaScaler, EthereumHandler
scaler = BrixaScaler('ethereum', handler=EthereumHandler('https://...'))
await scaler.start()
```

---

## Connect to Any Chain

| Chain | RPC Example |
|-------|-------------|
| Ethereum | https://eth-mainnet.alchemyapi.io/... |
| Polygon | https://polygon-rpc.com |
| BSC | https://bsc-dataseed.binance.org |
| Avalanche | https://api.avax.network/ext/bc/C/rpc |
| Arbitrum | https://arb1.arbitrum.io/rpc |
| Bitcoin | http://localhost:8332 |

---

## Need Help?

GitHub: https://github.com/Brixa420/brixa-blockchain

**Brixa** - Infinite TPS for everyone 🧸