"""
Momentum Trading Strategy
Buys when price goes up, sells when price goes down.
Uses simple technical indicators to identify momentum.
"""

from decimal import Decimal
from typing import List

from pydantic import Field

from hummingbot.core.data_type.common import MarketDict, PriceType, TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig, CandlesConfigDataType
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.position_executor.data_types import (
    PositionExecutorConfig,
    TripleBarrierConfig,
)
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class MomentumStrategyConfig(ControllerConfigBase):
    """Configuration for Momentum Trading Strategy"""
    controller_name: str = "momentum_strategy"
    controller_type: str = "momentum"

    # Exchange and trading pair
    connector_name: str = Field(
        default="binance",
        description="Exchange connector"
    )
    trading_pair: str = Field(
        default="ETH-USDT",
        description="Trading pair"
    )

    # Momentum Parameters
    short_window: int = Field(
        default=5,
        description="Short moving average period (candles)"
    )
    long_window: int = Field(
        default=20,
        description="Long moving average period (candles)"
    )
    candle_interval: str = Field(
        default="1m",
        description="Candle interval (1m, 5m, 15m, 1h, 4h, 1d)"
    )

    # Position Management
    position_amount_quote: Decimal = Field(
        default=Decimal("500"),
        description="Amount for each position in quote asset"
    )
    take_profit_pct: Decimal = Field(
        default=Decimal("2"),
        description="Take profit percentage (e.g., 2 = 2%)"
    )
    stop_loss_pct: Decimal = Field(
        default=Decimal("1"),
        description="Stop loss percentage (e.g., 1 = 1%)"
    )
    max_positions: int = Field(
        default=3,
        description="Maximum open positions at once"
    )

    # Candles configuration
    candles_config: List[CandlesConfig] = Field(
        default_factory=lambda: [
            CandlesConfig(
                connector_name="binance",
                trading_pair="ETH-USDT",
                interval="1m",
                max_records=100,
                data_type=CandlesConfigDataType.TRADING_PAIR
            )
        ]
    )

    def update_markets(self, markets: MarketDict) -> MarketDict:
        return markets.add_or_update(self.connector_name, self.trading_pair)


class MomentumStrategy(ControllerBase):
    """
    Momentum Trading Strategy

    Uses moving average crossover to identify momentum:
    - BUY when short MA > long MA (uptrend)
    - SELL when short MA < long MA (downtrend)
    - Uses position executor for proper stop loss and take profit management
    """

    def __init__(self, config: MomentumStrategyConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config

    async def update_processed_data(self):
        """Calculate moving averages and momentum signals"""
        candles_data = self.get_candles(
            self.config.connector_name,
            self.config.trading_pair,
            self.config.candle_interval
        )

        if candles_data is None or len(candles_data) < self.config.long_window:
            self.processed_data = {
                "signal": "NEUTRAL",
                "short_ma": None,
                "long_ma": None,
                "price": None,
                "can_trade": False
            }
            return

        # Get closing prices
        closes = [candle.close for candle in candles_data]

        # Calculate simple moving averages
        short_ma = sum(closes[-self.config.short_window:]) / self.config.short_window
        long_ma = sum(closes[-self.config.long_window:]) / self.config.long_window

        # Determine signal
        if short_ma > long_ma:
            signal = "BUY"  # Uptrend
        elif short_ma < long_ma:
            signal = "SELL"  # Downtrend
        else:
            signal = "NEUTRAL"

        current_price = closes[-1]

        self.processed_data = {
            "signal": signal,
            "short_ma": short_ma,
            "long_ma": long_ma,
            "price": current_price,
            "can_trade": True
        }

    def determine_executor_actions(self) -> list[ExecutorAction]:
        """Create buy/sell orders based on momentum signal"""
        if not self.processed_data.get("can_trade"):
            return []

        actions = []
        signal = self.processed_data["signal"]

        # Count active positions
        active_executors = len([e for e in self.executors_info if e.is_active])

        # Only open new positions if below max
        if active_executors < self.config.max_positions:
            if signal == "BUY":
                side = TradeType.BUY
            elif signal == "SELL":
                side = TradeType.SELL
            else:
                return []

            # Calculate amount
            amount = self.config.position_amount_quote / self.processed_data["price"]

            # Create position executor with stop loss and take profit
            tp_price = self.processed_data["price"] * (
                1 + (self.config.take_profit_pct / Decimal("100"))
            ) if side == TradeType.BUY else self.processed_data["price"] * (
                1 - (self.config.take_profit_pct / Decimal("100"))
            )

            sl_price = self.processed_data["price"] * (
                1 - (self.config.stop_loss_pct / Decimal("100"))
            ) if side == TradeType.BUY else self.processed_data["price"] * (
                1 + (self.config.stop_loss_pct / Decimal("100"))
            )

            config = PositionExecutorConfig(
                timestamp=self.market_data_provider.time(),
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                side=side,
                entry_price=self.processed_data["price"],
                amount=amount,
                triple_barrier_config=TripleBarrierConfig(
                    stop_loss_price=sl_price,
                    take_profit_price=tp_price,
                ),
            )

            actions.append(CreateExecutorAction(
                controller_id=self.config.id,
                executor_config=config
            ))

        return actions
