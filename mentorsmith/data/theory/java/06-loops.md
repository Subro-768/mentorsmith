---
id: 06-loops
title: Iteration, For-Each & Iterable Protocol
order: 6
lesson_id: 06-loops
summary: Loop constructs, labeled break/continue, the Iterable interface, and ConcurrentModificationException.
tags: loops, foreach, iterable, iterator
source_book: Programming with Java: A Primer
source_author: E. Balagurusamy
source_chapter: 7
source_page: 105
---

# 6. Iteration, For-Each & Iterable Protocol

### The Enhanced For-Each Loop
The enhanced `for (T item : collection)` loop is syntactic sugar. For collections, it compiles to:
```java
for (Iterator<T> it = collection.iterator(); it.hasNext(); ) {
    T item = it.next();
}
```

> **Warning**: Modifying a collection directly while iterating over it via for-each throws `ConcurrentModificationException`. Always use `Iterator.remove()` or removeIf!
