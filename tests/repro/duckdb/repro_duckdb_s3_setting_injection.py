import duckdb

con = duckdb.connect(":memory:")
con.execute("INSTALL httpfs; LOAD httpfs;")

# Demonstrate that setting values should never be interpolated into SQL strings.
con.execute("SET s3_access_key_id=?", ["REDACTED_TEST_VALUE"])
res = con.execute("SELECT * FROM duckdb_settings() WHERE name='s3_access_key_id'").fetchall()
print("Found setting:", res)
