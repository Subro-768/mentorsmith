---
id: 17-multithreading
title: Threads and Synchronisation
order: 17
tier: advanced
---

## Objectives
- Start a thread with `Runnable`.
- Explain what `start()` does that `run()` does not.
- Protect shared state with `synchronized`.
- Say what `volatile` does and does not guarantee.

## Explanation
A thread is an independent path of execution. The JVM gives you at least
one; `main` runs on it.

```java
class Worker implements Runnable {
    public void run() {
        for (int i = 0; i < 5; i++) System.out.println("work " + i);
    }
}

new Thread(new Worker()).start();
```

- Implement `Runnable` rather than extending `Thread`: a class can then extend something else as well, and the same task can be given to several threads.
- `start()` asks the scheduler to run the task on another thread. Calling `run()` yourself runs it inline, on the current thread, with no concurrency at all.
- `synchronized` locks the object's monitor, so only one thread at a time is inside the method. `synchronized (lock) { ... }` locks an object you choose, which is better when several fields must change together.
- `volatile` guarantees a thread sees the latest value, but it does **not** make `count++` atomic - that is still read, add, store. Use `AtomicInteger` or `synchronized`.

## Example
```java
class Counter {
    private int count = 0;
    synchronized void increment() { count++; }
    int value() { return count; }
}
```

## Knowledge checks
Q: What is the difference between `run()` and `start()`?
A: `start()` hands the task to a new thread; `run()` executes it immediately on the calling thread, so nothing is concurrent.
Q: Why is implementing `Runnable` usually better than extending `Thread`?
A: A class can do both, and one `Runnable` can be shared by several threads.
Q: Why can two threads lose an increment?
A: `count++` is three separate operations, and the threads can interleave between them.
Q: What does `volatile` guarantee?
A: That a thread always reads the current value rather than a cached one. It does not make compound operations atomic.
Q: What is the difference between a `BLOCKED` and a `WAITING` thread?
A: `BLOCKED` means waiting for a monitor to be released; `WAITING` means waiting for something else to happen, such as `sleep`, `join` or `wait`.

## Exercise
Write a `Counter` class with a `synchronized` increment method and a plain one. Start four threads that each increment it a thousand times - once using the synchronized version, once not - and print the final count in both cases. Explain the difference in the two results.

```java starter
public class Main {
    // Define Counter with a synchronized and an unsynchronized increment.

    public static void main(String[] args) {
        // Run both versions and print the final counts
    }
}
```

## Common mistakes
- Synchronizing on a `String` literal or a boxed `Integer` - the value is shared across the whole program, so unrelated code can lock the same object.
- Assuming `volatile` makes a counter safe.
- Holding a lock while doing slow work.

## Recap
- `Runnable` plus `start()` is the way to run work on another thread.
- `synchronized` protects shared state; `volatile` only guarantees visibility.
