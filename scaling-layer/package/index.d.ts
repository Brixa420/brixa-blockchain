/**
 * WrathScaler - TypeScript Definitions
 * Drop-in infinite TPS scaling layer for any blockchain
 */

export interface ScalingConfig {
  shards?: number;
  validatorsPerShard?: number;
  txBatchSize?: number;
  batchInterval?: number;
  router?: 'hash' | 'round-robin' | 'geographic';
}

export interface Transaction {
  from?: string;
  to: string;
  to?: string;
  amount: number | string;
  value?: number | string;
  data?: string;
  nonce?: number;
  gasPrice?: string;
  gas?: number;
}

export interface ChainHandler {
  submitBatch(transactions: Transaction[]): Promise<string[]>;
  getShardForAddress(address: string, shardCount: number): number;
}

export interface Stats {
  chain: string;
  shards: number;
  queued: number;
  processed: number;
  failed: number;
}

export class WrathScaler {
  constructor(chain: string, options?: ScalingConfig);
  
  setHandler(handler: ChainHandler): void;
  start(): Promise<void>;
  stop(): void;
  submit(tx: Transaction): Promise<string>;
  submitBatch(txs: Transaction[]): Promise<string[]>;
  getStats(): Stats;
  getShardForAddress(address: string): number;
}

export class BitcoinHandler implements ChainHandler {
  constructor(rpcUrl?: string);
  submitBatch(transactions: Transaction[]): Promise<string[]>;
  getShardForAddress(address: string, shardCount: number): number;
}

export class EthereumHandler implements ChainHandler {
  constructor(web3Provider: string);
  submitBatch(transactions: Transaction[]): Promise<string[]>;
  getShardForAddress(address: string, shardCount: number): number;
}

export class SolanaHandler implements ChainHandler {
  constructor(rpcUrl: string);
  submitBatch(transactions: Transaction[]): Promise<string[]>;
  getShardForAddress(address: string, shardCount: number): number;
}

export default WrathScaler;