---
id: 07-functions
title: Functions, Call Stacks & Calling Conventions
order: 7
lesson_id: 07-functions
summary: Stack frame layout, pass-by-value vs pass-by-reference, inlining, and name mangling.
tags: functions, stack, calling-conventions, inlining
---

# 7. Functions, Call Stacks & Calling Conventions

### Stack Frames and Activation Records
When a function is called:
1. Arguments are passed via registers (or pushed to the stack).
2. The return address is stored.
3. The stack pointer is decremented to reserve room for local variables.
4. On return, the frame pointer is restored and the instruction pointer jumps back.

---

### Pass Semantics
- **Pass by Value**: Copies the argument. Good for small primitive types ($\le 8$ bytes).
- **Pass by Const Reference (`const T&`)**: Passes memory address without allowing mutation. Optimal for large structs, objects, vectors, and strings.
- **Pass by Non-Const Reference (`T&`)**: Allows in-place mutation of the caller's variable.

```cpp
void process(const std::vector<std::string>& data); // Zero copy!
```

---

### The `inline` Specifier
`inline` advises the compiler to replace the call site directly with the function body, eliminating call/return overhead and unlocking cross-statement optimizations.
