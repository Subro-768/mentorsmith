---
id: 02-conditions-and-loops
title: Control Flow, Truthiness & Iterator Protocol
order: 2
lesson_id: 02-conditions-and-loops
summary: Truthiness semantics, short-circuit boolean logic, for-else constructs, and generators.
tags: flow, truthiness, loops, iterators
---

# 2. Control Flow, Truthiness & Iterator Protocol

### Truthiness: The `__bool__` and `__len__` Protocol
In Python, objects evaluate to `False` in conditional contexts if:
- They are constants: `None`, `False`.
- They are zero of any numeric type: `0`, `0.0`, `0j`.
- They are empty sequences/collections: `""`, `()`, `[]`, `{}`, `set()`.

---

### The `for...else` Pattern
Python loops feature an optional `else` block: it executes **only if the loop finishes naturally without encountering a `break`**:

```python
for item in items:
    if item == target:
        found = True
        break
else:
    print("Item was not found in the sequence")
```
