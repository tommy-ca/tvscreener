import pandas as pd
import pytest
from tvscreener_ext.screeners.filter_utils import (
    apply_ma_score_filter,
    apply_volume_filter,
)
from tvscreener_ext.screeners.filters import RocFilter
from tvscreener_ext.screeners.forex_opportunity import (
    ForexOpportunityScreener,
    ForexScreenerConfig,
)


class TestVolumeFilter:
    def test_volume_filter_removes_below_threshold(self):
        mock_df = pd.DataFrame(
            {
                "Name": ["EURUSD", "GBPUSD", "USDJPY"],
                "Symbol": ["EURUSD:OANDA", "GBPUSD:OANDA", "USDJPY:OANDA"],
                "Average Volume (10 day Calc)": [500000, 1500000, 2000000],
            }
        )

        result = apply_volume_filter(mock_df, min_volume=1000000)

        assert len(result) == 2
        assert "EURUSD" not in result["Name"].values

    def test_volume_filter_none_returns_original(self):
        mock_df = pd.DataFrame(
            {
                "Name": ["EURUSD"],
                "Symbol": ["EURUSD:OANDA"],
                "Average Volume (10 day Calc)": [500000],
            }
        )

        result = apply_volume_filter(mock_df, min_volume=None)

        assert len(result) == 1

    def test_volume_filter_empty_dataframe(self):
        mock_df = pd.DataFrame()
        result = apply_volume_filter(mock_df, min_volume=1000000)
        assert len(result) == 0


class TestScoreFilter:
    def test_rating_filter_keeps_above_threshold(self):
        mock_df = pd.DataFrame(
            {
                "Name": ["EURUSD", "GBPUSD"],
                "Symbol": ["EURUSD:OANDA", "GBPUSD:OANDA"],
                "Recommend Ma|15": [0.8, 0.2],
            }
        )

        result = apply_ma_score_filter(mock_df, min_ma_score=0.5)

        assert len(result) == 1
        assert result.iloc[0]["Name"] == "EURUSD"

    def test_rating_filter_empty_dataframe(self):
        mock_df = pd.DataFrame()
        result = apply_ma_score_filter(mock_df, min_ma_score=0.5)
        assert len(result) == 0


class TestRocFilter:
    def test_roc_filter_min_roc(self):
        screener = ForexOpportunityScreener(
            pairs=["EURUSD"],
            timeframes=["15"],
            config=ForexScreenerConfig(roc_filter=RocFilter(min_roc=1.0)),
        )

        mock_df = pd.DataFrame(
            {
                "Name": ["EURUSD", "GBPUSD"],
                "Symbol": ["EURUSD:OANDA", "GBPUSD:OANDA"],
                "Roc|15": [1.5, 0.5],
            }
        )

        assert screener.config.roc_filter is not None
        result = screener._apply_roc_filter(mock_df, screener.config.roc_filter)

        assert len(result) == 1
        assert result.iloc[0]["Name"] == "EURUSD"

    def test_roc_filter_max_roc(self):
        screener = ForexOpportunityScreener(
            pairs=["EURUSD"],
            timeframes=["15"],
            config=ForexScreenerConfig(roc_filter=RocFilter(max_roc=1.0)),
        )

        mock_df = pd.DataFrame(
            {
                "Name": ["EURUSD", "GBPUSD"],
                "Symbol": ["EURUSD:OANDA", "GBPUSD:OANDA"],
                "Roc|15": [1.5, 0.5],
            }
        )

        assert screener.config.roc_filter is not None
        result = screener._apply_roc_filter(mock_df, screener.config.roc_filter)

        assert len(result) == 1
        assert result.iloc[0]["Name"] == "GBPUSD"

    def test_roc_filter_empty_dataframe(self):
        screener = ForexOpportunityScreener(
            pairs=["EURUSD"],
            timeframes=["15"],
            config=ForexScreenerConfig(roc_filter=RocFilter(min_roc=1.0)),
        )

        mock_df = pd.DataFrame()
        assert screener.config.roc_filter is not None
        result = screener._apply_roc_filter(mock_df, screener.config.roc_filter)
        assert len(result) == 0

    def test_roc_filter_multi_timeframe(self):
        screener = ForexOpportunityScreener(
            pairs=["EURUSD"],
            timeframes=["15", "60"],
            config=ForexScreenerConfig(roc_filter=RocFilter(min_roc=1.0)),
        )

        mock_df = pd.DataFrame(
            {
                "Name": ["EURUSD", "GBPUSD", "USDJPY"],
                "Roc|15": [1.5, 1.5, 0.5],
                "Roc|60": [1.5, 0.5, 1.5],
            }
        )

        assert screener.config.roc_filter is not None
        result = screener._apply_roc_filter(mock_df, screener.config.roc_filter)

        assert len(result) == 1
        assert result.iloc[0]["Name"] == "EURUSD"


