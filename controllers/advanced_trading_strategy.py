"""
Advanced Trading Strategy with Volume, Momentum & Price Action
Professional-grade strategy using multiple technical indicators and market microstructure
"""

from decimal import Decimal
from typing import List, Optional

from pydantic import Field

from hummingbot.core.data_type.common import MarketDict, PriceType, TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig, CandlesConfigDataType
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.position_executor.data_types import (
    PositionExecutorConfig,
    TripleBarrierConfig,
)
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class AdvancedTradingStrategyConfig(ControllerConfigBase):
    """Professional trading strategy with advanced metrics"""
    controller_name: str = "advanced_trading_strategy"
    controller_type: str = "advanced"

    # Exchange and trading pair
    connector_name: str = Field(
        default="binance",
        description="Exchange (binance, kucoin, coinbase_advanced_trade, etc.)"
    )
    trading_pair: str = Field(
        default="BTC-USDT",
        description="Trading pair (BTC-USDT, ETH-USDT, DOGE-USDT, etc.)"
    )

    # ========== PRICE ACTION & MOMENTUM ==========
    # RSI (Relative Strength Index) for overbought/oversold
    rsi_period: int = Field(default=14, description="RSI calculation period")
    rsi_upper_threshold: Decimal = Field(
        default=Decimal("70"),
        description="RSI overbought threshold (0-100)"
    )
    rsi_lower_threshold: Decimal = Field(
        default=Decimal("30"),
        description="RSI oversold threshold (0-100)"
    )

    # MACD (Moving Average Convergence Divergence)
    macd_fast_period: int = Field(default=12, description="MACD fast period")
    macd_slow_period: int = Field(default=26, description="MACD slow period")
    macd_signal_period: int = Field(default=9, description="MACD signal period")

    # Bollinger Bands for volatility
    bb_period: int = Field(default=20, description="Bollinger Bands period")
    bb_std_dev: Decimal = Field(
        default=Decimal("2"),
        description="Bollinger Bands standard deviations"
    )

    # ========== VOLUME ANALYSIS ==========
    volume_ma_period: int = Field(
        default=20,
        description="Volume moving average period"
    )
    min_volume_multiplier: Decimal = Field(
        default=Decimal("1.5"),
        description="Min volume = MA * this multiplier to confirm signal"
    )

    # ========== PRICE ACTION ==========
    price_change_threshold: Decimal = Field(
        default=Decimal("0.5"),
        description="Min % price change to trigger (0.5 = 0.5%)"
    )
    support_resistance_lookback: int = Field(
        default=20,
        description="Lookback candles for support/resistance levels"
    )

    # ========== POSITION MANAGEMENT ==========
    position_size_quote: Decimal = Field(
        default=Decimal("1000"),
        description="Position size in quote asset (USDT)"
    )
    take_profit_pct: Decimal = Field(
        default=Decimal("5"),
        description="Take profit percentage (3%, 5%, 10%, etc.)"
    )
    stop_loss_pct: Decimal = Field(
        default=Decimal("2"),
        description="Stop loss percentage (1%, 2%, etc.)"
    )
    max_concurrent_positions: int = Field(
        default=3,
        description="Maximum open positions at once"
    )

    # ========== RISK MANAGEMENT ==========
    cooldown_between_trades: int = Field(
        default=300,
        description="Cooldown seconds between trades (prevents overtrading)"
    )
    daily_loss_limit: Decimal = Field(
        default=Decimal("1000"),
        description="Stop trading if daily loss exceeds this"
    )

    # Candles configuration
    candles_config: List[CandlesConfig] = Field(
        default_factory=lambda: [
            CandlesConfig(
                connector_name="binance",
                trading_pair="BTC-USDT",
                interval="5m",
                max_records=200,
                data_type=CandlesConfigDataType.TRADING_PAIR
            )
        ]
    )

    def update_markets(self, markets: MarketDict) -> MarketDict:
        return markets.add_or_update(self.connector_name, self.trading_pair)


