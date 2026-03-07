from pathlib import Path

p = Path("/tmp/does_not_exist/../malicious_file.txt")
print("Absolute:", p.absolute())
print("Resolved:", p.resolve())
