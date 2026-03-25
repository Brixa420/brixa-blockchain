/**
 * BrixaScaler RPC Proxy Server
 * Run as middleware between wallet and blockchain
 * 
 * Usage:
 *   node server.js --chain ethereum --rpc https://your-rpc-url --port 8545
 */

const http = require('http');
const { BrixaScaler, EthereumHandler, BitcoinHandler, SolanaHandler } = require('./brixa-scaler');

// Parse command line arguments
const args = process.argv.slice(2);
const config = {
  chain: 'ethereum',
  rpc: null,
  port: 8545,
  shards: 100,
  batchSize: 10000
};

for (let i = 0; i < args.length; i += 2) {
  const key = args[i].replace('--', '');
  const value = args[i + 1];
  if (key === 'chain') config.chain = value;
  if (key === 'rpc') config.rpc = value;
  if (key === 'port') config.port = parseInt(value);
  if (key === 'shards') config.shards = parseInt(value);
  if (key === 'batch-size') config.batchSize = parseInt(value);
}

// Check required args
if (!config.rpc) {
  console.log('Usage: node server.js --chain ethereum --rpc https://your-rpc-url [--port 8545] [--shards 100] [--batch-size 10000]');
  console.log('\nSupported chains: ethereum, bitcoin, solana, polygon, bsc, avalanche, arbitrum, optimism');
  process.exit(1);
}

// Create scaler
console.log(`\n🚀 Starting BrixaScaler...`);
console.log(`   Chain: ${config.chain}`);
console.log(`   RPC: ${config.rpc}`);
console.log(`   Shards: ${config.shards}\n`);

const scaler = new BrixaScaler(config.chain, {
  shards: config.shards,
  batchSize: config.batchSize,
  batchInterval: 100
});

// Set up handler based on chain
const chainLower = config.chain.toLowerCase();
if (chainLower === 'ethereum' || chainLower === 'polygon' || chainLower === 'bsc' || 
    chainLower === 'avalanche' || chainLower === 'arbitrum' || chainLower === 'optimism') {
  scaler.setHandler(new EthereumHandler(config.rpc));
} else if (chainLower === 'bitcoin' || chainLower === 'btc') {
  scaler.setHandler(new BitcoinHandler({ rpcUrl: config.rpc }));
} else if (chainLower === 'solana') {
  scaler.setHandler(new SolanaHandler(config.rpc));
}

// Start the scaler
scaler.start();

// Create HTTP proxy server
const server = http.createServer(async (req, res) => {
  // Enable CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }
  
  // Only handle POST (JSON-RPC)
  if (req.method !== 'POST') {
    res.writeHead(405, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Method not allowed' }));
    return;
  }
  
  let body = '';
  req.on('data', chunk => body += chunk);
  req.on('end', async () => {
    try {
      const rpc = JSON.parse(body);
      const { jsonrpc, method, params, id } = rpc;
      
      console.log(`📨 ${method}`);
      
      // Handle transaction methods through scaler
      if (method === 'eth_sendTransaction' || method === 'eth_sendRawTransaction') {
        const tx = params[0];
        
        // Submit to scaler
        const txId = scaler.submit(tx);
        
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          jsonrpc: '2.0',
          id,
          result: txId
        }));
        
        console.log(`   ✅ Queued: ${txId}`);
        
      } else if (method === 'eth_getTransactionReceipt') {
        // Pass through to RPC for receipts
        const result = await passThrough(config.rpc, method, params);
        
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ jsonrpc: '2.0', id, result }));
        
      } else if (method === 'eth_blockNumber' || method === 'eth_chainId' || 
                 method === 'eth_gasPrice' || method === 'eth_estimateGas') {
        // Read-only methods - pass through
        const result = await passThrough(config.rpc, method, params);
        
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ jsonrpc: '2.0', id, result }));
        
      } else if (method === 'eth_call') {
        // Read-only - pass through
        const result = await passThrough(config.rpc, method, params);
        
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ jsonrpc: '2.0', id, result }));
        
      } else {
        // Other methods - pass through
        const result = await passThrough(config.rpc, method, params);
        
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ jsonrpc: '2.0', id, result }));
      }
      
    } catch (error) {
      console.error(`   ❌ Error: ${error.message}`);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ 
        jsonrpc: '2.0', 
        id: 1, 
        error: { code: -32603, message: error.message } 
      }));
    }
  });
});

/**
 * Pass through JSON-RPC to backend RPC
 */
function passThrough(rpcUrl, method, params) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({
      jsonrpc: '2.0',
      method,
      params,
      id: 1
    });

    const url = new URL(rpcUrl);
    const isHttps = url.protocol === 'https:';
    const lib = isHttps ? require('https') : require('http');

    const options = {
      hostname: url.hostname,
      port: url.port || (isHttps ? 443 : 80),
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body)
      }
    };

    const req = lib.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          resolve(parsed.result);
        } catch (e) {
          reject(e);
        }
      });
    });

    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

// Start server
server.listen(config.port, () => {
  console.log(`\n✅ BrixaScaler proxy running on http://localhost:${config.port}`);
  console.log(`   Point your wallet RPC to: http://localhost:${config.port}\n`);
  
  // Stats reporter
  setInterval(() => {
    const stats = scaler.getStats();
    console.log(`📊 Stats: ${stats.queued} queued, ${stats.processed} processed, ${stats.failed} failed`);
  }, 5000);
});

// Handle shutdown
process.on('SIGINT', () => {
  console.log('\n🛑 Shutting down...');
  scaler.stop();
  server.close();
  process.exit(0);
});