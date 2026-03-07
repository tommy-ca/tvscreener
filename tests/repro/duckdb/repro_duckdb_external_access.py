import duckdb

con = duckdb.connect(":memory:")
con.execute("SET enable_external_access=False")
try:
    con.execute("SELECT * FROM read_csv('/etc/passwd')")
    print("read_csv WORKED")
except Exception as e:
    print(f"read_csv FAILED: {e}")
