---
id: 11-collections
title: The Collections Framework & Generics
order: 11
lesson_id: 11-collections
summary: List, Set, Queue, Map hierarchies, ArrayList array doubling, HashMap bucket hashing, and type erasure.
tags: collections, generics, hashmap, arraylist, type-erasure
source_book: Programming with Java: A Primer
source_author: E. Balagurusamy
source_chapter: 18
source_page: 341
---

# 11. The Collections Framework & Generics

### How `HashMap` Works Internally
- An array of buckets holding linked list nodes (or Red-Black balanced trees when a bucket exceeds 8 nodes — treeify threshold).
- Calculates index via `hash(key) & (n - 1)`.
- Keys must correctly implement both `equals()` and `hashCode()` contracts!

---

### Generics & Type Erasure
Java generics exist only at compile time for type safety. During compilation, generic type parameters (`List<String>`) are **erased** to their bounds (`List<Object>`), inserting implicit casts where necessary.
