---
id: 07-modules
title: ES Modules, CommonJS & Dynamic Imports
order: 7
lesson_id: 07-modules
summary: ESM vs CommonJS, live bindings, static analysis, and code splitting with dynamic import().
tags: modules, esm, commonjs, import, export
---

# 7. ES Modules, CommonJS & Dynamic Imports

### ES Modules (ESM) vs CommonJS (CJS)
- **CommonJS (`require` / `module.exports`)**: Synchronous, dynamic, loads at runtime. Values are copied.
- **ES Modules (`import` / `export`)**: Asynchronous, statically analyzable at compile/parse time, supports tree-shaking, and exposes **live bindings**.
