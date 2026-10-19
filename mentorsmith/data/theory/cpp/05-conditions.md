---
id: 05-conditions
title: Branching, Jump Tables & Modern Conditionals
order: 5
lesson_id: 05-conditions
summary: If-else statements, switch statement jump tables, and C++17 init-statements.
tags: branching, if, switch, jump-table, cpp17
---

# 5. Branching, Jump Tables & Modern Conditionals

### How the Hardware Executes Branches
Modern CPUs utilize branch predictors to speculate ahead of conditional jumps. Code with consistent branching patterns runs in fewer clock cycles than random branches due to branch misprediction penalties.

### Switch Statements & Jump Tables
When a `switch` has dense, sequential cases, the compiler emits a **jump table**: an array of code pointers indexed in $O(1)$ time rather than evaluating a cascading series of $O(N)$ comparisons.

```cpp
switch (op) {
    case '+': return a + b;
    case '-': return a - b;
    default:  return 0;
}
```

---

### C++17 Init-Statements in Conditions
C++17 introduced scoped variables directly inside `if` and `switch` statements:

```cpp
if (auto it = cache.find(key); it != cache.end()) {
    // 'it' is tightly scoped only to this branch
    use(it->second);
}
```
This prevents leaking temporary query iterators into surrounding function scope.
