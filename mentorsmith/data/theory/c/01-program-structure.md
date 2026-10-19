---
id: 01-program-structure
title: C Architecture, Preprocessing & Linking
order: 1
lesson_id: 01-program-structure
summary: The original C translation model, macros, headers, object files, and the ABI.
tags: c, compilation, preprocessor, abi
---

# 1. C Architecture, Preprocessing & Linking

### The Simple C Machine Model
C was designed to map transparently to hardware registers and machine instructions. There is no runtime engine, garbage collection, or automatic metadata.

```
Source (.c) ──(cpp)──> Expanded Source ──(gcc/clang)──> Assembly ──(as)──> Object (.o) ──(ld)──> Binary
```

### Direct Prototypes & Declarations
Before a function can be called in C, its prototype must be declared:
```c
int calculate_sum(int a, int b); // Function prototype declaration
```
In C99 and later, implicit function declarations are illegal.
