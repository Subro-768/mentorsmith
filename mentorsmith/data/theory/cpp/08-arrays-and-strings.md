---
id: 08-arrays-and-strings
title: Arrays, Contiguity & String Representations
order: 8
lesson_id: 08-arrays-and-strings
summary: C-style array decay, std::array, dynamic std::string, and std::string_view.
tags: arrays, strings, string_view, contiguity
---

# 8. Arrays, Contiguity & String Representations

### C Arrays vs `std::array` vs `std::vector`
- **C-style array (`int arr[10]`)**: Decays silently into a raw pointer (`int*`) when passed to functions, losing its size information.
- **`std::array<int, 10>`**: Zero-overhead wrapper providing `.size()`, bounds checking via `.at()`, and value semantics.
- **`std::vector<int>`**: Dynamic heap-allocated contiguous buffer that resizes dynamically with amortized $O(1)$ push.

---

### Modern Zero-Copy with `std::string_view` (C++17)
Passing a substring using traditional `std::string` allocates a new heap buffer. `std::string_view` represents a non-owning pointer and length, performing slicing in $O(1)$ with 0 allocations:

```cpp
void inspect(std::string_view sv) {
    // sv points directly into the caller's text buffer!
}
```
