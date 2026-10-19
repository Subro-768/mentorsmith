---
id: 05-exceptions
title: Exception Hierarchy & Context Managers
order: 5
lesson_id: 05-exceptions
summary: Python exception tree, traceback analysis, EAFP vs LBYL, and the __enter__/__exit__ protocol.
tags: exceptions, context-managers, eafp, with
---

# 5. Exception Hierarchy & Context Managers

### EAFP vs. LBYL
- **LBYL (Look Before You Leap)**: Check preconditions before acting.
- **EAFP (Easier to Ask for Forgiveness than Permission)**: Pythonic idiom — execute the code and handle errors if they arise.

```python
# Pythonic EAFP
try:
    val = mapping[key]
except KeyError:
    val = default
```

---

### The Context Manager Protocol (`with`)
The `with` statement ensures deterministic resource acquisition and cleanup:
```python
class ManagedResource:
    def __enter__(self):
        # acquire resource
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        # guaranteed release, even if an exception was raised
        return False
```
