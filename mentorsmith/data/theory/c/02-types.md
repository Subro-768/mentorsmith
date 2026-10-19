---
id: 02-types
title: Types, Storage Classes & Word Representation
order: 2
lesson_id: 02-types
summary: Two's complement, integer promotion, storage classes (static, extern), and limits.h.
tags: types, storage-classes, integers, twocomplement
---

# 2. Types, Storage Classes & Word Representation

### Two's Complement Integer Representation
Almost all modern hardware implements negative integers using two's complement. To negate a number in binary: invert all bits and add 1.

### Storage Classes
- `auto`: Default local variable with automatic storage duration on the stack.
- `static`: 
  - On local variable: Preserves state across calls, stored in `.data` or `.bss`.
  - On global function/variable: Internal linkage, visible **only** within that specific `.c` file.
- `extern`: External linkage, references a global defined in another translation unit.
