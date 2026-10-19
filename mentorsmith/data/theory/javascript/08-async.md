---
id: 08-async
title: The Event Loop, Promises & Async/Await
order: 8
lesson_id: 08-async
summary: Call stack, Task queue, Microtask queue, Promise lifecycle, and async/await mechanics.
tags: async, eventloop, promises, microtasks
---

# 8. The Event Loop, Promises & Async/Await

### The Event Loop & Microtask Priority
JavaScript execution is single-threaded. Concurrency is orchestrated by the Event Loop:
```
Call Stack ──> Microtask Queue (Promises, queueMicrotask) ──> Task Queue (setTimeout, I/O)
```
- **Rule**: After every completed script or task, the engine **drains the entire Microtask Queue completely** before picking the next task from the Task Queue!

```javascript
console.log("1");
setTimeout(() => console.log("4"), 0); // Task Queue
Promise.resolve().then(() => console.log("3")); // Microtask Queue
console.log("2");
// Output: 1, 2, 3, 4
```

---

### Async / Await
`async`/`await` is syntactic sugar over native Promises and Generators:
- An `async` function always returns a Promise.
- `await` pauses execution of the surrounding async function non-blockingly, yielding control back to the event loop until the awaited Promise settles.
