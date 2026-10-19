---
id: 03-functions
title: First-Class Functions, Scopes & Closures
order: 3
lesson_id: 03-functions
summary: LEGB scoping rule, closures, first-class functions, args/kwargs, and default argument traps.
tags: functions, legb, closures, scope, decorators
---

# 3. First-Class Functions, Scopes & Closures

### The LEGB Scoping Rule
Python resolves variable names in four successive scopes:
1. **L**ocal: Defined inside the current function.
2. **E**nclosing: Defined in outer nested enclosing functions.
3. **G**lobal: Module-level variables.
4. **B**uilt-in: System built-ins (`len`, `range`, `Exception`).

---

### The Mutable Default Argument Pitfall
Function default values are evaluated **once at module load time**, not per invocation:

```python
# DANGEROUS:
def append_to(element, target=[]):
    target.append(element)
    return target

# CORRECT:
def append_to(element, target=None):
    if target is None:
        target = []
    target.append(element)
    return target
```
