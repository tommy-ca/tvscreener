import os

import duckdb

# Create a file in HOME
home = os.path.expanduser("~")
test_file = os.path.join(home, "duckdb_test_tilde.csv")
with open(test_file, "w", encoding="utf-8") as f:
    f.write("a\n1")

con = duckdb.connect(":memory:")
try:
    path = "/home/tommyk/projects/quant/trading-view/tvscreener/~/duckdb_test_tilde.csv"
    res = con.execute(f"SELECT * FROM read_csv('{path}')").fetchall()
    print("DuckDB resolved middle tilde!", res)
except Exception as e:
    print("DuckDB failed middle tilde:", e)
