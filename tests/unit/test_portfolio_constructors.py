"""BasePortfolioConstructorとTopNPortfolioConstructorのテスト

TDDに従い、テストを先に作成する。
"""

from abc import ABC
from datetime import datetime

import polars as pl
import pytest

from qeel.config.params import PortfolioConstructorParams
from qeel.portfolio_constructors.base import BasePortfolioConstructor


class TestBasePortfolioConstructorValidation:
    """BasePortfolioConstructorのバリデーションテスト"""

    def test_validate_inputs_success(self) -> None:
        """正常なシグナルとポジションでバリデーションが成功する"""

        class ConcreteConstructor(BasePortfolioConstructor):
            def construct(
                self, signals: pl.DataFrame, current_positions: pl.DataFrame
            ) -> pl.DataFrame:
                self._validate_inputs(signals, current_positions)
                return pl.DataFrame(
                    {"datetime": [datetime(2024, 1, 1)], "symbol": ["AAPL"]}
                )

        params = PortfolioConstructorParams()
        constructor = ConcreteConstructor(params=params)

        signals = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)],
                "symbol": ["AAPL"],
                "signal": [1.5],
            }
        )
        positions = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "quantity": [100.0],
                "avg_price": [150.0],
            }
        )

        # バリデーションが成功することを確認
        result = constructor.construct(signals, positions)
        assert result.height == 1

    def test_validate_inputs_invalid_signal_schema(self) -> None:
        """シグナルスキーマが不正な場合にValueErrorが発生する"""

        class ConcreteConstructor(BasePortfolioConstructor):
            def construct(
                self, signals: pl.DataFrame, current_positions: pl.DataFrame
            ) -> pl.DataFrame:
                self._validate_inputs(signals, current_positions)
                return pl.DataFrame()

        params = PortfolioConstructorParams()
        constructor = ConcreteConstructor(params=params)

        # datetime列が欠けている
        signals = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "signal": [1.5],
            }
        )
        positions = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "quantity": [100.0],
                "avg_price": [150.0],
            }
        )

        with pytest.raises(ValueError, match="必須列が不足しています"):
            constructor.construct(signals, positions)

    def test_validate_inputs_invalid_position_schema(self) -> None:
        """ポジションスキーマが不正な場合にValueErrorが発生する"""

        class ConcreteConstructor(BasePortfolioConstructor):
            def construct(
                self, signals: pl.DataFrame, current_positions: pl.DataFrame
            ) -> pl.DataFrame:
                self._validate_inputs(signals, current_positions)
                return pl.DataFrame()

        params = PortfolioConstructorParams()
        constructor = ConcreteConstructor(params=params)

        signals = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)],
                "symbol": ["AAPL"],
                "signal": [1.5],
            }
        )
        # quantity列が欠けている
        positions = pl.DataFrame(
            {
                "symbol": ["AAPL"],
                "avg_price": [150.0],
            }
        )

        with pytest.raises(ValueError, match="必須列が不足しています"):
            constructor.construct(signals, positions)

    def test_validate_output_success(self) -> None:
        """正常なポートフォリオDataFrameで出力バリデーションが成功する"""

        class ConcreteConstructor(BasePortfolioConstructor):
            def construct(
                self, signals: pl.DataFrame, current_positions: pl.DataFrame
            ) -> pl.DataFrame:
                portfolio = pl.DataFrame(
                    {
                        "datetime": [datetime(2024, 1, 1)],
                        "symbol": ["AAPL"],
                        "signal_strength": [1.5],
                    }
                )
                return self._validate_output(portfolio)

        params = PortfolioConstructorParams()
        constructor = ConcreteConstructor(params=params)

        signals = pl.DataFrame(
            {"datetime": [datetime(2024, 1, 1)], "symbol": ["AAPL"]}
        )
        positions = pl.DataFrame(
            {"symbol": ["AAPL"], "quantity": [100.0], "avg_price": [150.0]}
        )

        result = constructor.construct(signals, positions)
        assert "datetime" in result.columns
        assert "symbol" in result.columns

    def test_validate_output_invalid_schema(self) -> None:
        """出力スキーマが不正な場合にValueErrorが発生する"""

        class ConcreteConstructor(BasePortfolioConstructor):
            def construct(
                self, signals: pl.DataFrame, current_positions: pl.DataFrame
            ) -> pl.DataFrame:
                # datetime列が欠けているポートフォリオ
                portfolio = pl.DataFrame(
                    {
                        "symbol": ["AAPL"],
                        "signal_strength": [1.5],
                    }
                )
                return self._validate_output(portfolio)

        params = PortfolioConstructorParams()
        constructor = ConcreteConstructor(params=params)

        signals = pl.DataFrame(
            {"datetime": [datetime(2024, 1, 1)], "symbol": ["AAPL"]}
        )
        positions = pl.DataFrame(
            {"symbol": ["AAPL"], "quantity": [100.0], "avg_price": [150.0]}
        )

        with pytest.raises(ValueError, match="必須列が不足しています"):
            constructor.construct(signals, positions)


