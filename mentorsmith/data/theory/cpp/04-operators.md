---
id: 04-operators
title: Operators, Precedence & Evaluation Order
order: 4
lesson_id: 04-operators
summary: Arithmetic, bitwise manipulation, short-circuit evaluation, and sequencing rules.
tags: operators, precedence, bitwise, short-circuit
source_book: Object Oriented Programming with C++
source_author: Dhamodharan G, Balasubramanian, Priya K
source_chapter: 2.5
source_page: 5
---

# 4. Operators, Precedence & Evaluation Order

### Bitwise Manipulation Techniques
Bitwise operators operate directly on binary representations:
- `&` (AND), `|` (OR), `^` (XOR), `~` (NOT), `<<` (Left Shift), `>>` (Right Shift).

```cpp
// Setting a bit:
flags |= (1 << 3);

// Clearing a bit:
flags &= ~(1 << 3);

// Checking a bit:
bool is_set = (flags & (1 << 3)) != 0;
```

---

### Short-Circuit Evaluation
Logical `&&` and `||` evaluate left-to-right with short-circuit semantics:
- If the left operand of `&&` evaluates to `false`, the right operand is **never executed**.
- If the left operand of `||` evaluates to `true`, the right operand is **never executed**.

This makes safe pointer dereferences idiomatic:
```cpp
if (ptr != nullptr && ptr->is_valid()) {
    // Safe: is_valid() only called if ptr is not null
}
```
