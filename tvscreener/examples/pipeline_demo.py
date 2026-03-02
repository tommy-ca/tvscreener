from pathlib import Path

import narwhals as nw
import pandas as pd

from tvscreener.lib.query import AnalyticsPipeline, EdgeQueryClient


def demo_pipeline():
    # 1. Setup sample data
    df = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT", "GOOGL", "TSLA"],
            "price": [150.0, 300.0, 2800.0, 700.0],
            "volume": [1000000, 800000, 500000, 1200000],
        }
    )

    parquet_path = Path("exports/test_data.parquet")
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(parquet_path)

    # 2. Define a Narwhals transformation
    @nw.narwhalify
    def filter_high_price(df):
        return df.filter(nw.col("price") > 200)

    # 3. Build and run the pipeline
    with EdgeQueryClient(":memory:") as client:
        pipeline = (
            AnalyticsPipeline(client, parquet_path)
            # SQL Step with Jinja2 and parameters
            .sql("SELECT * FROM df WHERE volume > {{ min_vol }}", params={"min_vol": 600000})
            # Narwhals Step
            .transform(filter_high_price)
            # Another SQL Step using DuckDB macros
            .sql("SELECT *, sma(price, 2) as price_sma FROM df")
        )

        result = pipeline.execute()
        print("Pipeline Result:")
        print(result)


if __name__ == "__main__":
    demo_pipeline()
