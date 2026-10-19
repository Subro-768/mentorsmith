---
id: 01-variables-and-types
title: Variables, Dynamic Typing & The Object Model
order: 1
lesson_id: 01-variables-and-types
summary: Everything is an object, reference assignment semantics, immutability, and memory identity.
tags: variables, types, immutability, references
---

# 1. Variables, Dynamic Typing & The Object Model

### Names Are Labels, Not Boxes
In languages like C or C++, a variable is a named memory location (a box) where bits are written. In Python, **variables are merely reference pointers (names) bound to objects residing in memory**.

```python
a = [1, 2, 3]
b = a          # b references the EXACT same list in memory!
b.append(4)
print(a)       # Prints [1, 2, 3, 4]
```

### Identity vs. Equality (`is` vs `==`)
- `==`: Value equality (evaluates `a.__eq__(b)`).
- `is`: Identity equality (checks `id(a) == id(b)` in memory).

```python
x = [1, 2]
y = [1, 2]
print(x == y)  # True (identical content)
print(x is y)  # False (different heap allocations)
```

---

### Mutable vs. Immutable Types
- **Immutable**: `int`, `float`, `bool`, `str`, `tuple`, `frozenset`, `bytes`. Modifying one produces a brand new object.
- **Mutable**: `list`, `dict`, `set`, `bytearray`, custom objects. Modified in-place.
