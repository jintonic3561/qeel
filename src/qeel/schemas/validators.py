"""Polars DataFrameスキーマバリデータ

data-model.md 2.1-2.8を参照。
各スキーマクラスは必須列の型検証を行う。
"""

import polars as pl


class OHLCVSchema:
    """OHLCVのPolarsスキーマ定義

    必須列:
        datetime: pl.Datetime - データ利用可能時刻
        symbol: pl.String - 銘柄コード
        open: pl.Float64
        high: pl.Float64
        low: pl.Float64
        close: pl.Float64
        volume: pl.Int64

    Note:
        BaseDataSourceは任意のスキーマを返すことができ、OHLCVSchemaは
        OHLCV価格データに特化したデータソースの参照例として提供される。
    """

    REQUIRED_COLUMNS: dict[str, type[pl.DataType]] = {
        "datetime": pl.Datetime,
        "symbol": pl.String,
        "open": pl.Float64,
        "high": pl.Float64,
        "low": pl.Float64,
        "close": pl.Float64,
        "volume": pl.Int64,
    }

    @staticmethod
    def validate(df: pl.DataFrame) -> pl.DataFrame:
        """スキーマバリデーション(必須列のみ)

        Args:
            df: バリデーション対象のDataFrame

        Returns:
            バリデーション済みDataFrame

        Raises:
            ValueError: 必須列が不足または型が不正な場合
        """
        for col, dtype in OHLCVSchema.REQUIRED_COLUMNS.items():
            if col not in df.columns:
                raise ValueError(f"必須列が不足しています: {col}")
            if df[col].dtype != dtype:
                raise ValueError(f"列'{col}'の型が不正です。期待: {dtype}, 実際: {df[col].dtype}")
        return df


class SignalSchema:
    """SignalのPolarsスキーマ定義

    必須列:
        datetime: pl.Datetime - シグナル生成日時
        symbol: pl.String - 銘柄コード

    オプション列例(ユーザが任意に追加可能):
        signal: pl.Float64 - シグナル値(単一シグナルの場合)
        signal_momentum: pl.Float64 - モメンタムシグナル(複数シグナルの例)
        signal_value: pl.Float64 - バリューシグナル(複数シグナルの例)
        その他、ユーザが定義する任意のシグナル列
    """

    REQUIRED_COLUMNS: dict[str, type[pl.DataType]] = {
        "datetime": pl.Datetime,
        "symbol": pl.String,
    }

    @staticmethod
    def validate(df: pl.DataFrame) -> pl.DataFrame:
        """スキーマバリデーション(必須列のみ)

        Args:
            df: バリデーション対象のDataFrame

        Returns:
            バリデーション済みDataFrame

        Raises:
            ValueError: 必須列が不足または型が不正な場合
        """
        for col, dtype in SignalSchema.REQUIRED_COLUMNS.items():
            if col not in df.columns:
                raise ValueError(f"必須列が不足しています: {col}")
            if df[col].dtype != dtype:
                raise ValueError(f"列'{col}'の型が不正です。期待: {dtype}, 実際: {df[col].dtype}")
        return df


class PortfolioSchema:
    """PortfolioのPolarsスキーマ定義

    必須列:
        datetime: pl.Datetime - 構築日時
        symbol: pl.String - 銘柄コード

    オプション列(ユーザが任意に追加可能):
        signal_strength: pl.Float64 - シグナル強度
        priority: pl.Int64 - 優先度
        tags: pl.String - タグ(カスタムメタデータ)
    """

    REQUIRED_COLUMNS: dict[str, type[pl.DataType]] = {
        "datetime": pl.Datetime,
        "symbol": pl.String,
    }

    @staticmethod
    def validate(df: pl.DataFrame) -> pl.DataFrame:
        """スキーマバリデーション(必須列のみ)

        Args:
            df: バリデーション対象のDataFrame

        Returns:
            バリデーション済みDataFrame

        Raises:
            ValueError: 必須列が不足または型が不正な場合
        """
        for col, dtype in PortfolioSchema.REQUIRED_COLUMNS.items():
            if col not in df.columns:
                raise ValueError(f"必須列が不足しています: {col}")
            if df[col].dtype != dtype:
                raise ValueError(f"列'{col}'の型が不正です。期待: {dtype}, 実際: {df[col].dtype}")
        return df


class PositionSchema:
    """PositionのPolarsスキーマ定義

    必須列:
        symbol: pl.String - 銘柄コード
        quantity: pl.Float64 - 保有数量
        avg_price: pl.Float64 - 平均取得単価
    """

    REQUIRED_COLUMNS: dict[str, type[pl.DataType]] = {
        "symbol": pl.String,
        "quantity": pl.Float64,
        "avg_price": pl.Float64,
    }

    @staticmethod
    def validate(df: pl.DataFrame) -> pl.DataFrame:
        """スキーマバリデーション(必須列のみ)

        Args:
            df: バリデーション対象のDataFrame

        Returns:
            バリデーション済みDataFrame

        Raises:
            ValueError: 必須列が不足または型が不正な場合
        """
        for col, dtype in PositionSchema.REQUIRED_COLUMNS.items():
            if col not in df.columns:
                raise ValueError(f"必須列が不足しています: {col}")
            if df[col].dtype != dtype:
                raise ValueError(f"列'{col}'の型が不正です。期待: {dtype}, 実際: {df[col].dtype}")
        return df


