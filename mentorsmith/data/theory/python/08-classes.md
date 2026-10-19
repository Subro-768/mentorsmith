---
id: 08-classes
title: Classes, Dunder Methods & Metaclasses
order: 8
lesson_id: 08-classes
summary: __init__ vs __new__, method resolution order (C3 linearization), properties, and slots.
tags: oop, classes, dunder, mro, slots
---

# 8. Classes, Dunder Methods & Metaclasses

### `__new__` vs `__init__`
- `__new__(cls, ...)`: Class method responsible for **allocating** the instance. Returns a new instance.
- `__init__(self, ...)`: Instance method responsible for **initializing** the allocated instance's attributes.

---

### Optimization with `__slots__`
By default, Python objects store instance attributes in a dynamic `__dict__`, taking ~150 bytes per object. Declaring `__slots__` replaces `__dict__` with a fixed-size C array, cutting memory usage by 70%:

```python
class Vector:
    __slots__ = ("x", "y", "z")
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z
```