class TestExportMethod:
    def test_export_csv_format(self, tmp_path):
        screener = ForexOpportunityScreener(pairs=["EURUSD"], timeframes=["15"])

        mock_df = pd.DataFrame(
            {
                "Name": ["EURUSD"],
                "Price": [1.0850],
                "ENSEMBLE_SCORE": [0.5],
                "ROC_AVG": [0.25],
            }
        )

        screener._cached_data = mock_df

        output_path = tmp_path / "test_export.csv"
        screener.export(str(output_path), "csv", include_index=False)

        assert output_path.exists()
        content = output_path.read_text()
        assert "EURUSD" in content

    def test_export_json_format(self, tmp_path):
        screener = ForexOpportunityScreener(pairs=["EURUSD"], timeframes=["15"])

        mock_df = pd.DataFrame(
            {
                "Name": ["EURUSD"],
                "Price": [1.0850],
                "ENSEMBLE_SCORE": [0.5],
            }
        )

        screener._cached_data = mock_df

        output_path = tmp_path / "test_export.json"
        screener.export(str(output_path), "json", orient="records")

        assert output_path.exists()

    def test_export_invalid_format_raises(self, tmp_path):
        screener = ForexOpportunityScreener(pairs=["EURUSD"], timeframes=["15"])

        mock_df = pd.DataFrame({"Name": ["EURUSD"]})
        screener._cached_data = mock_df

        output_path = tmp_path / "test_export.xyz"

        with pytest.raises(ValueError, match="Unknown export format"):
            screener.export(str(output_path), "xyz")

    def test_export_with_metadata(self, tmp_path):
        screener = ForexOpportunityScreener(pairs=["EURUSD"], timeframes=["15"])

        mock_df = pd.DataFrame({"Name": ["EURUSD"], "Price": [1.0850], "ENSEMBLE_SCORE": [0.5]})
        screener._cached_data = mock_df

        output_path = tmp_path / "test_export.csv"
        metadata = {"pairs": ["EURUSD"], "timeframes": ["15"]}
        screener.export(str(output_path), "csv", include_index=False, metadata=metadata)


class TestContractTypeFilter:
    def test_contract_type_cfd_only(self):
        screener = ForexOpportunityScreener(
            pairs=["EURUSD"],
            timeframes=["15"],
            config=ForexScreenerConfig(contract_type="cfd"),
        )

        mock_df = pd.DataFrame(
            {
                "Name": ["EURUSD", "GBPUSD"],
                "Subtype": ["cfd", "spot"],
            }
        )

        result = screener._apply_contract_type_filter(mock_df)

        assert len(result) == 1
        assert result.iloc[0]["Name"] == "EURUSD"

    def test_contract_type_all_returns_all(self):
        screener = ForexOpportunityScreener(
            pairs=["EURUSD"],
            timeframes=["15"],
            config=ForexScreenerConfig(contract_type="all"),
        )

        mock_df = pd.DataFrame(
            {
                "Name": ["EURUSD", "GBPUSD"],
                "Subtype": ["cfd", "spot"],
            }
        )

        result = screener._apply_contract_type_filter(mock_df)

        assert len(result) == 2


class TestEdgeCases:
    def test_empty_dataframe_operations(self):
        screener = ForexOpportunityScreener(pairs=["EURUSD"], timeframes=["15"])

        mock_df = pd.DataFrame()

        result = screener._apply_score_and_roc_filters(mock_df)

        assert len(result) == 0

    def test_missing_volume_column(self):
        mock_df = pd.DataFrame(
            {
                "Name": ["EURUSD"],
                "Symbol": ["EURUSD:OANDA"],
            }
        )

        result = apply_volume_filter(mock_df, min_volume=1000000)

        assert len(result) == 1

    def test_null_rating_values_treated_as_neutral(self):
        mock_df = pd.DataFrame(
            {
                "Name": ["EURUSD"],
                "Symbol": ["EURUSD:OANDA"],
                "Recommend Ma|15": [None],
            }
        )

        result = apply_ma_score_filter(mock_df, min_ma_score=0.5)

        assert len(result) == 0
