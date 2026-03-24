"""
Chain Handlers for WrathScaler
Each handler implements blockchain-specific submission logic
"""

import hashlib
import asyncio
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class ChainHandler(ABC):
    """Abstract base class for blockchain handlers"""
    
    @abstractmethod
    async def submit_batch(self, transactions: List[Dict]) -> List[str]:
        """Submit batch of transactions to the blockchain"""
        pass
    
    def get_shard_for_address(self, address: str, shard_count: int) -> int:
        """Get deterministic shard for an address"""
        address = address.lower().strip()
        
        # Generic hash
        hash_val = 0
        for i, char in enumerate(address):
            hash_val = ((hash_val << 5) - hash_val) + ord(char)
            hash_val = hash_val & 0xffffffff
        
        return hash_val % shard_count


class BitcoinHandler(ChainHandler):
    """Bitcoin and Bitcoin-like chains (Litecoin, Dogecoin, etc.)"""
    
    def __init__(self, rpc_url: Optional[str] = None, rpc_user: Optional[str] = None, rpc_pass: Optional[str] = None):
        """
        Initialize Bitcoin handler
        
        Args:
            rpc_url: Bitcoin Core RPC URL (e.g., http://localhost:8332)
            rpc_user: RPC username
            rpc_pass: RPC password
        """
        self.rpc_url = rpc_url or "http://localhost:8332"
        self.rpc_user = rpc_user
        self.rpc_pass = rpc_pass
    
    async def submit_batch(self, transactions: List[Dict]) -> List[str]:
        """
        Submit batch to Bitcoin network
        
        Each transaction should have:
        - to: Bitcoin address (bc1... or legacy)
        - amount: Amount in BTC (not satoshis)
        - fee: Fee in BTC (optional)
        """
        txids = []
        
        for tx in transactions:
            try:
                txid = await self._send_bitcoin_tx(tx)
                txids.append(txid)
            except Exception as e:
                txids.append(f"failed_{hashlib.sha256(str(tx).encode()).hexdigest()[:8]}")
        
        return txids
    
    async def _send_bitcoin_tx(self, tx: Dict) -> str:
        """Send a single Bitcoin transaction"""
        # In production, use python-bitcoinrpc or bitcoincashlib
        
        # Example implementation:
        # import bitcoinrpc
        # conn = bitcoinrpc.connect_to_remote(self.rpc_url, self.rpc_user, self.rpc_pass)
        # tx = conn.createrawtransaction([{"txid": tx["from_txid"], "vout": tx["from_vout"]}])
        # tx = conn.signrawtransaction(tx)
        # return conn.sendrawtransaction(tx["hex"])
        
        return f"btc_{hashlib.sha256(str(tx).encode()).hexdigest()[:16]}"
    
    def get_shard_for_address(self, address: str, shard_count: int) -> int:
        """Bitcoin-specific shard routing"""
        address = address.lower().strip()
        
        # Handle bech32 (bc1...) - take the data part after hrp
        # Handle base58 - direct hash
        hash_val = 0
        for char in address:
            hash_val = ((hash_val << 5) - hash_val) + ord(char)
            hash_val = hash_val & 0xffffffff
        
        return hash_val % shard_count


