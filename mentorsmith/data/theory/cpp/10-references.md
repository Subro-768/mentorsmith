---
id: 10-references
title: References & Aliasing
order: 10
lesson_id: 10-references
summary: Lvalue references, aliases, immutable binding, and differences between pointers and references.
tags: references, lvalue, aliasing
---

# 10. References & Aliasing

### References as Permanent Aliases
A reference is not a distinct object in memory—it is a compiler-enforced alias for an existing variable:

```cpp
int original = 10;
int& ref = original; // ref IS original
ref = 50;            // original is now 50
```

### Core Invariants:
1. **Must be initialized**: A reference cannot exist unattached (`int& r;` is a compile error).
2. **Cannot be reseated**: Reassigning a reference copies into the target; it does not redirect the alias.
3. **Cannot be null**: Eliminates null checks common with pointers.
