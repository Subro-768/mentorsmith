---
id: 06-loops
title: Iteration Constructs & Loop Optimization
order: 6
lesson_id: 06-loops
summary: For, while, range-based loops, vectorization, and cache locality during iteration.
tags: loops, iteration, cache-locality, vectorization
source_book: Object Oriented Programming with C++
source_author: Dhamodharan G, Balasubramanian, Priya K
source_chapter: 3
source_page: 12
---

# 6. Iteration Constructs & Loop Optimization

### Loop Mechanics & Cache Locality
Loops that process memory sequentially (stride 1) maximize hardware cache hit rates:

```cpp
// Cache-friendly: row-major traversal matches C++ contiguous memory layout
for (int r = 0; r < ROWS; ++r) {
    for (int c = 0; c < COLS; ++c) {
        matrix[r][c] += 1;
    }
}
```
Traversing columns first causes constant cache line evictions and orders of magnitude slower execution!

---

### Range-Based For Loops (C++11+)
Range-based for loops expand under the hood into iterator pairs:
```cpp
for (const auto& item : container) {
    // Uses const reference to eliminate expensive copy overhead
}
```
