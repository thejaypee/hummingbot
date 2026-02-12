"""
Grid Trading Strategy
Places orders at regular price intervals to profit from price oscillations.
Ideal for sideways/ranging markets.
"""

from decimal import Decimal
from typing import List

from pydantic import Field

from hummingbot.core.data_type.common import MarketDict, PriceType, TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class GridTradingStrategyConfig(ControllerConfigBase):
    """Configuration for Grid Trading Strategy"""
    controller_name: str = "grid_trading_strategy"
    controller_type: str = "grid"

    # Exchange and trading pair
    connector_name: str = Field(
        default="binance",
        description="Exchange connector"
    )
    trading_pair: str = Field(
        default="BTC-USDT",
        description="Trading pair"
    )

    # Grid Parameters
    lower_price: Decimal = Field(
        default=Decimal("40000"),
        description="Lower price boundary for grid"
    )
    upper_price: Decimal = Field(
        default=Decimal("50000"),
        description="Upper price boundary for grid"
    )
    grid_levels: int = Field(
        default=10,
        description="Number of grid levels between lower and upper price"
    )
    grid_amount_quote: Decimal = Field(
        default=Decimal("100"),
        description="Amount to invest at each grid level"
    )

    # Optional
    candles_config: List[CandlesConfig] = Field(default=[])

    def update_markets(self, markets: MarketDict) -> MarketDict:
        return markets.add_or_update(self.connector_name, self.trading_pair)


class GridTradingStrategy(ControllerBase):
    """
    Grid Trading Strategy

    Creates a grid of buy/sell orders between two price levels:
    - Buy at lower levels, sell at higher levels
    - Automatically profits from price oscillations
    - Perfect for ranging markets
    """

    def __init__(self, config: GridTradingStrategyConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self.grid_prices = self._calculate_grid_prices()
        self.placed_orders = set()

    def _calculate_grid_prices(self) -> List[Decimal]:
        """Calculate evenly spaced price grid"""
        price_range = self.config.upper_price - self.config.lower_price
        price_step = price_range / (self.config.grid_levels - 1)
        return [
            self.config.lower_price + (i * price_step)
            for i in range(self.config.grid_levels)
        ]

    async def update_processed_data(self):
        """Get current market price"""
        price = self.market_data_provider.get_price_by_type(
            self.config.connector_name,
            self.config.trading_pair,
            PriceType.MidPrice
        )

        self.processed_data = {
            "current_price": price,
            "time": self.market_data_provider.time()
        }

    def determine_executor_actions(self) -> list[ExecutorAction]:
        """
        Create grid orders:
        - BUY orders below current price
        - SELL orders above current price
        """
        actions = []
        current_price = self.processed_data["current_price"]

        for grid_price in self.grid_prices:
            # Skip if order already placed for this price
            if grid_price in self.placed_orders:
                continue

            # Determine order side based on price
            if grid_price < current_price:
                # Below current price - BUY
                side = TradeType.BUY
            elif grid_price > current_price:
                # Above current price - SELL
                side = TradeType.SELL
            else:
                # At current price - skip
                continue

            # Calculate amount
            amount = self.config.grid_amount_quote / grid_price

            # Create position executor
            config = PositionExecutorConfig(
                timestamp=self.processed_data["time"],
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                side=side,
                entry_price=grid_price,
                amount=amount,
            )

            actions.append(CreateExecutorAction(
                controller_id=self.config.id,
                executor_config=config
            ))

            # Mark as placed
            self.placed_orders.add(grid_price)

        return actions
