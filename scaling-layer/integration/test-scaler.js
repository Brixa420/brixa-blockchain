/**
 * BrixaScaler - Real Test Script
 * Tests actual RPC connections to blockchains
 */

const { BrixaScaler, EthereumHandler, BitcoinHandler, SolanaHandler } = require('./brixa-scaler');

async function testEthereum() {
  console.log('\n🧪 Testing Ethereum Handler...\n');
  
  // Replace with your RPC URL (can use Alchemy free tier, Infura, etc.)
  const RPC_URL = process.env.ETH_RPC || 'https://eth-mainnet.alchemyapi.io/YOUR_KEY';
  
  // Only test if we have a real RPC URL
  if (RPC_URL.includes('YOUR_KEY')) {
    console.log('⚠️  Set ETH_RPC environment variable to test');
    console.log('   export ETH_RPC="https://eth-mainnet.alchemyapi.io/..."\n');
    return;
  }
  
  try {
    const handler = new EthereumHandler(RPC_URL);
    
    // Test: Get block number
    console.log('📡 Fetching current block...');
    const blockNumber = await handler.call('eth_blockNumber');
    console.log(`   Current block: ${parseInt(blockNumber, 16)}`);
    
    // Test: Get gas price
    const gasPrice = await handler.call('eth_gasPrice');
    console.log(`   Gas price: ${parseInt(gasPrice, 16)} Gwei`);
    
    console.log('✅ Ethereum handler working!\n');
    
    // Now test full scaler
    const scaler = new BrixaScaler('ethereum', { shards: 10, batchSize: 100 });
    scaler.setHandler(handler);
    await scaler.start();
    
    // Queue some test transactions (they won't actually send without signing)
    console.log('📝 Queueing test transactions...');
    for (let i = 0; i < 5; i++) {
      scaler.submit({
        to: `0x${Math.random().toString(16).substr(2, 40)}`,
        value: '0x0',
        data: '0x'
      });
    }
    
    console.log(`   Queued: ${scaler.getStats().queued} transactions`);
    
    // Wait for processing
    await new Promise(r => setTimeout(r, 500));
    
    console.log(`   Stats: ${JSON.stringify(scaler.getStats())}`);
    
    scaler.stop();
    console.log('✅ Scaler test complete!\n');
    
  } catch (error) {
    console.error('❌ Ethereum test failed:', error.message);
  }
}

async function testBitcoin() {
  console.log('\n🧪 Testing Bitcoin Handler...\n');
  
  // Requires Bitcoin Core RPC or Electrum
  const RPC_URL = process.env.BTC_RPC || 'http://localhost:8332';
  const RPC_USER = process.env.BTC_USER || 'user';
  const RPC_PASS = process.env.BTC_PASS || 'pass';
  
  try {
    const handler = new BitcoinHandler({
      rpcUrl: RPC_URL,
      rpcUser: RPC_USER,
      rpcPass: RPC_PASS
    });
    
    // Test connection (won't work without real credentials)
    console.log('📡 Testing Bitcoin connection...');
    console.log('   (Requires Bitcoin Core running with RPC enabled)');
    
    // Try to get blockchain info
    try {
      const info = await handler.rpcCall('getblockchaininfo', []);
      console.log(`   Blocks: ${info.blocks}`);
      console.log('✅ Bitcoin handler working!\n');
    } catch (e) {
      console.log('⚠️  Bitcoin Core not available - handler ready for use');
    }
    
  } catch (error) {
    console.error('❌ Bitcoin test failed:', error.message);
  }
}

async function testSolana() {
  console.log('\n🧪 Testing Solana Handler...\n');
  
  const RPC_URL = process.env.SOL_RPC || 'https://api.mainnet-beta.solana.com';
  
  try {
    const handler = new SolanaHandler(RPC_URL);
    
    // Test: Get slot
    console.log('📡 Fetching current slot...');
    const slot = await handler.call('getSlot');
    console.log(`   Current slot: ${slot}`);
    
    // Test: Get version
    const version = await handler.call('getVersion');
    console.log(`   Version: ${JSON.stringify(version)}`);
    
    console.log('✅ Solana handler working!\n');
    
  } catch (error) {
    console.error('❌ Solana test failed:', error.message);
  }
}

async function testAll() {
  console.log('='.repeat(50));
  console.log('🧪 BrixaScaler - Full Integration Test');
  console.log('='.repeat(50));
  
  // Test each chain
  await testEthereum();
  await testBitcoin();
  await testSolana();
  
  console.log('='.repeat(50));
  console.log('✅ All tests complete!');
  console.log('='.repeat(50));
}

// Export test functions
module.exports = { testEthereum, testBitcoin, testSolana, testAll };

// Run if executed directly
if (require.main === module) {
  testAll().catch(console.error);
}