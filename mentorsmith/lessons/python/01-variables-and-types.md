---
id: 01-variables-and-types
title: Variables and Types
order: 1
---

## Objectives
- Create variables and understand that names, not types, hold the meaning.
- Meet the core built-in types: `int`, `float`, `str`, `bool`.
- Explain why Python has no declaration keyword.
- Use `type()` and `isinstance()` to inspect a value.

## Explanation
Python has no `int x = 5;` declaration. A name simply starts pointing at a
value:

```python
age = 30
pi = 3.14159
name = "Ada"
is_valid = True
```

The core types:

| Type | Example | Notes |
|---|---|---|
| `int` | `30` | Arbitrarily large — `2**100` is fine |
| `float` | `3.14` | Floating point, so `0.1 + 0.2 != 0.3` |
| `str` | `"Ada"` | Immutable text |
| `bool` | `True` | Subclass of `int`; `True == 1` is True |

**Python is dynamically typed**, meaning the type belongs to the value, not the
name. You can rebind a name to a different type, which is legal but usually a
mistake:

```python
x = 10
x = "ten"        # legal, but confusing — pick a new name instead
```

`type(value)` reports the type. `isinstance(value, int)` is more useful when you
want to ask a question rather than print a label.

`int` is unbounded, which removes a whole class of C++ overflow bugs:

```python
big = 2 ** 200
print(big)          # a very long number, no overflow
```

Watch the trap that carries over from C++: division between two `int`s gives a
`float` in Python, unlike C and C++.

```python
print(7 / 2)        # 3.5  <- Python's true division
print(7 // 2)       # 3    <- floor division, the integer answer
```

## Example
```python
# variables_and_types.py
name = "Ada"
age = 36
height = 1.62
is_student = False

print(name, type(name).__name__)
print(age, type(age).__name__)
print(height, type(height).__name__)
print(is_student, type(is_student).__name__)

print(isinstance(age, int))          # True
print(isinstance(age, float))        # False
print(isinstance(height, (int, float)))  # either is acceptable

total = 7 / 2
whole = 7 // 2
print(total, whole)                  # 3.5 3
```

## Knowledge checks
Q: Why does Python not need `int age = 30;`?
A: Python is dynamically typed, so a name is bound to a value and the type travels with the value rather than being declared.
Q: What does `7 / 2` produce in Python, and how do you get the integer answer?
A: `3.5`. Use `7 // 2` for floor division, which gives `3`.
Q: What happens if you assign a string to a variable that held an integer?
A: Nothing errors. Python allows rebinding, and the name then refers to a `str` instead. It is legal but usually confusing.

## Exercise
Create variables for a book: `title` (a string), `pages` (an integer), `price`
(a float) and `in_stock` (a boolean). Print each value on its own line with its
type name, then print `True` or `False` for whether the book costs more than 10.

```python starter
title = "Dune"
pages = 412
price = 9.99
in_stock = True

# Print each value followed by its type name, one per line.
# Then print whether price is more than 10.
```

## Common mistakes
- **Using `;`** at line ends. Python uses newlines; a semicolon is legal but wrong style.
- **Expecting C++ integer division.** `7 / 2` is `3.5`, not `3`.
- **Assuming a name has a fixed type.** It can be rebound to anything.
- **Using `=` for comparison.** In Python assignment is `=` and comparison is `==`, unlike C++ where both meanings exist.
- **Shadowing a builtin** by calling a variable `list` or `sum`.

## Recap
- Names bind to values; types belong to values.
- Core types: `int`, `float`, `str`, `bool`.
- `int` does not overflow.
- `/` is true division, `//` is floor division.
- `type()` and `isinstance()` are your inspection tools.