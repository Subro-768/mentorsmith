---
id: 12-structures
title: Structures, Memory Alignment & Padding
order: 12
lesson_id: 12-structures
summary: Aggregates, struct packing, alignment constraints, and cache alignment.
tags: structs, padding, alignment, sizeof
source_book: Object Oriented Programming with C++
source_author: Dhamodharan G, Balasubramanian, Priya K
source_chapter: 5
source_page: 23
---

# 12. Structures, Memory Alignment & Padding

### Memory Alignment and Struct Padding
CPUs fetch data from memory aligned to natural word boundaries (e.g., 4-byte boundaries for 32-bit ints, 8-byte for 64-bit pointers).

```cpp
struct Inefficient {
    char a;    // 1 byte + 3 bytes padding
    int b;     // 4 bytes
    char c;    // 1 byte + 7 bytes padding
    double d;  // 8 bytes
}; // Total: 24 bytes!

struct Optimized {
    double d;  // 8 bytes
    int b;     // 4 bytes
    char a;    // 1 byte
    char c;    // 1 byte + 2 bytes padding
}; // Total: 16 bytes!
```
Arranging members in decreasing order of size minimizes wasted padding bytes.
