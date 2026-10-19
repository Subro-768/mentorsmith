---
id: 16-multithreading
title: Threads, Synchronisation & the `Runnable` Contract
order: 16
lesson_id: 17-multithreading
summary: Creating threads, the Runnable contract, shared state, synchronized methods, and the states a thread moves through.
tags: threads, concurrency, synchronization, runnable
source_book: Programming with Java: A Primer
source_author: E. Balagurusamy
source_chapter: 12
source_page: 207
---

# 16. Threads, Synchronisation & the `Runnable` Contract

A thread is an independent path of execution inside one program. The JVM
gives you at least one; `main` runs on one. Starting another is one call.

```java
class Worker implements Runnable {
    public void run() {
        for (int i = 0; i < 5; i++) System.out.println("work " + i);
    }
}

Thread t = new Thread(new Worker());
t.start();     // not run() - start() asks the scheduler to run it
```

### `Thread` vs `Runnable`
`Runnable` is the better choice, for two practical reasons: a class can
implement `Runnable` and still extend something else, and the same
`Runnable` can be handed to several threads. Extending `Thread` gives you
one task per class and no way to share it.

```java
new Thread(() -> System.out.println("hello")).start();
```

### The states of a thread
```
new ──start()──> runnable ──scheduler picks it──> running
                                                  │
        ┌─────────────────────────────────────────┤
        │                                         ▼
     blocked (waiting for a lock)          waiting (sleep/join/wait)
        │                                         │
        └─────────────────────────────────────────┴──> terminated
```
`BLOCKED` means "waiting for a monitor"; `WAITING` means "waiting for
something to happen". The distinction matters when reading a thread dump.

### Shared state needs protection
Two threads incrementing the same counter without synchronisation lose
updates, because `count++` is three steps: read, add, store.

```java
private int count = 0;
synchronized void increment() { count++; }   // one thread at a time
```

`synchronized` locks the object's monitor for the duration of the method.
`synchronized (lock) { ... }` locks an explicit object instead, which is
better when several fields need to move together.

### The `wait` / `notify` rules
- `wait()` releases the monitor and parks the thread; `notify()` wakes one
  waiter; `notifyAll()` wakes all of them.
- Always call `wait()` inside a `while` loop, not `if` - a thread can wake
  up for a reason that is no longer true.
- The monitor must be held when calling `wait()` or `notify()`.

### `volatile` and thread safety
`volatile` guarantees a thread sees the latest value of a field, and it
prevents the compiler from caching it in a register. It does **not** make
compound operations atomic: `count++` is still three steps. Use
`AtomicInteger` for counters, or `synchronized` for anything compound.

### Common mistakes
- Calling `run()` instead of `start()` - the method then runs on the calling
  thread and nothing is concurrent at all.
- Synchronizing on a boxed `Integer` or a `String` literal: the value is
  shared across the whole program, so unrelated code can lock the same
  object.
- Assuming `volatile` makes a counter safe.
- Holding a lock while doing slow work.

### Review questions
1. What is the difference between calling `run()` and `start()` on a
   thread?
2. Why is implementing `Runnable` usually better than extending `Thread`?
3. What is the difference between a `BLOCKED` thread and a `WAITING` one?
4. Why can two threads lose an increment even when each individual read
   and write is atomic?
5. What does `synchronized` lock, and what does `synchronized (lock)` lock
   instead?
6. Why must `wait()` be called in a `while` loop rather than an `if`?
7. What does `volatile` guarantee, and what does it not guarantee?
8. Why is synchronizing on a `String` literal dangerous?

### Practice
Write a `Counter` class with a `synchronized` increment method and a plain
one. Start four threads that each increment it a thousand times, one using
the synchronized version and one not. Print the final count in both cases
and explain the difference.
