/**
 * BrixaScaler RPC Proxy Server
 * Run as middleware - NO API KEY NEEDED!
 * 
 * Usage:
 *   node server.js --chain ethereum --port 8545
 * 
 * That's it! Uses public RPCs automatically.
 */

const http = require('http');
const { BrixaScaler, PUBLIC_RPCS, getPublicRPC } = require('./brixa-scaler');

// Parse args
const args = process.argv.slice(2);
const config = {
  chain: 'ethereum',
  port: 8545,
  shards: 100,
  batchSize: 1000,
  demo: false
};

for (let i = 0; i < args.length; i += 2) {
  const key = args[i].replace('--', '');
  const value = args[i + 1];
  if (key === 'chain') config.chain = value;
  if (key === 'port') config.port = parseInt(value);
  if (key === 'shards') config.shards = parseInt(value);
  if (key === 'batch-size') config.batchSize = parseInt(value);
  if (key === 'demo') config.demo = true;
}

async function main() {
  console.log('\n' + '═'.repeat(50));
  console.log('💜 BrixaScaler - VPN for TPS');
  console.log('═'.repeat(50));
  console.log(`   Chain: ${config.chain}`);
  console.log(`   Port: ${config.port}`);
  console.log(`   Shards: ${config.shards}\n`);

  // Create scaler
  const scaler = new BrixaScaler(config.chain, {
    shards: config.shards,
    batchSize: config.batchSize,
    demo: config.demo
  });

  // Auto-start with public RPC
  await scaler.start();

  // Show available chains
  console.log('📡 Available chains (free public RPCs):');
  const chains = Object.keys(PUBLIC_RPCS).filter(c => c !== 'bitcoin');
  chains.forEach(c => console.log(`   - ${c}`));
  console.log('');

  // Create proxy server
  const server = http.createServer(async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
      res.writeHead(200);
      res.end();
      return;
    }

    if (req.method !== 'POST') {
      // Show status page
      const stats = scaler.getStats();
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(`
<!DOCTYPE html>
<html>
<head>
  <title>BrixaScaler - ${config.chain}</title>
  <style>
    body { font-family: system-ui; max-width: 600px; margin: 50px auto; padding: 20px; background: #1a1a2e; color: #fff; }
    h1 { color: #e94560; }
    .stats { background: #222; padding: 20px; border-radius: 10px; }
    .stat { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #333; }
    .label { color: #888; }
    code { background: #333; padding: 5px 10px; border-radius: 5px; }
    .chains { margin-top: 20px; }
  </style>
</head>
<body>
  <h1>💜 BrixaScaler</h1>
  <p><strong>VPN for TPS</strong> - Running on ${config.chain}</p>
  
  <div class="stats">
    <div class="stat"><span class="label">Chain</span><span>${stats.chain}</span></div>
    <div class="stat"><span class="label">Shards</span><span>${stats.shards}</span></div>
    <div class="stat"><span class="label">Queued</span><span>${stats.queued}</span></div>
    <div class="stat"><span class="label">Status</span><span>${stats.running ? '✅ Running' : '❌ Stopped'}</span></div>
  </div>
  
  <h3>Your Wallet RPC:</h3>
  <code>http://localhost:${config.port}</code>
  
  <div class="chains">
    <h3>Available:</h3>
    <code>ethereum</code> <code>polygon</code> <code>bsc</code> <code>avalanche</code>
    <code>arbitrum</code> <code>optimism</code> <code>solana</code>
  </div>
  
  <p><small>No API key needed! Using free public RPCs.</small></p>
  
  <div style="background: #ff9800; color: #000; padding: 15px; border-radius: 10px; margin-top: 20px; text-align: center;">
    <strong>⚠️ DEMO MODE</strong><br>
    Transactions are queued but NOT sent to chain.<br>
    To send real transactions, add your private key.
  </div>
</body>
</html>
      `);
      return;
    }

    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', async () => {
      try {
        const rpc = JSON.parse(body);
        const { jsonrpc, method, params, id } = rpc;

        console.log(`📨 ${method}`);

        // Handle transactions
        if (method === 'eth_sendTransaction' || method === 'eth_sendRawTransaction') {
          const tx = params[0] || {};
          const txId = scaler.submit(tx);

          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ jsonrpc: '2.0', id, result: txId }));
          console.log(`   ✅ Queued: ${txId}`);

        } else if (method === 'eth_blockNumber' || method === 'eth_chainId' || 
                   method === 'eth_gasPrice' || method === 'net_version') {
          // For demo, return fake but realistic responses
          const fakeResponses = {
            'eth_blockNumber': '0x10d4f1e',
            'eth_chainId': config.chain === 'ethereum' ? '0x1' : 
                           config.chain === 'polygon' ? '0x89' :
                           config.chain === 'bsc' ? '0x38' : '0x1',
            'eth_gasPrice': '0x4a817c800',
            'net_version': '1'
          };

          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ jsonrpc: '2.0', id, result: fakeResponses[method] || '0x0' }));

        } else {
          // Other methods - return success
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ jsonrpc: '2.0', id, result: null }));
        }

      } catch (error) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ jsonrpc: '2.0', id: 1, error: { code: -32603, message: error.message } }));
      }
    });
  });

  server.listen(config.port, () => {
    console.log('✅ Server running!');
    console.log(`   Point wallet to: http://localhost:${config.port}\n`);
    console.log('💜 BrixaScaler - VPN for TPS\n');
    console.log('⚠️  DEMO MODE - Transactions are queued but NOT sent to chain\n');
  });

  // Stats
  setInterval(() => {
    const stats = scaler.getStats();
    if (stats.queued > 0) {
      console.log(`📊 Queued: ${stats.queued} | Chain: ${stats.chain}`);
    }
  }, 5000);
}

main().catch(console.error);