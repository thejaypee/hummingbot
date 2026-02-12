"""
DCA (Dollar Cost Averaging) Strategy
Automatically buys fixed amounts of an asset at regular intervals.
Perfect for long-term accumulation with minimal configuration.
"""

from decimal import Decimal
from typing import List

from pydantic import Field

from hummingbot.core.data_type.common import MarketDict, PriceType, TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, OrderExecutorConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class DCAStrategyConfig(ControllerConfigBase):
    """Configuration for DCA Strategy"""
    controller_name: str = "dca_strategy"
    controller_type: str = "dca"

    # Exchange and trading pair
    connector_name: str = Field(
        default="binance",
        description="Exchange connector (binance, kucoin, coinbase, etc)"
    )
    trading_pair: str = Field(
        default="BTC-USDT",
        description="Trading pair (e.g., BTC-USDT, ETH-USDT)"
    )

    # DCA Parameters
    order_amount_quote: Decimal = Field(
        default=Decimal("100"),
        description="Amount in quote asset to invest each interval (USDT)"
    )
    order_interval_seconds: int = Field(
        default=3600,
        description="Time between orders in seconds (3600 = 1 hour, 86400 = 1 day)"
    )

    # Optional
    candles_config: List[CandlesConfig] = Field(default=[])

    def update_markets(self, markets: MarketDict) -> MarketDict:
        return markets.add_or_update(self.connector_name, self.trading_pair)


class DCAStrategy(ControllerBase):
    """
    Dollar Cost Averaging Strategy

    Buys a fixed amount of an asset at regular intervals, regardless of price.
    This averages out the entry price over time and removes emotion from trading.
    """

    def __init__(self, config: DCAStrategyConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self.last_order_timestamp = 0

    async def update_processed_data(self):
        """Get current market price"""
        price = self.market_data_provider.get_price_by_type(
            self.config.connector_name,
            self.config.trading_pair,
            PriceType.MidPrice
        )

        # Count active orders
        active_executors = len([e for e in self.executors_info if e.is_active])

        self.processed_data = {
            "mid_price": price,
            "active_executors": active_executors,
            "time": self.market_data_provider.time()
        }

    def determine_executor_actions(self) -> list[ExecutorAction]:
        """
        Create buy orders at regular intervals.
        Only creates a new order if:
        1. No orders are currently active
        2. Enough time has passed since last order
        """
        time_since_last_order = (
            self.processed_data["time"] - self.last_order_timestamp
        )

        # Check if we should place a new order
        if (self.processed_data["active_executors"] == 0 and
            time_since_last_order >= self.config.order_interval_seconds):

            self.last_order_timestamp = self.processed_data["time"]

            # Calculate order amount in base asset
            amount = self.config.order_amount_quote / self.processed_data["mid_price"]

            # Create market buy order
            config = OrderExecutorConfig(
                timestamp=self.processed_data["time"],
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                side=TradeType.BUY,
                amount=amount,
                execution_strategy=ExecutionStrategy.MARKET,
                price=self.processed_data["mid_price"],
            )

            return [CreateExecutorAction(
                controller_id=self.config.id,
                executor_config=config
            )]

        return []
