#!/usr/bin/env python3
"""Test one real WETH -> USDC swap on Sepolia, priced via Mainnet"""

import asyncio

from uniswap_live_trader import SEPOLIA_USDC, SEPOLIA_WETH, UniswapLiveTrader


async def main():
    print("\nSWAP TEST | Mainnet Pricing + Sepolia Execution\n")

    trader = UniswapLiveTrader()

    mainnet_price = trader.get_mainnet_price(1.0)
    weth_bal = trader.get_balance(SEPOLIA_WETH)
    usdc_bal = trader.get_balance(SEPOLIA_USDC)

    print(f"  Mainnet WETH/USDC: ${mainnet_price:.2f}")
    print(f"  Sepolia WETH: {weth_bal:.6f}")
    print(f"  Sepolia USDC: {usdc_bal:.2f}\n")

    if weth_bal < 0.05:
        print("Insufficient WETH (need 0.05)")
        return

    print("Executing: 0.05 WETH -> USDC on Sepolia...")
    tx_hash = trader.swap_weth_to_usdc(0.05)

    if tx_hash:
        await asyncio.sleep(2)
        weth_final = trader.get_balance(SEPOLIA_WETH)
        usdc_final = trader.get_balance(SEPOLIA_USDC)

        print(f"\n  TX: https://sepolia.etherscan.io/tx/{tx_hash}")
        print(f"  WETH: {weth_final:.6f} (was {weth_bal:.6f})")
        print(f"  USDC: {usdc_final:.2f} (was {usdc_bal:.2f})")
        print(
            f"  Mainnet value of swap: "
            f"${mainnet_price * 0.05:.2f}")
    else:
        print("Swap failed - check logs")


if __name__ == "__main__":
    asyncio.run(main())
