---
id: 06-modules
title: Modules and Imports
order: 6
---

## Objectives
- Split code across modules.
- Use `import`, `from ... import ...` and aliases.
- Explain `if __name__ == "__main__":`.
- Avoid circular imports.

## Explanation
A **module** is just a `.py` file. A **package** is a directory of modules with
an `__init__.py`. Splitting code keeps each file focused and makes it testable
in isolation.

```python
# geometry.py
import math

def area(radius):
    return math.pi * radius * radius

def circumference(radius):
    return 2 * math.pi * radius
```

Import it:

```python
# main.py
import geometry                     # use geometry.area(...)
from geometry import area            # use area(...)
import geometry as geo               # use geo.area(...)
from math import pi, sqrt           # bring in specific names
```

**Standard library modules worth knowing:**

| Module | Contents |
|---|---|
| `math` | `pi`, `sqrt`, `floor` |
| `os` / `pathlib` | Filesystem and paths |
| `json` | Read and write JSON |
| `datetime` | Dates and times |
| `random` | Pseudo-random numbers |
| `sys` | Interpreter details |
| `statistics` | `mean`, `median`, `stdev` |

**`if __name__ == "__main__":`** guards the code that should run only when the
file is executed directly, not when it is imported:

```python
def main():
    print("running")

if __name__ == "__main__":
    main()
```

Without the guard, importing your module for testing would run its demo code.

**Circular imports** (A imports B, B imports A) fail at import time. Break the
cycle by moving shared definitions into a third module that both depend on, or
by importing inside the function that needs it:

```python
def load():
    import json          # deferred import avoids the cycle
    ...
```

**`__all__`** controls what `from module import *` exposes. Prefer explicit
imports so readers can see where each name comes from.

## Example
```python
# stats_tool.py - a module with no side effects
import statistics


def summarise(values):
    if not values:
        raise ValueError("need at least one value")
    return {
        "count": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def best_index(values):
    """Index of the largest value; the first one if tied."""
    if not values:
        raise ValueError("need at least one value")
    return max(range(len(values)), key=lambda i: values[i])
```

```python
# run_stats.py - imports the module
from stats_tool import summarise, best_index

marks = [70, 85, 92, 60, 78]

report = summarise(marks)
for key, value in report.items():
    print(f"{key:8}: {value:.2f}")

print("best index:", best_index(marks))
print("top value :", marks[best_index(marks)])


# Only runs when executed directly, so importing run_stats is side-effect free.
if __name__ == "__main__":
    print("done")
```

Run it:

```bash
python3 run_stats.py
```

## Knowledge checks
Q: Why guard demo code with `if __name__ == "__main__":`?
A: So the code runs only when the file is executed, not when it is imported by another module or a test.
Q: What is the difference between `import geometry` and `from geometry import area`?
A: The first binds the module name and needs `geometry.area(...)`; the second binds `area` directly.
Q: What causes a circular import error?
A: Two modules importing each other at module level. Break the cycle by extracting shared code into a third module or deferring the import into a function.

## Exercise
Split a small calculator into two files. `calc.py` holds `add`, `subtract`,
`multiply` and `divide` where `divide` raises `ValueError` for a zero divisor.
`run_calc.py` imports them, reads two numbers, and prints all four results,
reporting the divide failure if one occurs. Guard the demo with
`if __name__ == "__main__":`.

```python starter
# calc.py

def divide(a, b):
    # Raise ValueError when b == 0, else return a / b
```

```python starter
# run_calc.py
# Import the four functions, read two numbers, print each result.
# Handle the ZeroDivision-style failure from divide without crashing.
# Put the demo under if __name__ == "__main__":
```

## Common mistakes
- **Running demo code at import time.** Guard it.
- **Using `import *`.** It hides where names come from.
- **Circular imports.** Extract shared code or import inside the function.
- **Expecting a relative import from the command line.** Modules run as `__main__` when executed directly; use absolute imports between your own files.
- **Creating files in the directory you run from.** Use `pathlib`.

## Recap
- A module is a `.py` file; a package is a directory with `__init__.py`.
- `import x`, `from x import y`, and `as` aliases all work.
- Guard entry points with `if __name__ == "__main__":`.
- Break import cycles by extracting shared definitions.
- Prefer explicit imports over `import *`.