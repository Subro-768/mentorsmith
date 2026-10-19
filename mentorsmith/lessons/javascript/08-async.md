---
id: 08-async
title: Asynchronous Fundamentals
order: 8
tier: advanced
---

## Objectives
- Explain the event loop and why synchronous code blocks everything.
- Use promises with `async`/`await`.
- Handle rejection properly.
- Know when a promise-based API is the wrong tool.

## Explanation
JavaScript runs on one thread. Code that waits blocks the only thread there is,
so the interface freezes.

```javascript
console.log("one");
console.log("two");
```

That is predictable because there is no waiting involved. Add a wait and the
ordering becomes non-obvious:

```javascript
console.log("A");
setTimeout(() => console.log("B"), 0);   // runs last
Promise.resolve().then(() => console.log("C"));
console.log("D");
// A, D, C, B
```

The explanation is the **event loop**: synchronous code runs to completion
first, then queued microtasks (promise callbacks), then queued macrotasks
(`setTimeout`). `await` is sugar that lets you write asynchronous code in
reading order without callbacks:

```javascript
async function load() {
  const first = await fetchValue();     // pauses here, not the thread
  const second = await fetchOther();    // starts only when the first resolves
  return first + second;
}
```

**Promises** have three states: pending, fulfilled and rejected. A promise that
settles never changes again.

```javascript
const promise = new Promise((resolve, reject) => {
  setTimeout(() => resolve("done"), 100);
});
```

In practice you rarely construct one; you consume them.

**Error handling must include rejection.** A `try`/`catch` around an `await`
does catch a rejection — but a `catch` around a promise you never awaited does
not run, and the rejection becomes an unhandled rejection:

```javascript
// BAD: the catch never runs
try {
  doAsync();               // returns a rejected promise, not awaited
} catch { }

// GOOD
try {
  await doAsync();
} catch (error) { }
```

**Run independent work in parallel.** Awaiting inside a loop serialises it:

```javascript
const sequential = [];
for (const id of ids) sequential.push(await load(id));   // one after another

const parallel = await Promise.all(ids.map(id => load(id)));   // concurrently
```

**`Promise.all` fails fast**: if one rejects, the whole thing rejects.
`Promise.allSettled` waits for everything and reports each outcome, which is
usually what you want when each operation is independent.

**`AbortController`** cancels work that is no longer needed:

```javascript
const controller = new AbortController();
const promise = doWork({ signal: controller.signal });
controller.abort();
```

**Never block the event loop.** A `while (true) {}` loop freezes the page and,
in Node, stops everything including the timers that would have stopped it.
MentorSmith runs untrusted code in a separate process with a timeout for exactly
this reason.

## Example
```javascript
// async.mjs
function delay(value, ms) {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

function maybeFail(shouldFail) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (shouldFail) reject(new Error("the operation failed"));
      else resolve("succeeded");
    }, 10);
  });
}

async function sequential() {
  const started = Date.now();
  const a = await delay("a", 50);
  const b = await delay("b", 50);
  return `${a}${b} in about 100ms (took ${Date.now() - started}ms)`;
}

async function parallel() {
  const started = Date.now();
  const [a, b] = await Promise.all([delay("a", 50), delay("b", 50)]);
  return `${a}${b} in about 50ms (took ${Date.now() - started}ms)`;
}

async function safeAll() {
  const results = await Promise.allSettled([
    maybeFail(false),
    maybeFail(true),
  ]);
  return results.map((r) =>
    r.status === "fulfilled" ? `ok: ${r.value}` : `failed: ${r.reason.message}`
  );
}

// Ordering explained
console.log("1 sync");
setTimeout(() => console.log("5 timeout"), 0);
Promise.resolve().then(() => console.log("4 microtask"));
console.log("2 sync");

async function main() {
  console.log(await sequential());
  console.log(await parallel());
  console.log(await safeAll());

  // awaiting inside try/catch does catch a rejection
  try {
    await maybeFail(true);
  } catch (error) {
    console.log("caught:", error.message);
  }

  // a cancellation
  const controller = new AbortController();
  controller.abort();
  console.log("aborted:", controller.signal.aborted);
}

await main();
console.log("done");
```

## Knowledge checks
Q: In what order do the event loop stages run for this code: a synchronous log, `setTimeout(0)`, and a resolved promise?
A: Synchronous first, then promise microtasks, then `setTimeout` callbacks last.
Q: Why does `Promise.allSettled` differ from `Promise.all`?
A: `Promise.all` rejects as soon as any promise rejects. `allSettled` waits for every promise and reports each result or reason, which suits independent operations.
Q: Why must you `await` a promise for `try`/`catch` to catch its rejection?
A: The `catch` runs on synchronous throw and on rejection of an awaited promise. A rejection on a promise you never await escapes as an unhandled rejection.
Q: Why is an infinite loop especially damaging in JavaScript?
A: The single thread runs the loop forever, so nothing else happens — including the timer that might have interrupted it. Blocking work belongs in a worker or a separate process.

## Exercise
Write `wait(ms)` returning a promise that resolves after `ms`. Then write
`fetchAll()` that awaits three `wait` calls sequentially and reports the total
time, and `fetchAllFast()` that runs them concurrently with `Promise.all` and
reports the total time. The fast version should take roughly a third as long.

```javascript starter
function wait(ms) {
  // new Promise + setTimeout
}

async function fetchAll() {
  // three sequential awaits, then return elapsed ms
}

async function fetchAllFast() {
  // Promise.all over the three waits
}
```

## Common mistakes
- **Using `await` inside a loop** and needlessly serialising independent work.
- **Forgetting to `await`,** so the `catch` never runs.
- **Using `Promise.all`** when a single failure should not cancel the rest.
- **Blocking the event loop** with a tight loop or a synchronous heavy computation.
- **Assuming `await` makes code parallel.** It makes code readable; the work still runs concurrently only when started together.

## Recap
- The event loop runs sync code, then microtasks, then timers.
- `await` pauses one async function, not the whole thread.
- `try`/`catch` catches a rejection only for an awaited promise.
- `Promise.all` is concurrent but fails fast; `allSettled` waits for all.
- Never block the event loop; heavy or untrusted work belongs elsewhere.