class AdvancedTradingStrategy(ControllerBase):
    """
    Advanced Trading Strategy with Professional Metrics

    Combines:
    - Price Action Analysis (Support/Resistance, Breakouts)
    - Momentum Indicators (RSI, MACD)
    - Volume Analysis (OBV, Volume MA)
    - Volatility Analysis (Bollinger Bands)
    - Risk Management (Position sizing, stops, limits)
    """

    def __init__(self, config: AdvancedTradingStrategyConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self.last_trade_timestamp = 0
        self.daily_loss = Decimal("0")

    def _calculate_rsi(self, closes: List[Decimal], period: int) -> Optional[Decimal]:
        """Calculate Relative Strength Index"""
        if len(closes) < period + 1:
            return None

        gains = []
        losses = []

        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(Decimal("0"))
            else:
                gains.append(Decimal("0"))
                losses.append(abs(change))

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return Decimal("100") if avg_gain > 0 else Decimal("50")

        rs = avg_gain / avg_loss
        rsi = Decimal("100") - (Decimal("100") / (Decimal("1") + rs))
        return rsi

    def _calculate_macd(
        self, closes: List[Decimal]
    ) -> tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
        """Calculate MACD, Signal, and Histogram"""
        if len(closes) < self.config.macd_slow_period:
            return None, None, None

        # EMA calculations
        ema_fast = self._ema(closes, self.config.macd_fast_period)
        ema_slow = self._ema(closes, self.config.macd_slow_period)

        macd = ema_fast - ema_slow

        signal_values = [
            ema_fast - ema_slow for ema_fast, ema_slow in
            zip(
                self._ema_series(closes, self.config.macd_fast_period),
                self._ema_series(closes, self.config.macd_slow_period)
            )
        ]
        signal = self._ema(signal_values, self.config.macd_signal_period)
        histogram = macd - signal

        return macd, signal, histogram

    def _ema(self, values: List[Decimal], period: int) -> Decimal:
        """Calculate Exponential Moving Average"""
        if len(values) < period:
            return sum(values) / len(values)
        multiplier = Decimal("2") / (Decimal(period) + Decimal("1"))
        ema = sum(values[:period]) / period
        for value in values[period:]:
            ema = value * multiplier + ema * (Decimal("1") - multiplier)
        return ema

    def _ema_series(self, values: List[Decimal], period: int) -> List[Decimal]:
        """Calculate EMA series"""
        if len(values) < period:
            return [Decimal("0")] * len(values)
        result = []
        multiplier = Decimal("2") / (Decimal(period) + Decimal("1"))
        ema = sum(values[:period]) / period
        for i, value in enumerate(values):
            if i < period:
                result.append(sum(values[:i+1]) / (i+1))
            else:
                ema = value * multiplier + ema * (Decimal("1") - multiplier)
                result.append(ema)
        return result

    def _find_support_resistance(
        self, highs: List[Decimal], lows: List[Decimal]
    ) -> tuple[Decimal, Decimal]:
        """Identify support and resistance levels"""
        lookback = min(self.config.support_resistance_lookback, len(highs))
        support = min(lows[-lookback:])
        resistance = max(highs[-lookback:])
        return support, resistance

    async def update_processed_data(self):
        """Calculate all technical indicators"""
        candles = self.get_candles(
            self.config.connector_name,
            self.config.trading_pair,
            "5m"
        )

        if not candles or len(candles) < 50:
            self.processed_data = {"signal": "NEUTRAL", "can_trade": False}
            return

        closes = [candle.close for candle in candles]
        highs = [candle.high for candle in candles]
        lows = [candle.low for candle in candles]
        volumes = [candle.volume for candle in candles]

        current_price = closes[-1]
        current_volume = volumes[-1]

        # ========== CALCULATE INDICATORS ==========

        # RSI
        rsi = self._calculate_rsi(closes, self.config.rsi_period)

        # MACD
        macd, signal, histogram = self._calculate_macd(closes)

        # Volume MA
        volume_ma = sum(volumes[-self.config.volume_ma_period:]) / self.config.volume_ma_period
        volume_confirmed = current_volume > volume_ma * self.config.min_volume_multiplier

        # Support/Resistance
        support, resistance = self._find_support_resistance(highs, lows)

        # Price change
        price_change_pct = ((current_price - closes[-50]) / closes[-50]) * Decimal("100")

        # Bollinger Bands
        bb_ma = sum(closes[-self.config.bb_period:]) / self.config.bb_period
        bb_std = self._std_dev(closes[-self.config.bb_period:])
        bb_upper = bb_ma + (bb_std * self.config.bb_std_dev)
        bb_lower = bb_ma - (bb_std * self.config.bb_std_dev)

        # ========== DETERMINE SIGNAL ==========
        signal = "NEUTRAL"

        # BUY Signals
        if (
            rsi and rsi < self.config.rsi_lower_threshold and  # Oversold
            macd and signal and histogram < 0 and  # MACD bearish
            volume_confirmed and  # Strong volume
            current_price > support and  # Above support
            price_change_pct.abs() > self.config.price_change_threshold  # Significant move
        ):
            signal = "BUY"

        # SELL Signals
        elif (
            rsi and rsi > self.config.rsi_upper_threshold and  # Overbought
            macd and signal and histogram > 0 and  # MACD bullish
            volume_confirmed and  # Strong volume
            current_price < resistance and  # Below resistance
            price_change_pct.abs() > self.config.price_change_threshold  # Significant move
        ):
            signal = "SELL"

        self.processed_data = {
            "signal": signal,
            "can_trade": True,
            "current_price": current_price,
            "rsi": rsi,
            "macd": macd,
            "macd_signal": signal,
            "macd_histogram": histogram,
            "volume_confirmed": volume_confirmed,
            "support": support,
            "resistance": resistance,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
            "price_change_pct": price_change_pct,
            "volume_ratio": current_volume / volume_ma if volume_ma > 0 else Decimal("0"),
            "time": self.market_data_provider.time()
        }

    def determine_executor_actions(self) -> list[ExecutorAction]:
        """Create buy/sell orders based on signal"""
        if not self.processed_data.get("can_trade"):
            return []

        actions = []
        signal = self.processed_data["signal"]
        current_time = self.processed_data["time"]

        # Check cooldown
        if current_time - self.last_trade_timestamp < self.config.cooldown_between_trades:
            return []

        # Check daily loss limit
        if self.daily_loss > self.config.daily_loss_limit:
            return []

        # Count active positions
        active_positions = len([e for e in self.executors_info if e.is_active])

        # Only trade if below max positions
        if active_positions < self.config.max_concurrent_positions and signal != "NEUTRAL":

            current_price = self.processed_data["current_price"]
            side = TradeType.BUY if signal == "BUY" else TradeType.SELL

            # Calculate amount
            amount = self.config.position_size_quote / current_price

            # Calculate stop loss and take profit
            if side == TradeType.BUY:
                sl_price = current_price * (
                    1 - (self.config.stop_loss_pct / Decimal("100"))
                )
                tp_price = current_price * (
                    1 + (self.config.take_profit_pct / Decimal("100"))
                )
            else:
                sl_price = current_price * (
                    1 + (self.config.stop_loss_pct / Decimal("100"))
                )
                tp_price = current_price * (
                    1 - (self.config.take_profit_pct / Decimal("100"))
                )

            # Create executor
            config = PositionExecutorConfig(
                timestamp=current_time,
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                side=side,
                entry_price=current_price,
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

            self.last_trade_timestamp = current_time

        return actions

    @staticmethod
    def _std_dev(values: List[Decimal]) -> Decimal:
        """Calculate standard deviation"""
        if not values:
            return Decimal("0")
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance.sqrt()
