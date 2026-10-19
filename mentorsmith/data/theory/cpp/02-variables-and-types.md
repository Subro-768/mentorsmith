---
id: 02-variables-and-types
title: Fundamental Types, Storage & Value Categories
order: 2
lesson_id: 02-variables-and-types
summary: Memory representations, signed vs unsigned integer overflow, IEEE 754 floating point, and const correctness.
tags: types, memory, integers, const, ieee754
source_book: Object Oriented Programming with C++
source_author: Dhamodharan G, Balasubramanian, Priya K
source_chapter: 2
source_page: 3
---

# 2. Fundamental Types, Storage & Value Categories

### Memory Representation & Architecture Sizes
C++ maps primitive types directly to underlying hardware words:

| Type | Typical Size (x86_64) | Value Range | Note |
|---|---|---|---|
| `bool` | 1 byte | `true` or `false` | Must have addressable byte size |
| `char` | 1 byte | -128 to 127 or 0 to 255 | Character literal / smallest addressable unit |
| `int` | 4 bytes | $-2^{31}$ to $2^{31}-1$ | Default architecture integer |
| `long long` | 8 bytes | $-2^{63}$ to $2^{63}-1$ | Guaranteed at least 64 bits |
| `float` | 4 bytes | $pprox \pm 3.4 	imes 10^{38}$ | IEEE 754 single precision (7 decimals) |
| `double` | 8 bytes | $pprox \pm 1.7 	imes 10^{308}$ | IEEE 754 double precision (15 decimals) |

---

### The Signed vs. Unsigned Trap
Unsigned integers obey modulo arithmetic:
- In C++, unsigned arithmetic overflows wrap around safely defined as $(x \pmod{2^N})$.
- **Signed integer overflow is Undefined Behavior (UB)**. The compiler assumes signed overflow never occurs and may optimize out boundary checks!

```cpp
// DANGEROUS: Mixing signed and unsigned comparisons
int count = -1;
unsigned int size = 5;
if (count < size) {
    // This branch will NOT execute!
    // 'count' is implicitly converted to an unsigned integer, becoming ~4.29 billion.
}
```

---

### Const Correctness
The `const` qualifier locks an identifier against modification, verified at compile time:

```cpp
const int max_retry = 3;
// max_retry = 4; // Compile-time error!
```
Enforcing `const` on read-only variables and parameters unlocks compiler optimizations and eliminates entire classes of mutation bugs.
