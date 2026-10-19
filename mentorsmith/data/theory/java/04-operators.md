---
id: 04-operators
title: Operators, Short-Circuit Evaluation & Numeric Promotion
order: 4
lesson_id: 04-operators
summary: Integer division, binary numeric promotion, bitwise operators, and String concatenation bytecode.
tags: operators, promotion, modulo, bitwise
source_book: Programming with Java: A Primer
source_author: E. Balagurusamy
source_chapter: 5
source_page: 60
---

# 4. Operators, Short-Circuit Evaluation & Numeric Promotion

### Binary Numeric Promotion
When evaluating expressions with mixed operand types, Java automatically promotes the smaller type:
- If any operand is `double`, the other is promoted to `double`.
- Otherwise, if any operand is `float`, the other is promoted to `float`.
- Otherwise, if any operand is `long`, the other is promoted to `long`.
- Otherwise, both operands are promoted to `int` (even if both are `byte` or `short`!).

---

### String Concatenation (`+`)
Under the hood, `String a + b` is rewritten by the compiler to use `StringBuilder.append()` or `invokedynamic` (StringConcatFactory in Java 9+), avoiding intermediate allocations.
