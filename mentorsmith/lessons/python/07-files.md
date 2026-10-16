---
id: 07-files
title: Files
order: 7
---

## Objectives
- Read and write text files with `open()`.
- Use `with` so files always close.
- Choose between text and binary mode.
- Parse simple delimited data safely.

## Explanation
`open(path, mode)` returns a file object. The common modes:

| Mode | Meaning |
|---|---|
| `"r"` | Read (default) |
| `"w"` | Write, truncating the file |
| `"a"` | Append |
| `"x"` | Write, failing if the file exists |
| `"b"` | Binary, e.g. `"rb"` |

Always use a `with` block. It closes the file even if an exception is raised
part-way through:

```python
with open("notes.txt", "r", encoding="utf-8") as file:
    for line in file:
        print(line.rstrip())
```

Omitting `encoding="utf-8"` makes the default platform encoding, which is a
frequent source of trouble when sharing files.

**Check that reading worked.** Opening a missing file raises `FileNotFoundError`,
so handle it rather than letting the program die:

```python
try:
    with open("data.txt", encoding="utf-8") as file:
        content = file.read()
except FileNotFoundError:
    content = ""
```

**Writing and appending:**

```python
with open("log.txt", "w", encoding="utf-8") as file:
    file.write("first\n")
    file.write("second\n")

with open("log.txt", "a", encoding="utf-8") as file:
    file.write("third\n")
```

**Whole-file versus line-by-line.** `read()` loads everything into memory;
`readlines()` returns a list; iterating reads lazily and is better for large
files.

```python
text   = file.read()             # whole file as one string
lines  = file.readlines()        # whole file as a list
first  = file.readline()         # one line
```

**`pathlib` is the modern way to handle paths**, because it composes instead of
concatenating strings:

```python
from pathlib import Path

path = Path("data") / "marks.txt"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text("1 2 3\n", encoding="utf-8")
print(path.exists(), path.suffix, path.name)
```

**Parsing delimited text** with `str.split()` and `str.strip()`:

```python
name, mark = line.split(",")
mark = int(mark.strip())
```

Use `csv` for real comma-separated data, because quoted fields contain commas.

## Example
```python
# files.py
from pathlib import Path

RECORDS = Path("records.txt")


def write_records(rows):
    with RECORDS.open("w", encoding="utf-8") as file:
        for name, mark in rows:
            file.write(f"{name},{mark}\n")


def append_record(name, mark):
    with RECORDS.open("a", encoding="utf-8") as file:
        file.write(f"{name},{mark}\n")


def read_records():
    """Return parsed records, reporting a problem instead of crashing."""
    if not RECORDS.exists():
        return [], "no file yet"
    rows = []
    with RECORDS.open("r", encoding="utf-8") as file:
        for number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            if "," not in line:
                return rows, f"malformed record on line {number}"
            name, _, mark = line.partition(",")
            try:
                rows.append((name.strip(), int(mark.strip())))
            except ValueError:
                return rows, f"line {number} has a non-numeric mark"
    return rows, ""


write_records([("Ada", 93), ("Alan", 81)])
append_record("Grace", 74)

rows, problem = read_records()
print("rows   :", rows)
print("problem:", problem or "none")

if rows:
    total = sum(mark for _, mark in rows)
    print("average:", total / len(rows))

print("exists :", RECORDS.exists(), "| suffix:", RECORDS.suffix)
```

## Knowledge checks
Q: Why is `with open(...)` preferred over calling `open()` directly?
A: It closes the file on every path, including when an exception is raised inside the block.
Q: What does mode `"w"` do to an existing file?
A: Truncates it — the previous contents are lost. Use `"a"` to append.
Q: Why pass `encoding="utf-8"`?
A: Without it Python uses the platform default, which differs between systems and causes confusing decoding errors.
Q: What does `Path("data") / "marks.txt"` do?
A: Joins the two path components using the correct separator for the platform, without manual string concatenation.

## Exercise
Write `journal()` that appends one line of user input to `journal.txt` using
append mode, so earlier entries survive. Then write `count_entries()` that
reads the file back and returns how many non-blank lines it contains. Report a
missing file clearly rather than crashing.

```python starter
from pathlib import Path

JOURNAL = Path("journal.txt")


def append_entry(text):
    # Append text plus a newline to JOURNAL, checking for write failure.


def count_entries():
    # Return (count, problem). Missing file -> (0, "no journal yet").
```

## Common mistakes
- **Using `"w"` when you meant `"a"`,** silently destroying earlier data.
- **Forgetting `encoding="utf-8"`,** causing platform-dependent decoding errors.
- **Calling `open()` without `with`,** leaving the file open on an exception path.
- **Splitting on `","` when fields may contain commas.** Use the `csv` module.
- **Ignoring the return of `file.write`.** It returns the character count.

## Recap
- `open(path, mode)`; always use `with`.
- `"r"`, `"w"` (truncates), `"a"`, `"x"`; add `b` for binary.
- Pass `encoding="utf-8"` explicitly.
- Check for `FileNotFoundError` instead of crashing.
- `pathlib` composes paths and creates directories cleanly.