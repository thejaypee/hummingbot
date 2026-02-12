#!/usr/bin/env python3
"""Test one real WETH → USDC swap on Uniswap V3 Sepolia"""

import asyncio
from uniswap_live_trader import UniswapLiveTrader

async def main():
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║  🔬 REAL UNISWAP SWAP TEST - Execute actual trade        ║")
    print("╚════════════════════════════════════════════════════════════╝\n")

    trader = UniswapLiveTrader()

    # Check balance
    weth_bal = trader.get_balance("0x7b79995e5f793A07Bc00c21412e50Ecae098E7f9")
    usdc_bal = trader.get_balance("0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238")

    print(f"📊 Current Balances:")
    print(f"   WETH: {weth_bal:.6f}")
    print(f"   USDC: {usdc_bal:.2f}\n")

    if weth_bal < 0.05:
        print("❌ Insufficient WETH to execute test trade")
        return

    print("💱 Executing REAL swap: 0.05 WETH → USDC")
    print("⏳ Waiting for confirmation on Sepolia blockchain...\n")

    result = trader.swap_weth_to_usdc(0.05)

    if result:
        print(f"\n✅ SWAP SUCCESSFUL!")
        print(f"📍 Transaction: https://sepolia.etherscan.io/tx/{result['tx']}")

        # Verify final balances
        await asyncio.sleep(2)
        weth_final = trader.get_balance("0x7b79995e5f793A07Bc00c21412e50Ecae098E7f9")
        usdc_final = trader.get_balance("0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238")

        print(f"\n📊 Final Balances:")
        print(f"   WETH: {weth_final:.6f} (was {weth_bal:.6f})")
        print(f"   USDC: {usdc_final:.2f} (was {usdc_bal:.2f})")
        print(f"\n✨ Proof of real trading: Check Etherscan link above")
    else:
        print("❌ Swap failed - check logs for details")

if __name__ == "__main__":
    asyncio.run(main())
