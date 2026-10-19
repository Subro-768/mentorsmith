---
id: 09-classes-and-objects
title: Object Lifecycle, Heap Allocation & Garbage Collection
order: 9
lesson_id: 09-classes-and-objects
summary: Object headers, Mark-and-Sweep, generational GC (Eden, Survivor, Tenured), and constructor chaining.
tags: classes, oop, gc, heap, allocation
source_book: Programming with Java: A Primer
source_author: E. Balagurusamy
source_chapter: 8
source_page: 126
---

# 9. Object Lifecycle, Heap Allocation & Garbage Collection

### Generational Garbage Collection
The JVM divides the heap into generations based on the weak generational hypothesis (most objects die young):
- **Young Generation**:
  - `Eden Space`: Where new objects are initially allocated.
  - `Survivor Spaces (S0/S1)`: Where surviving objects are copied during Minor GC.
- **Old (Tenured) Generation**: Where long-lived objects reside after surviving multiple GC cycles.

---

### Constructor Chaining (`super` and `this`)
Subclass constructors invoke the superclass constructor first. If not written explicitly, the compiler inserts `super()` as the very first statement.
