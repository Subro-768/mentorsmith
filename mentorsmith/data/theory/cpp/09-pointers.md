---
id: 09-pointers
title: Pointers, Memory Addresses & Pointer Arithmetic
order: 9
lesson_id: 09-pointers
summary: Address-of operator, dereferencing, pointer arithmetic, void pointers, and nullptr.
tags: pointers, memory, addresses, pointer-arithmetic
---

# 9. Pointers, Memory Addresses & Pointer Arithmetic

### Pointer Fundamentals
A pointer is an unsigned integer containing the direct memory address of a byte in the process's virtual address space:

```cpp
int x = 42;
int* ptr = &x;     // & takes the address
*ptr = 100;        // * dereferences to read or modify the pointed-to memory
```

---

### Pointer Arithmetic
Pointer arithmetic scales automatically by `sizeof(T)`:
```cpp
int arr[5] = {10, 20, 30, 40, 50};
int* p = arr;
p += 2; // Increments address by 2 * sizeof(int) = 8 bytes
std::cout << *p; // Prints 30
```

---

### Null Pointers: `nullptr` vs `NULL`
Always use `nullptr` (C++11). Unlike old C `NULL` (which was `#define NULL 0`), `nullptr` is strongly typed (`std::nullptr_t`) and cannot mistakenly bind to integer overloads.