class EthereumHandler(ChainHandler):
    """Ethereum and EVM-compatible chains"""
    
    def __init__(self, web3_provider: str, private_key: Optional[str] = None):
        """
        Initialize Ethereum handler
        
        Args:
            web3_provider: RPC URL (e.g., https://eth-mainnet.alchemyapi.io/v2/...)
            private_key: Private key for signing (optional)
        """
        self.web3_provider = web3_provider
        self.private_key = private_key
    
    async def submit_batch(self, transactions: List[Dict]) -> List[str]:
        """Submit batch to Ethereum/EVM chain"""
        tx_hashes = []
        
        for tx in transactions:
            try:
                tx_hash = await self._send_evm_tx(tx)
                tx_hashes.append(tx_hash)
            except Exception as e:
                tx_hashes.append(f"failed_{hashlib.sha256(str(tx).encode()).hexdigest()[:8]}")
        
        return tx_hashes
    
    async def _send_evm_tx(self, tx: Dict) -> str:
        """Send a single EVM transaction"""
        # In production, use web3.py
        # from web3 import Web3
        # w3 = Web3(Web3.HTTPProvider(self.web3_provider))
        # nonce = w3.eth.get_transaction_count(self.address)
        # tx = {...}
        # signed = w3.eth.account.sign_transaction(tx, self.private_key)
        # return w3.eth.send_raw_transaction(signed.rawTransaction)
        
        return f"0x{hashlib.sha256(str(tx).encode()).hexdigest()[:16]}"
    
    def get_shard_for_address(self, address: str, shard_count: int) -> int:
        """EVM-specific shard routing (use last 40 chars of address)"""
        address = address.lower().strip().replace('0x', '')
        
        hash_val = 0
        for i in range(min(40, len(address))):
            hash_val = ((hash_val << 5) - hash_val) + ord(address[i])
            hash_val = hash_val & 0xffffffff
        
        return hash_val % shard_count


class PolygonHandler(EthereumHandler):
    """Polygon (MATIC) - uses EVM"""
    
    def __init__(self, rpc_url: str = "https://polygon-rpc.com", private_key: Optional[str] = None):
        super().__init__(rpc_url, private_key)


class BSCHandler(EthereumHandler):
    """Binance Smart Chain - uses EVM"""
    
    def __init__(self, rpc_url: str = "https://bsc-dataseed.binance.org", private_key: Optional[str] = None):
        super().__init__(rpc_url, private_key)


class AvalancheHandler(EthereumHandler):
    """Avalanche C-Chain - uses EVM"""
    
    def __init__(self, rpc_url: str = "https://api.avax.network/ext/bc/C/rpc", private_key: Optional[str] = None):
        super().__init__(rpc_url, private_key)


class SolanaHandler(ChainHandler):
    """Solana blockchain"""
    
    def __init__(self, rpc_url: str = "https://api.mainnet-beta.solana.com", private_key: Optional[str] = None):
        self.rpc_url = rpc_url
        self.private_key = private_key
    
    async def submit_batch(self, transactions: List[Dict]) -> List[str]:
        """Submit batch to Solana"""
        signatures = []
        
        for tx in transactions:
            try:
                sig = await self._send_solana_tx(tx)
                signatures.append(sig)
            except Exception as e:
                signatures.append(f"failed_{hashlib.sha256(str(tx).encode()).hexdigest()[:8]}")
        
        return signatures
    
    async def _send_solana_tx(self, tx: Dict) -> str:
        """Send a single Solana transaction"""
        # In production, use solders or solana-py
        # from solders.keypair import Keypair
        # from solders.transaction import Transaction
        # ... build and send transaction
        
        return f"{hashlib.sha256(str(tx).encode()).hexdigest()[:16]}"
    
    def get_shard_for_address(self, address: str, shard_count: int) -> int:
        """Solana-specific shard routing"""
        address = address.lower().strip()
        
        hash_val = 0
        for i in range(min(44, len(address))):
            hash_val = ((hash_val << 5) - hash_val) + ord(address[i])
            hash_val = hash_val & 0xffffffff
        
        return hash_val % shard_count


class OptimismHandler(EthereumHandler):
    """Optimism - uses EVM"""
    
    def __init__(self, rpc_url: str = "https://mainnet.optimism.io", private_key: Optional[str] = None):
        super().__init__(rpc_url, private_key)


class ArbitrumHandler(EthereumHandler):
    """Arbitrum - uses EVM"""
    
    def __init__(self, rpc_url: str = "https://arb1.arbitrum.io/rpc", private_key: Optional[str] = None):
        super().__init__(rpc_url, private_key)