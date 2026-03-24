"""
BrixaScaler - Drop-in Infinite TPS Scaling Layer

Supports: Bitcoin, Ethereum, Solana, Polygon, BSC, Avalanche, and any blockchain

INSTALL:
    pip install brixa-scaling-layer

QUICK START:
    from brixa_scaling import BrixaScaler, BitcoinHandler, EthereumHandler
    
    # Bitcoin
    scaler = BrixaScaler('bitcoin', handler=BitcoinHandler())
    
    # Ethereum
    scaler = BrixaScaler('ethereum', handler=EthereumHandler(web3_provider="https://..."))
    
    await scaler.start()
    await scaler.submit({'to': 'address', 'amount': 0.001})
"""

from .scaling import BrixaScaler, ScalingConfig, ChainHandler
from .handlers import BitcoinHandler, EthereumHandler, SolanaHandler, PolygonHandler, BSCHandler

__version__ = "1.0.0"
__all__ = [
    'BrixaScaler',
    'ScalingConfig', 
    'ChainHandler',
    'BitcoinHandler',
    'EthereumHandler',
    'SolanaHandler',
    'PolygonHandler',
    'BSCHandler',
]
