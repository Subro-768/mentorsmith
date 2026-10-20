---
id: 06-pointers
title: Pointers, Indirection & Memory Manipulation
order: 6
lesson_id: 06-pointers
summary: Direct memory addressing, double pointers, function pointers, and void pointers.
tags: pointers, indirection, memory, function-pointers
source_book: Programming in ANSI C
source_author: Ray Dawson
source_chapter: Section 10
source_page: 92
---

# 6. Pointers, Indirection & Memory Manipulation

### Pointer Indirection Levels
- `int *ptr`: Points directly to an integer.
- `int **pptr`: Points to an `int*` pointer (used to modify pointers passed to functions or represent dynamically allocated 2D arrays).

---

### Function Pointers
In C, functions have memory addresses. Function pointers enable callbacks and polymorphic behavior:
```c
int compare(const void *a, const void *b);
qsort(array, count, sizeof(int), compare);
```
