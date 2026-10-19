---
id: 07-files
title: File I/O, Encodings & Pathlib
order: 7
lesson_id: 07-files
summary: Text vs binary modes, UTF-8 encoding pitfalls, buffering, and object-oriented paths via pathlib.
tags: files, pathlib, utf-8, io
---

# 7. File I/O, Encodings & Pathlib

### Always Specify Encodings
Default file encodings vary across operating systems (UTF-8 on Linux, CP-1252 or Windows-1250 on Windows). Always state encoding explicitly:

```python
with open("data.txt", "r", encoding="utf-8") as f:
    text = f.read()
```

---

### Modern Filesystem Operations with `pathlib`
`pathlib.Path` replaces legacy `os.path` strings with clean object-oriented APIs:
```python
from pathlib import Path

p = Path("logs") / "today.log"
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text("All systems operational", encoding="utf-8")
```
