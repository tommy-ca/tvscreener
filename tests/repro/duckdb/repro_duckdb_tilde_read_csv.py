import os

import duckdb

# Create a file in HOME
home = os.path.expanduser("~")
test_file = os.path.join(home, "duckdb_test_tilde.csv")
with open(test_file, "w", encoding="utf-8") as f:
    f.write("a\n1")

con = duckdb.connect(":memory:")
try:
    res = con.execute("SELECT * FROM read_csv('~/duckdb_test_tilde.csv')").fetchall()
    print("DuckDB resolved tilde!", res)
except Exception as e:
    print("DuckDB failed:", e)
