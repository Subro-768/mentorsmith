---
id: 03-functions
title: Functions, Arrow Functions & Lexical `this`
order: 3
lesson_id: 03-functions
summary: Function declarations vs expressions, arrow functions, execution context, and call/apply/bind.
tags: functions, arrow-functions, this, execution-context
---

# 3. Functions, Arrow Functions & Lexical `this`

### How `this` Is Determined
Unlike most OOP languages, `this` in standard JavaScript functions is determined by **how the function was invoked at runtime**:
- Method call (`obj.method()`): `this` is `obj`.
- Direct function call (`fn()`): `this` is `globalThis` (or `undefined` in strict mode).
- Explicit binding: `fn.call(ctx)`, `fn.apply(ctx)`, `fn.bind(ctx)`.

---

### Arrow Functions
Arrow functions (`() => {}`) **do not have their own `this` binding**. They lexically inherit `this` from the enclosing lexical scope, making them ideal for callbacks.