class TestBasePortfolioConstructorABC:
    """BasePortfolioConstructorのABC継承テスト"""

    def test_is_abstract_class(self) -> None:
        """BasePortfolioConstructorが抽象基底クラスであることを確認"""
        assert issubclass(BasePortfolioConstructor, ABC)

    def test_cannot_instantiate_directly(self) -> None:
        """BasePortfolioConstructorは直接インスタンス化できない"""
        with pytest.raises(TypeError, match="abstract"):
            BasePortfolioConstructor(params=PortfolioConstructorParams())  # type: ignore

    def test_must_implement_construct(self) -> None:
        """constructメソッドの実装が必要"""

        # 抽象メソッドを実装しないサブクラス
        class IncompleteConstructor(BasePortfolioConstructor):
            pass

        with pytest.raises(TypeError, match="abstract"):
            IncompleteConstructor(params=PortfolioConstructorParams())  # type: ignore

    def test_subclass_with_construct_works(self) -> None:
        """constructメソッドを実装したサブクラスはインスタンス化できる"""

        class CompleteConstructor(BasePortfolioConstructor):
            def construct(
                self, signals: pl.DataFrame, current_positions: pl.DataFrame
            ) -> pl.DataFrame:
                return pl.DataFrame(
                    {"datetime": [datetime(2024, 1, 1)], "symbol": ["TEST"]}
                )

        params = PortfolioConstructorParams()
        constructor = CompleteConstructor(params=params)
        assert constructor.params == params


