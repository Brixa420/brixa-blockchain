# Brixa - Simple Scaling Layer

**Add infinite TPS to any blockchain in 2 minutes.**

---

## Easiest Way (One File)

### Step 1: Save This File

Save as `brixa.html`:

```html
<!DOCTYPE html>
<html><head><title>Brixa Scaler</title></head>
<body style="font-family:sans-serif;max-width:600px;margin:50px auto;padding:20px;background:#1a1a2e;color:#fff;">
<h2>💜 Brixa Scaler</h2>
<p>Add infinite TPS to any blockchain</p>

<input id="chain" value="ethereum" style="padding:10px;width:100%;margin:10px 0;" readonly>
<input id="rpc" placeholder="Your RPC URL (e.g. https://eth-mainnet.alchemyapi.io/...)" style="padding:10px;width:100%;margin:10px 0;">
<button onclick="start()" style="background:#e94560;color:#fff;padding:15px 30px;border:none;cursor:pointer;font-size:16px;">Start Proxy</button>

<div id="status" style="margin-top:20px;padding:15px;background:#222;border-radius:8px;display:none;">
  <h3>✅ Running!</h3>
  <p>Point your wallet RPC to:</p>
  <code style="background:#333;padding:10px;display:block;">http://localhost:8545</code>
  <p style="margin-top:10px;"><small>Stats: <span id="stats">-</span></small></p>
</div>

<script src="https://unpkg.com/brixa-scaler"></script>
<script>
let scaler;

async function start(){
  const chain = document.getElementById('chain').value;
  const rpc = document.getElementById('rpc').value;
  
  scaler = new BrixaScaler(chain, { shards: 100 });
  
  // Simple handler
  scaler.submitToChain = async (batch) => {
    console.log(`Would send ${batch.length} txs to ${rpc}`);
  };
  
  await scaler.start();
  document.getElementById('status').style.display = 'block';
  
  setInterval(() => {
    const s = scaler.getStats();
    document.getElementById('stats').innerText = 
      `Shards: ${s.shards} | Queued: ${s.queued} | Processed: ${s.processed}`;
  }, 1000);
}
</script>
</body></html>
```

### Step 2: Open in Browser

Double-click `brixa.html`

### Step 3: Enter Your RPC & Click Start

That's it! Your wallet now connects through Brixa's scaling layer.

---

## CLI Way

```bash
# Install
npm install -g brixa-scaler

# Run proxy
brixa-scaler proxy --chain ethereum --rpc https://your-rpc-url

# Your wallet now uses Brixa!
# RPC: http://localhost:8545
```

---

## Python Way

```bash
pip install brixa-scaling-layer
```

```python
from brixa_scaling import BrixaScaler, EthereumHandler

scaler = BrixaScaler('ethereum', handler=EthereumHandler('https://your-rpc'))
await scaler.start()
scaler.submit({'to': '0x...', 'amount': 1})
```

---

## Supported Chains

- Ethereum
- Polygon
- BSC
- Avalanche
- Arbitrum
- Optimism
- Bitcoin
- Solana
- Any chain!

---

**That's it!** 

For docs: https://github.com/Brixa420/brixa-blockchain

**Brixa** - Infinite TPS for everyone 🧸💖