import duckdb

con = duckdb.connect("test_readonly.duckdb")
con.execute("CREATE TABLE t AS SELECT 1 AS x")
con.close()

con = duckdb.connect("test_readonly.duckdb", read_only=True)
try:
    con.execute("COPY t TO 'test_output.csv'")
    print("COPY TO WORKED in read_only")
except Exception as e:
    print(f"COPY TO FAILED: {e}")