class TestTopNPortfolioConstructor:
    """TopNPortfolioConstructorのテスト"""

    def test_top_n_default_params(self) -> None:
        """デフォルトパラメータで上位10銘柄が選定される"""
        from qeel.portfolio_constructors.top_n import (
            TopNConstructorParams,
            TopNPortfolioConstructor,
        )

        params = TopNConstructorParams()
        assert params.top_n == 10
        assert params.ascending is False

    def test_top_n_custom_params(self) -> None:
        """カスタムパラメータで指定した銘柄数が選定される"""
        from qeel.portfolio_constructors.top_n import (
            TopNConstructorParams,
            TopNPortfolioConstructor,
        )

        params = TopNConstructorParams(top_n=5, ascending=True)
        assert params.top_n == 5
        assert params.ascending is True

    def test_top_n_selects_top_symbols_descending(self) -> None:
        """降順モードでシグナル上位N銘柄が選定される"""
        from qeel.portfolio_constructors.top_n import (
            TopNConstructorParams,
            TopNPortfolioConstructor,
        )

        params = TopNConstructorParams(top_n=3)
        constructor = TopNPortfolioConstructor(params=params)

        signals = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)] * 5,
                "symbol": ["A", "B", "C", "D", "E"],
                "signal": [1.0, 3.0, 2.0, 5.0, 4.0],
            }
        )
        positions = pl.DataFrame(
            {"symbol": [], "quantity": [], "avg_price": []},
            schema={"symbol": pl.String, "quantity": pl.Float64, "avg_price": pl.Float64},
        )

        result = constructor.construct(signals, positions)

        assert result.height == 3
        assert result["symbol"].to_list() == ["D", "E", "B"]  # 5.0, 4.0, 3.0

    def test_top_n_selects_top_symbols_ascending(self) -> None:
        """昇順モードでシグナル下位N銘柄が選定される"""
        from qeel.portfolio_constructors.top_n import (
            TopNConstructorParams,
            TopNPortfolioConstructor,
        )

        params = TopNConstructorParams(top_n=3, ascending=True)
        constructor = TopNPortfolioConstructor(params=params)

        signals = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)] * 5,
                "symbol": ["A", "B", "C", "D", "E"],
                "signal": [1.0, 3.0, 2.0, 5.0, 4.0],
            }
        )
        positions = pl.DataFrame(
            {"symbol": [], "quantity": [], "avg_price": []},
            schema={"symbol": pl.String, "quantity": pl.Float64, "avg_price": pl.Float64},
        )

        result = constructor.construct(signals, positions)

        assert result.height == 3
        assert result["symbol"].to_list() == ["A", "C", "B"]  # 1.0, 2.0, 3.0

    def test_signal_strength_metadata_included(self) -> None:
        """signal_strengthがメタデータとして含まれる"""
        from qeel.portfolio_constructors.top_n import (
            TopNConstructorParams,
            TopNPortfolioConstructor,
        )

        params = TopNConstructorParams(top_n=2)
        constructor = TopNPortfolioConstructor(params=params)

        signals = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)] * 3,
                "symbol": ["A", "B", "C"],
                "signal": [1.0, 3.0, 2.0],
            }
        )
        positions = pl.DataFrame(
            {"symbol": [], "quantity": [], "avg_price": []},
            schema={"symbol": pl.String, "quantity": pl.Float64, "avg_price": pl.Float64},
        )

        result = constructor.construct(signals, positions)

        assert "signal_strength" in result.columns
        assert result["signal_strength"].to_list() == [3.0, 2.0]

    def test_empty_signals_returns_empty_dataframe(self) -> None:
        """空のシグナルDataFrameに対して空のDataFrameを返す"""
        from qeel.portfolio_constructors.top_n import (
            TopNConstructorParams,
            TopNPortfolioConstructor,
        )

        params = TopNConstructorParams(top_n=5)
        constructor = TopNPortfolioConstructor(params=params)

        signals = pl.DataFrame(
            {"datetime": [], "symbol": [], "signal": []},
            schema={"datetime": pl.Datetime, "symbol": pl.String, "signal": pl.Float64},
        )
        positions = pl.DataFrame(
            {"symbol": [], "quantity": [], "avg_price": []},
            schema={"symbol": pl.String, "quantity": pl.Float64, "avg_price": pl.Float64},
        )

        result = constructor.construct(signals, positions)

        assert result.height == 0
        assert "datetime" in result.columns
        assert "symbol" in result.columns

    def test_fewer_signals_than_top_n(self) -> None:
        """シグナル数がtop_n未満の場合、すべての銘柄を返す"""
        from qeel.portfolio_constructors.top_n import (
            TopNConstructorParams,
            TopNPortfolioConstructor,
        )

        params = TopNConstructorParams(top_n=10)
        constructor = TopNPortfolioConstructor(params=params)

        signals = pl.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1)] * 3,
                "symbol": ["A", "B", "C"],
                "signal": [1.0, 2.0, 3.0],
            }
        )
        positions = pl.DataFrame(
            {"symbol": [], "quantity": [], "avg_price": []},
            schema={"symbol": pl.String, "quantity": pl.Float64, "avg_price": pl.Float64},
        )

        result = constructor.construct(signals, positions)

        assert result.height == 3
        assert result["symbol"].to_list() == ["C", "B", "A"]  # 3.0, 2.0, 1.0

    def test_top_n_param_validation(self) -> None:
        """top_nパラメータは正の整数でなければならない"""
        from pydantic import ValidationError

        from qeel.portfolio_constructors.top_n import TopNConstructorParams

        with pytest.raises(ValidationError):
            TopNConstructorParams(top_n=0)

        with pytest.raises(ValidationError):
            TopNConstructorParams(top_n=-1)
