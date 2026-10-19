---
id: 07-structures
title: Structures, Unions, Alignment & Bitfields
order: 7
lesson_id: 07-structures
summary: Struct memory layouts, offsetof macro, union memory sharing, and bitfields.
tags: structs, unions, bitfields, offsetof
---

# 7. Structures, Unions, Alignment & Bitfields

### Unions: Overlapping Memory Storage
A `union` allocates only enough memory to hold its single largest member. All members share the exact same starting memory address:

```c
union Data {
    int i;
    float f;
    char str[4];
}; // sizeof(union Data) is 4 bytes!
```
Writing to one field overwrites the data of the others.
