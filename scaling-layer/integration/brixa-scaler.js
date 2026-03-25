/**
 * BrixaScaler - VPN for TPS
 * Real implementation that connects to actual blockchains
 */

const { EthereumHandler, BitcoinHandler, SolanaHandler } = require('./real-handlers');

class BrixaScaler {
  /**
   * @param {string} chain - 'ethereum', 'bitcoin', 'solana', 'polygon', etc.
   * @param {object} options - { shards: 100, batchSize: 10000, batchInterval: 100 }
   */
  constructor(chain, options = {}) {
    this.chain = chain.toLowerCase();
    this.options = {
      shards: options.shards || 100,
      batchSize: options.batchSize || 10000,
      batchInterval: options.batchInterval || 100,
      router: options.router || 'hash'
    };
    
    this.handler = null;
    this.queue = [];
    this.shards = new Array(this.options.shards).fill(null).map(() => []);
    this.running = false;
    this.processor = null;
    this.stats = {
      queued: 0,
      processed: 0,
      failed: 0,
      shards: this.options.shards
    };
  }

  /**
   * Set the chain handler
   * @param {EthereumHandler|BitcoinHandler|SolanaHandler} handler
   */
  setHandler(handler) {
    this.handler = handler;
  }

  /**
   * Set handler by chain name (auto-detect)
   */
  setChain(rpcUrl, privateKey = null) {
    switch (this.chain) {
      case 'ethereum':
      case 'polygon':
      case 'bsc':
      case 'avalanche':
      case 'arbitrum':
      case 'optimism':
      case 'base':
      case 'fantom':
        this.handler = new EthereumHandler(rpcUrl, privateKey);
        break;
      case 'bitcoin':
      case 'btc':
      case 'litecoin':
      case 'dogecoin':
        this.handler = new BitcoinHandler({ rpcUrl, rpcUser: privateKey?.rpcUser, rpcPass: privateKey?.rpcPass });
        break;
      case 'solana':
        this.handler = new SolanaHandler(rpcUrl);
        break;
      default:
        throw new Error(`Unknown chain: ${this.chain}`);
    }
  }

  /**
   * Start the scaler - begins processing transactions
   */
  async start() {
    if (this.running) return;
    
    if (!this.handler) {
      throw new Error('No handler set. Use setHandler() or setChain()');
    }
    
    this.running = true;
    
    // Start batch processor
    this.processor = setInterval(async () => {
      await this.processBatch();
    }, this.options.batchInterval);
    
    console.log(`✅ BrixaScaler started on ${this.chain} with ${this.options.shards} shards`);
  }

  /**
   * Stop the scaler
   */
  stop() {
    this.running = false;
    if (this.processor) {
      clearInterval(this.processor);
      this.processor = null;
    }
  }

  /**
   * Submit a transaction to the queue
   * @param {object} tx - { to, value, data, from, etc. }
   * @returns {string} Transaction ID
   */
  submit(tx) {
    const txId = `tx_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    const txWithId = { ...tx, id: txId, chain: this.chain, timestamp: Date.now() };
    
    // Route to shard
    const shardIndex = this.getShardIndex(tx.to || tx.from || '');
    this.shards[shardIndex].push(txWithId);
    
    this.stats.queued = this.queue.length;
    
    return txId;
  }

  /**
   * Get shard index for an address
   */
  getShardIndex(address) {
    if (!this.handler) {
      return Math.floor(Math.random() * this.options.shards);
    }
    return this.handler.getShardForAddress(address, this.options.shards);
  }

  /**
   * Process all shards - send batches to chain
   */
  async processBatch() {
    for (let i = 0; i < this.shards.length; i++) {
      const shard = this.shards[i];
      if (shard.length === 0) continue;
      
      // Get up to batchSize transactions
      const batch = shard.splice(0, this.options.batchSize);
      
      try {
        const results = await this.handler.submitBatch(batch);
        
        // Update stats
        this.stats.processed += batch.length;
        this.stats.queued = this.getTotalQueued();
        
        // Log results
        const successful = results.filter(r => r !== null).length;
        console.log(`📦 Shard ${i}: Sent ${batch.length} txs, ${successful} successful`);
        
      } catch (error) {
        console.error(`❌ Shard ${i} failed: ${error.message}`);
        this.stats.failed += batch.length;
        
        // Re-queue failed transactions
        shard.unshift(...batch);
      }
    }
  }

  /**
   * Get total queued transactions
   */
  getTotalQueued() {
    return this.shards.reduce((sum, shard) => sum + shard.length, 0);
  }

  /**
   * Get current stats
   */
  getStats() {
    return {
      chain: this.chain,
      shards: this.stats.shards,
      queued: this.getTotalQueued(),
      processed: this.stats.processed,
      failed: this.stats.failed,
      running: this.running
    };
  }
}

// Export for Node.js
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { BrixaScaler, EthereumHandler, BitcoinHandler, SolanaHandler };
}

// Export for browser
if (typeof window !== 'undefined') {
  window.BrixaScaler = BrixaScaler;
  window.BrixaScaler.handlers = { EthereumHandler, BitcoinHandler, SolanaHandler };
}