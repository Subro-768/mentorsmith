---
id: 01-variables-and-types
title: JavaScript Engine, Data Types & Scope Declarations
order: 1
lesson_id: 01-variables-and-types
summary: V8 engine, 7 primitives, object references, const/let TDZ, and typeof quirks.
tags: javascript, v8, types, let, const, tdz
---

# 1. JavaScript Engine, Data Types & Scope Declarations

### V8 Engine Pipeline
Modern JavaScript engines (like V8 in Node.js and Chrome) don't simply interpret text:
1. **Parser**: Generates Abstract Syntax Tree (AST).
2. **Ignition**: Bytecode interpreter producing fast execution.
3. **TurboFan**: Optimizing JIT compiler profiling hot functions and generating optimized machine code based on hidden classes (shapes).

---

### `const`, `let` vs `var` (Temporal Dead Zone)
- `var`: Function-scoped, hoisted and initialized to `undefined`.
- `let` / `const`: Block-scoped, hoisted into the **Temporal Dead Zone (TDZ)** where accessing them before declaration throws a `ReferenceError`.
