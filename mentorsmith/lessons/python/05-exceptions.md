---
id: 05-exceptions
title: Exceptions and Errors
order: 5
---

## Objectives
- Catch exceptions with `try` / `except`.
- Read the traceback and find the real failing line.
- Raise your own exceptions with meaningful messages.
- Choose between raising and returning an error value.

## Explanation
When something goes wrong, Python *raises* an exception, which unwinds the
stack until something catches it:

```python
try:
    value = int("not a number")
except ValueError as error:
    print("bad input:", error)
```

`error` is the exception instance. `str(error)` gives its message.

**Catch specific exceptions, not everything.** `except:` with no type also
catches `KeyboardInterrupt` and `SystemExit`, which you must never swallow:

```python
# BAD - hides real problems
try:
    risky()
except:
    pass

# GOOD
try:
    risky()
except ValueError as error:
    print("handled:", error)
```

Common types you will meet:

| Exception | Cause |
|---|---|
| `ValueError` | Right type, wrong value (`int("abc")`) |
| `TypeError` | Wrong type (`"a" + 1`) |
| `IndexError` | List index out of range |
| `KeyError` | Dict key missing |
| `ZeroDivisionError` | Division by zero |
| `FileNotFoundError` | File does not exist |

**`else`, `finally` and `raise ... from`:**

```python
try:
    value = int(text)
except ValueError as error:
    print("rejected")
else:
    print("accepted", value)      # only if no exception
finally:
    print("always runs")
```

`finally` runs on every path, including an exception you did not catch. Use it
for cleanup.

**Raising your own exception** with a message that says what to do:

```python
def withdraw(balance, amount):
    if amount <= 0:
        raise ValueError("amount must be positive")
    if amount > balance:
        raise ValueError(f"cannot withdraw {amount} from a balance of {balance}")
    return balance - amount
```

`raise ... from error` preserves the cause, which makes tracebacks readable:

```python
try:
    int(text)
except ValueError as error:
    raise ValueError(f"expected a whole number, got {text!r}") from error
```

**Read the traceback bottom-up.** The last line names the exception; the line
above it is where it was raised; lines above that are the call chain.

## Example
```python
# exceptions.py
def safe_int(text):
    """Return an int, or None. Choosing to return rather than raise."""
    try:
        return int(text.strip())
    except (ValueError, AttributeError):
        return None


def total(values):
    if not values:
        raise ValueError("total needs at least one value")
    return sum(values)


def parse_all(texts):
    numbers = []
    for text in texts:
        try:
            numbers.append(int(text))
        except ValueError as error:
            print(f"skipping {text!r}: {error}")
    return numbers


print("safe_int('42')  :", safe_int("42"))
print("safe_int('abc') :", safe_int("abc"))

try:
    total([])
except ValueError as error:
    print("refused:", error)

print("parse_all       :", parse_all(["1", "two", "3", "nope", "5"]))

# finally always runs
handle = None
try:
    handle = open("example.txt", "w")
    raise RuntimeError("something went wrong mid-write")
except RuntimeError as error:
    print("caught:", error)
finally:
    if handle is not None:
        handle.close()
        print("closed in finally")

# re-raising with a clearer message
try:
    int("twelve")
except ValueError as error:
    try:
        raise TypeError(f"expected a whole number, got {'twelve'!r}") from error
    except TypeError as clearer:
        print("clearer:", clearer)
```

## Knowledge checks
Q: Why is bare `except:` a bad idea?
A: It catches everything including `KeyboardInterrupt` and `SystemExit`, so the program becomes impossible to stop and real errors are hidden.
Q: When does `finally` run?
A: On every path: normal completion, a caught exception, and an exception that propagates out.
Q: What does `raise ... from error` do?
A: Chains the new exception to the original so the traceback shows what actually caused it.
Q: How do you read a Python traceback?
A: Bottom-up. The final line names the exception and message; the line above it is where it was raised; further lines are the call chain.

## Exercise
Write `safe_divide(a, b)` that returns the result or raises a clear
`ValueError`. Then read a line with `input()`, convert it with `int()`, and
report any failure without crashing. Finally write `average(values)` that
raises `ValueError` for an empty list.

```python starter
def safe_divide(a, b):
    # Raise ValueError("division by zero") when b == 0, else return a / b


def read_number(prompt):
    # input(), then int(). Catch ValueError and return None.


def average(values):
    # Raise ValueError for an empty list, else return the mean.
```

## Common mistakes
- **Bare `except:`.** Catches `KeyboardInterrupt` too.
- **Catching and printing but not explaining.** Include the value that was wrong.
- **Using `pass` in an except block.** That silently discards the error.
- **Assuming the traceback's first line is the cause.** It is the last line.
- **Raising inside a `finally`.** It masks the original exception.

## Recap
- `try` / `except` / `else` / `finally`.
- Catch specific exception types.
- `raise ValueError("clear message")` for your own errors.
- Read tracebacks bottom-up.
- `finally` always runs; use it for cleanup.