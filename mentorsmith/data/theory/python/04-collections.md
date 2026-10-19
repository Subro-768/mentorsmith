---
id: 04-collections
title: Collections, Hashing & Memory Complexity
order: 4
lesson_id: 04-collections
summary: Dynamic array over-allocation in lists, hash tables in dicts/sets, collision resolution, and comprehensions.
tags: collections, list, dict, hash-table, amortized
---

# 4. Collections, Hashing & Memory Complexity

### How Python `dict` Works: Compact Hash Tables
Since Python 3.6, dicts use a compact hash table design:
- An **indices array** stores sparse hash buckets.
- An **entries array** stores dense `[hash, key, value]` in insertion order.
- Average lookup, insert, and delete are $O(1)$.
- Keys must be **hashable** (implementing `__hash__` and immutable).

---

### List Growth Factor
`list` is an array of object pointers. When capacity is exceeded, Python over-allocates with growth proportional to $(N + (N \gg 3) + 6)$, guaranteeing amortized $O(1)$ append.
