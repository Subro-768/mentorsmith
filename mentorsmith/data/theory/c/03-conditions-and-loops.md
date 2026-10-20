---
id: 03-conditions-and-loops
title: Structured Control Flow & Branching Mechanics
order: 3
lesson_id: 03-conditions-and-loops
summary: Zero as false, while/do-while/for equivalence, and break/continue in C.
tags: branching, conditions, loops, control-flow
source_book: Programming in ANSI C
source_author: Ray Dawson
source_chapter: Section 6
source_page: 48
---

# 3. Structured Control Flow & Branching Mechanics

### The Concept of Boolean Truth in C
Historically, C had no built-in `bool` type (introduced in C99 via `<stdbool.h>`). In C, **any non-zero numerical value evaluates to true**, and **exactly zero (`0`) evaluates to false**.

```c
if (pointer) { /* true if pointer != NULL */ }
```

### The Comma Operator
In `for` loops, multiple expressions can be chained using the comma operator:
```c
for (int i = 0, j = 10; i < j; i++, j--) {
    // Both loop variables advance simultaneously
}
```
