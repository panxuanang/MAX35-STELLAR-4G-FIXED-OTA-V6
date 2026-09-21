#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: find_source_root.py <directory>")
base = Path(sys.argv[1]).resolve()
candidates = []
for cmake in base.rglob("CMakeLists.txt"):
    root = cmake.parent
    if (root / "main" / "CMakeLists.txt").exists() and (root / "main" / "boards").is_dir():
        candidates.append(root)
if not candidates:
    raise SystemExit(f"No Xiaozhi source root found under {base}")
candidates.sort(key=lambda p: (len(p.parts), str(p)))
print(candidates[0])
