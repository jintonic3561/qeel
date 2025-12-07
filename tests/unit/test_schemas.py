"""DataFrame Schema Validatorsのユニットテスト

TDD: RED → GREEN → REFACTOR
data-model.md 2.1-2.8を参照
"""

from datetime import date, datetime

import polars as pl
import pytest


# OHLCVSchema tests
def test_ohlcv_schema_valid() -> None:
    """正常なDataFrameでバリデーションパス"""
    from qeel.schemas.validators import OHLCVSchema

    df = pl.DataFrame(
        {
            "datetime": [datetime(2023, 1, 1)],
            "symbol": ["AAPL"],
            "open": [150.0],
            "high": [152.0],
            "low": [149.0],
            "close": [151.0],
            "volume": [1000000],
        }
    )
    result = OHLCVSchema.validate(df)
    assert result.equals(df)


def test_ohlcv_schema_missing_column() -> None:
    """必須列欠損でValueError"""
    from qeel.schemas.validators import OHLCVSchema

    df = pl.DataFrame(
        {
            "datetime": [datetime(2023, 1, 1)],
            "symbol": ["AAPL"],
            # "open"が欠損
            "high": [152.0],
            "low": [149.0],
            "close": [151.0],
            "volume": [1000000],
        }
    )
    with pytest.raises(ValueError, match="必須列が不足しています"):
        OHLCVSchema.validate(df)


def test_ohlcv_schema_wrong_dtype() -> None:
    """型不一致でValueError"""
    from qeel.schemas.validators import OHLCVSchema

    df = pl.DataFrame(
        {
            "datetime": [datetime(2023, 1, 1)],
            "symbol": ["AAPL"],
            "open": ["invalid"],  # 型が不正(strではなくfloat64が期待される)
            "high": [152.0],
            "low": [149.0],
            "close": [151.0],
            "volume": [1000000],
        }
    )
    with pytest.raises(ValueError, match="型が不正です"):
        OHLCVSchema.validate(df)


# SignalSchema tests
def test_signal_schema_valid() -> None:
    """正常なDataFrameでバリデーションパス"""
    from qeel.schemas.validators import SignalSchema

    df = pl.DataFrame(
        {
            "datetime": [datetime(2023, 1, 1)],
            "symbol": ["AAPL"],
            "signal": [0.5],
        }
    )
    result = SignalSchema.validate(df)
    assert result.equals(df)


def test_signal_schema_allows_extra_columns() -> None:
    """追加列は許容"""
    from qeel.schemas.validators import SignalSchema

    df = pl.DataFrame(
        {
            "datetime": [datetime(2023, 1, 1)],
            "symbol": ["AAPL"],
            "signal_momentum": [0.3],
            "signal_value": [0.7],
        }
    )
    result = SignalSchema.validate(df)
    assert result.equals(df)


# PortfolioSchema tests
def test_portfolio_schema_valid() -> None:
    """正常なDataFrameでバリデーションパス"""
    from qeel.schemas.validators import PortfolioSchema

    df = pl.DataFrame(
        {
            "datetime": [datetime(2023, 1, 1)],
            "symbol": ["AAPL"],
            "signal_strength": [0.8],
        }
    )
    result = PortfolioSchema.validate(df)
    assert result.equals(df)


# PositionSchema tests
def test_position_schema_valid() -> None:
    """正常なDataFrameでバリデーションパス"""
    from qeel.schemas.validators import PositionSchema

    df = pl.DataFrame(
        {
            "symbol": ["AAPL"],
            "quantity": [100.0],
            "avg_price": [150.0],
        }
    )
    result = PositionSchema.validate(df)
    assert result.equals(df)


# OrderSchema tests
def test_order_schema_valid() -> None:
    """正常なDataFrameでバリデーションパス"""
    from qeel.schemas.validators import OrderSchema

    df = pl.DataFrame(
        {
            "symbol": ["AAPL"],
            "side": ["buy"],
            "quantity": [100.0],
            "price": [150.0],
            "order_type": ["market"],
        }
    )
    result = OrderSchema.validate(df)
    assert result.equals(df)


def test_order_schema_invalid_side() -> None:
    """不正なside値でValueError"""
    from qeel.schemas.validators import OrderSchema

    df = pl.DataFrame(
        {
            "symbol": ["AAPL"],
            "side": ["invalid_side"],
            "quantity": [100.0],
            "price": [150.0],
            "order_type": ["market"],
        }
    )
    with pytest.raises(ValueError, match="不正なside値"):
        OrderSchema.validate(df)


def test_order_schema_invalid_order_type() -> None:
    """不正なorder_type値でValueError"""
    from qeel.schemas.validators import OrderSchema

    df = pl.DataFrame(
        {
            "symbol": ["AAPL"],
            "side": ["buy"],
            "quantity": [100.0],
            "price": [150.0],
            "order_type": ["invalid_type"],
        }
    )
    with pytest.raises(ValueError, match="不正なorder_type値"):
        OrderSchema.validate(df)


# FillReportSchema tests
def test_fill_report_schema_valid() -> None:
    """正常なDataFrameでバリデーションパス"""
    from qeel.schemas.validators import FillReportSchema

    df = pl.DataFrame(
        {
            "order_id": ["ORD123"],
            "symbol": ["AAPL"],
            "side": ["buy"],
            "filled_quantity": [100.0],
            "filled_price": [150.5],
            "commission": [1.5],
            "timestamp": [datetime(2023, 1, 1, 9, 30)],
        }
    )
    result = FillReportSchema.validate(df)
    assert result.equals(df)


# MetricsSchema tests
def test_metrics_schema_valid() -> None:
    """正常なDataFrameでバリデーションパス"""
    from qeel.schemas.validators import MetricsSchema

    df = pl.DataFrame(
        {
            "date": [date(2023, 1, 1)],
            "daily_return": [0.01],
            "cumulative_return": [0.01],
            "volatility": [0.02],
            "sharpe_ratio": [0.5],
            "max_drawdown": [-0.05],
        }
    )
    result = MetricsSchema.validate(df)
    assert result.equals(df)
