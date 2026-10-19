---
id: 05-scope
title: Closures, Lexical Scope & Garbage Collection
order: 5
lesson_id: 05-scope
summary: Lexical environment, closure mechanics, module pattern, and memory leak prevention.
tags: closures, scope, memory, leak-prevention
---

# 5. Closures, Lexical Scope & Garbage Collection

### What Is a Closure?
A **closure** is the combination of a function bundled together with references to its surrounding lexical environment:
```javascript
function makeCounter() {
    let count = 0; // Enclosed private variable
    return function() {
        return ++count;
    };
}
const counter = makeCounter();
console.log(counter()); // 1
console.log(counter()); // 2
```
Even after `makeCounter()` finishes execution, `count` remains alive in memory because the returned inner function maintains a live reference to it.
