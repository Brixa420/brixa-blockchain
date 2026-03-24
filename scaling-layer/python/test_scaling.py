"""
Test script for BrixaScaler Python package
"""

import asyncio
from brixa_scaling import BrixaScaler, BitcoinHandler, EthereumHandler


async def test_bitcoin():
    """Test Bitcoin handler"""
    handler = BitcoinHandler(rpc_url="http://localhost:8332")
    scaler = BrixaScaler('bitcoin', handler=handler)
    
    await scaler.start()
    
    # Submit test transactions
    for i in range(10):
        await scaler.submit({
            'to': f'bc1q{"a" * 38}{i}',
            'amount': 0.001 * (i + 1)
        })
    
    stats = scaler.get_stats()
    print(f"Bitcoin test: {stats}")
    
    await scaler.stop()


async def test_ethereum():
    """Test Ethereum handler"""
    handler = EthereumHandler(web3_provider="https://eth-mainnet.alchemyapi.io/")
    scaler = BrixaScaler('ethereum', handler=handler)
    
    await scaler.start()
    
    # Submit test transactions
    for i in range(10):
        await scaler.submit({
            'to': f'0x{"a" * 40}',
            'amount': 1e18 * (i + 1)
        })
    
    stats = scaler.get_stats()
    print(f"Ethereum test: {stats}")
    
    await scaler.stop()


async def main():
    print("Testing BrixaScaler...")
    
    print("\n--- Bitcoin ---")
    await test_bitcoin()
    
    print("\n--- Ethereum ---")
    await test_ethereum()
    
    print("\n✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(main())