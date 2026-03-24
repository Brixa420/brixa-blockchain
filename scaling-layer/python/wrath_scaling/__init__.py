"""
WrathScaler - Drop-in Infinite TPS Scaling Layer

Supports: Bitcoin, Ethereum, Solana, Polygon, BSC, Avalanche, and any blockchain

INSTALL:
    pip install wrath-scaling-layer

QUICK START:
    from wrath_scaling import WrathScaler, BitcoinHandler, EthereumHandler
    
    # Bitcoin
    scaler = WrathScaler('bitcoin', handler=BitcoinHandler())
    
    # Ethereum
    scaler = WrathScaler('ethereum', handler=EthereumHandler(web3_provider="https://..."))
    
    await scaler.start()
    await scaler.submit({'to': 'address', 'amount': 0.001})
"""

from .scaling import WrathScaler, ScalingConfig, ChainHandler
from .handlers import BitcoinHandler, EthereumHandler, SolanaHandler, PolygonHandler, BSCHandler

__version__ = "1.0.0"
__all__ = [
    'WrathScaler',
    'ScalingConfig', 
    'ChainHandler',
    'BitcoinHandler',
    'EthereumHandler',
    'SolanaHandler',
    'PolygonHandler',
    'BSCHandler',
]
