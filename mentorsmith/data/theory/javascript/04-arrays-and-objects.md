---
id: 04-arrays-and-objects
title: Object Prototypes, Descriptors & Array Methods
order: 4
lesson_id: 04-arrays-and-objects
summary: Prototype chains, Object.create, Property descriptors, and functional Array pipelines.
tags: objects, prototypes, arrays, functional
---

# 4. Object Prototypes, Descriptors & Array Methods

### The Prototype Chain
Every object in JavaScript has an internal link (`[[Prototype]]`, accessed via `Object.getPrototypeOf(obj)`) to another object:
- When accessing `obj.prop`, if not found on `obj`, the engine traverses up the prototype chain until found or reaching `null`.

---

### Immutable Functional Array Methods
Modern JavaScript favors non-mutating transformation pipelines:
- `.map()`: Transforms each element into a new array.
- `.filter()`: Selects elements based on a predicate.
- `.reduce()`: Accumulates elements into a single aggregate result.
