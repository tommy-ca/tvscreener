import os

import duckdb

con = duckdb.connect(":memory:")
con.execute("INSTALL httpfs; LOAD httpfs;")
try:
    con.execute("SET s3_access_key_id=?", ["test_key"])
    print("SET with parameters WORKED")
except Exception as e:
    print(f"SET with parameters FAILED: {e}")

try:
    con = duckdb.connect("test.duckdb", read_only=False)
    con.execute("CREATE TABLE t1 (i INTEGER)")
    con.close()

    con = duckdb.connect("test.duckdb", read_only=True)
    con.execute("SET lock_configuration=True;")
    print("SET lock_configuration on read_only WORKED")
except Exception as e:
    print(f"SET lock_configuration FAILED: {e}")
finally:
    if os.path.exists("test.duckdb"):
        os.remove("test.duckdb")
