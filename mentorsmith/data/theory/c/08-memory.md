---
id: 08-memory
title: Dynamic Memory Allocation & Heap Management
order: 8
lesson_id: 08-memory
summary: malloc, calloc, realloc, free, heap fragmentation, and valgrind memory auditing.
tags: memory, malloc, free, heap, valgrind
source_book: Programming in ANSI C
source_author: Ray Dawson
source_chapter: Section 11
source_page: 106
---

# 8. Dynamic Memory Allocation & Heap Management

### The Dynamic Allocation Family
- `malloc(size)`: Allocates `size` uninitialized bytes.
- `calloc(num, size)`: Allocates and zeros all memory bits.
- `realloc(ptr, new_size)`: Expands or shrinks an existing heap block, relocating if necessary.
- `free(ptr)`: Releases the allocated block back to the allocator.

> **Rules of Memory Safety**:
> 1. Every successful `malloc` must be paired with exactly one `free`.
> 2. Never dereference a pointer after freeing it (Dangling pointer / Use-After-Free).
> 3. Set pointers to `NULL` immediately after freeing.
