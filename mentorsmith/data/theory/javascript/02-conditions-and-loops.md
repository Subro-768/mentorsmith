---
id: 02-conditions-and-loops
title: Type Coercion, Equality & Iteration Protocols
order: 2
lesson_id: 02-conditions-and-loops
summary: Loose (==) vs strict (===) equality, truthy/falsy coercion, and for..in vs for..of.
tags: equality, coercion, loops, for-of
---

# 2. Type Coercion, Equality & Iteration Protocols

### Strict Equality (`===`) vs Loose Equality (`==`)
Loose equality performs complex, counter-intuitive implicit type coercion rules:
```javascript
"" == 0          // true!
0 == false       // true!
null == undefined// true!
```
**Rule**: Always use strict equality (`===`) to ensure type and value identity without coercion.

---

### `for...in` vs `for...of`
- `for...in`: Iterates over the **keys (properties)** of an object (including prototype keys).
- `for...of`: Iterates over the **values** of an iterable (Array, Map, Set, generator).
