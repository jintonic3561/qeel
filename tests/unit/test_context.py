"""Contextモデルのテスト"""

from datetime import datetime

import polars as pl
import pytest

from qeel.models.context import Context


class TestContext:
    """Contextモデルのテスト"""

    def test_context_requires_current_datetime(self) -> None:
        """current_datetimeは必須フィールド"""
        with pytest.raises(Exception):  # ValidationError
            Context()  # type: ignore[call-arg]

    def test_context_optional_fields_default_none(self) -> None:
        """オプショナルフィールドはデフォルトでNone"""
        ctx = Context(current_datetime=datetime(2025, 1, 15, 9, 0, 0))

        assert ctx.current_datetime == datetime(2025, 1, 15, 9, 0, 0)
        assert ctx.signals is None
        assert ctx.portfolio_plan is None
        assert ctx.entry_orders is None
        assert ctx.exit_orders is None
        assert ctx.current_positions is None

    def test_context_accepts_polars_dataframe(self) -> None:
        """Polars DataFrameを保持可能"""
        signals_df = pl.DataFrame(
            {
                "datetime": [datetime(2025, 1, 15)],
                "symbol": ["AAPL"],
                "signal": [0.5],
            }
        )

        ctx = Context(
            current_datetime=datetime(2025, 1, 15, 9, 0, 0),
            signals=signals_df,
        )

        assert ctx.signals is not None
        assert isinstance(ctx.signals, pl.DataFrame)
        assert ctx.signals.shape == (1, 3)

    def test_context_serialization_arbitrary_types(self) -> None:
        """arbitrary_types_allowed設定が有効であることを確認"""
        # Polars DataFrameを含むContextが作成できることで確認
        signals_df = pl.DataFrame(
            {
                "datetime": [datetime(2025, 1, 15)],
                "symbol": ["AAPL"],
            }
        )

        ctx = Context(
            current_datetime=datetime(2025, 1, 15, 9, 0, 0),
            signals=signals_df,
        )

        # 問題なくインスタンスが作成できればOK
        assert ctx.signals is not None

    def test_context_model_dump_excludes_dataframes(self) -> None:
        """model_dump()はDataFrameをシリアライズ不可（arbitrary_types_allowedの制限確認）"""
        signals_df = pl.DataFrame(
            {
                "datetime": [datetime(2025, 1, 15)],
                "symbol": ["AAPL"],
            }
        )

        ctx = Context(
            current_datetime=datetime(2025, 1, 15, 9, 0, 0),
            signals=signals_df,
        )

        # model_dump()はDataFrameをそのまま返す（シリアライズはされない）
        dumped = ctx.model_dump()

        # DataFrameはそのまま含まれる
        assert "signals" in dumped
        assert isinstance(dumped["signals"], pl.DataFrame)