class OrderSchema:
    """OrderのPolarsスキーマ定義

    必須列:
        symbol: pl.String - 銘柄コード
        side: pl.String - 売買区分("buy" / "sell")
        quantity: pl.Float64 - 数量
        price: pl.Float64 - 価格(nullの場合は成行)
        order_type: pl.String - 注文タイプ("market", "limit")
    """

    REQUIRED_COLUMNS: dict[str, type[pl.DataType]] = {
        "symbol": pl.String,
        "side": pl.String,
        "quantity": pl.Float64,
        "price": pl.Float64,
        "order_type": pl.String,
    }

    @staticmethod
    def validate(df: pl.DataFrame) -> pl.DataFrame:
        """スキーマバリデーション(必須列と値の妥当性)

        Args:
            df: バリデーション対象のDataFrame

        Returns:
            バリデーション済みDataFrame

        Raises:
            ValueError: 必須列が不足、型が不正、またはside/order_type値が不正な場合
        """
        for col, dtype in OrderSchema.REQUIRED_COLUMNS.items():
            if col not in df.columns:
                raise ValueError(f"必須列が不足しています: {col}")
            # price以外はnull不可
            if col != "price" and df[col].null_count() > 0:
                raise ValueError(f"列'{col}'にnullが含まれています")

        # sideのバリデーション
        allowed_sides = {"buy", "sell"}
        actual_sides = set(df["side"].unique().to_list())
        if not actual_sides.issubset(allowed_sides):
            raise ValueError(f"不正なside値: {actual_sides - allowed_sides}")

        # order_typeのバリデーション
        allowed_types = {"market", "limit"}
        actual_types = set(df["order_type"].unique().to_list())
        if not actual_types.issubset(allowed_types):
            raise ValueError(f"不正なorder_type値: {actual_types - allowed_types}")

        return df


class FillReportSchema:
    """FillReportのPolarsスキーマ定義

    必須列:
        order_id: pl.String - 注文ID
        symbol: pl.String - 銘柄コード
        side: pl.String - 売買区分
        filled_quantity: pl.Float64 - 約定数量
        filled_price: pl.Float64 - 約定価格
        commission: pl.Float64 - 手数料
        timestamp: pl.Datetime - 約定タイムスタンプ
    """

    REQUIRED_COLUMNS: dict[str, type[pl.DataType]] = {
        "order_id": pl.String,
        "symbol": pl.String,
        "side": pl.String,
        "filled_quantity": pl.Float64,
        "filled_price": pl.Float64,
        "commission": pl.Float64,
        "timestamp": pl.Datetime,
    }

    @staticmethod
    def validate(df: pl.DataFrame) -> pl.DataFrame:
        """スキーマバリデーション(必須列のみ)

        Args:
            df: バリデーション対象のDataFrame

        Returns:
            バリデーション済みDataFrame

        Raises:
            ValueError: 必須列が不足または型が不正な場合
        """
        for col, dtype in FillReportSchema.REQUIRED_COLUMNS.items():
            if col not in df.columns:
                raise ValueError(f"必須列が不足しています: {col}")
            if df[col].dtype != dtype:
                raise ValueError(f"列'{col}'の型が不正です。期待: {dtype}, 実際: {df[col].dtype}")
        return df


class MetricsSchema:
    """MetricsのPolarsスキーマ定義

    必須列:
        date: pl.Date - 日付
        daily_return: pl.Float64 - 日次リターン
        cumulative_return: pl.Float64 - 累積リターン
        volatility: pl.Float64 - ボラティリティ
        sharpe_ratio: pl.Float64 - シャープレシオ
        max_drawdown: pl.Float64 - 最大ドローダウン
    """

    REQUIRED_COLUMNS: dict[str, type[pl.DataType]] = {
        "date": pl.Date,
        "daily_return": pl.Float64,
        "cumulative_return": pl.Float64,
        "volatility": pl.Float64,
        "sharpe_ratio": pl.Float64,
        "max_drawdown": pl.Float64,
    }

    @staticmethod
    def validate(df: pl.DataFrame) -> pl.DataFrame:
        """スキーマバリデーション(必須列のみ)

        Args:
            df: バリデーション対象のDataFrame

        Returns:
            バリデーション済みDataFrame

        Raises:
            ValueError: 必須列が不足または型が不正な場合
        """
        for col, dtype in MetricsSchema.REQUIRED_COLUMNS.items():
            if col not in df.columns:
                raise ValueError(f"必須列が不足しています: {col}")
            if df[col].dtype != dtype:
                raise ValueError(f"列'{col}'の型が不正です。期待: {dtype}, 実際: {df[col].dtype}")
        return df
