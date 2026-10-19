---
id: 05-scope
title: Scope and Closures
order: 5
tier: core
---

## Objectives
- Distinguish global, module, function and block scope.
- Explain the temporal dead zone.
- Create and use a closure.
- Understand why `let` in a loop fixes the classic closure bug.

## Explanation
Scope decides where a name is visible.

```javascript
const global = "anywhere";

function example() {
  const inFunction = "inside only";
  if (true) {
    let inBlock = "inside the block only";
  }
  // inBlock is not visible here
}
```

`let` and `const` are **block-scoped**: they exist only within the braces that
contain them. `var` is function-scoped, so it leaks out of blocks and loops.
That difference is the main practical reason to stop using `var`.

**Hoisting.** Declarations are processed before the code runs, but the effect
differs:

```javascript
console.log(x);       // undefined, not an error
var x = 1;

console.log(y);       // ReferenceError!
let y = 2;
```

`var` is hoisted and initialised to `undefined`. `let` and `const` are hoisted
into the *temporal dead zone* — they exist but cannot be touched until the
declaration executes. That is why `let` fails loudly where `var` fails quietly.

**Closures.** A function keeps access to the variables in the scope where it was
defined, even after that scope has exited:

```javascript
function makeCounter() {
  let count = 0;              // private to this closure
  return function increment() {
    count += 1;
    return count;
  };
}

const counter = makeCounter();
console.log(counter());   // 1
console.log(counter());   // 2

const other = makeCounter();
console.log(other());     // 1 - a separate private count
```

Each call to `makeCounter` creates a fresh `count`. That is how you get private
state without classes.

**The loop-closure bug** is the same idea gone wrong:

```javascript
const bad = [];
for (var i = 0; i < 3; i++) bad.push(() => i);
console.log(bad.map(f => f()));    // [3, 3, 3]

const good = [];
for (let j = 0; j < 3; j++) good.push(() => j);
console.log(good.map(f => f()));   // [0, 1, 2]
```

All three closures share one `var`. With `let`, each iteration gets its own
binding, so each closure remembers its own number.

**Arrow functions inherit `this`**, which is why they are convenient as
callbacks but wrong as object methods:

```javascript
const timer = {
  seconds: 0,
  startBad() {
    setTimeout(function () { console.log(this.seconds); }, 100);  // undefined `this`
  },
  startGood() {
    setTimeout(() => console.log(this.seconds), 100);              // arrow inherits it
  }
};
```

## Example
```javascript
// scope.mjs
const global = "visible everywhere";

function blockScopeDemo() {
  const inFunction = "function scope";
  if (true) {
    let inBlock = "block scope";
    console.log("inside block:", inBlock);
  }
  // console.log(inBlock);   // ReferenceError if uncommented
  return inFunction;
}

console.log(blockScopeDemo());

// Temporal dead zone
console.log("var hoisting  :", typeof maybeLater);   // "undefined"
var maybeLater = 1;
// console.log(maybeLater);  // would throw if it were let

// Closures give private state
function makeCounter(start = 0) {
  let count = start;
  return {
    increment() { count += 1; return count; },
    get value() { return count; },
  };
}

const counter = makeCounter(10);
console.log(counter.increment(), counter.increment(), counter.value);

const separate = makeCounter();
console.log("independent:", separate.value);   // 0, not 20

// The loop-closure bug
const withVar = [];
for (var i = 0; i < 3; i++) withVar.push(() => i);
console.log("with var:", withVar.map(f => f()));    // [3, 3, 3]

const withLet = [];
for (let j = 0; j < 3; j++) withLet.push(() => j);
console.log("with let:", withLet.map(f => f()));   // [0, 1, 2]

// Closures over a loop variable declared with let in a for-of
const names = ["Ada", "Alan", "Grace"];
const greeters = [];
for (const name of names) {
  greeters.push(() => `Hello, ${name}`);
}
console.log(greeters.map(g => g()));   // each has its own name

// this: arrow functions inherit it
const timer = {
  label: "mine",
  withFunction() {
    return (function () { return this; })();     // undefined in strict mode
  },
  withArrow() {
    return (() => this)();                      // the timer object
  },
};
console.log("function this:", timer.withFunction());
console.log("arrow this   :", timer.withArrow().label);
```

## Knowledge checks
Q: What is the difference in scope between `var` and `let`?
A: `var` is function-scoped and leaks out of blocks and loops. `let` is block-scoped and exists only inside its braces.
Q: What is the temporal dead zone?
A: The span between when a `let` or `const` is hoisted and when its declaration executes. Touching the name in that span throws a `ReferenceError`.
Q: Why does `var` in a loop give `[3, 3, 3]`?
A: All closures share the single function-scoped `var`, so each sees its final value. `let` creates a fresh binding per iteration.
Q: Why prefer arrow functions as callbacks?
A: They inherit `this` from the surrounding scope instead of receiving their own, which is usually what a callback wants.

## Exercise
Write `makeCounter(start)` returning an object with `increment`, `decrement` and
a `value` getter, all closing over a private `count`. Create two counters and
prove they do not share state.

```javascript starter
function makeCounter(start = 0) {
  let count = start;
  return {
    increment() { /* count += 1; return count */ },
    decrement() { /* count -= 1; return count */ },
    get value() { /* return count */ },
  };
}

const a = makeCounter(5);
const b = makeCounter();
// Prove a and b are independent.
```

## Common mistakes
- **Using `var`**, which leaks out of blocks and breaks loop closures.
- **Reading a `let` before its declaration,** which throws rather than returning `undefined`.
- **Expecting a closure to see the final loop value** when written with `var`.
- **Using a `function` as a callback where `this` matters.**
- **Expecting a closure over a loop variable in a `for...of` to share state.** It does not.

## Recap
- `let` and `const` are block-scoped; `var` is function-scoped.
- `var` hoists to `undefined`; `let`/`const` sit in a temporal dead zone.
- A closure remembers the scope where it was defined, not the current values.
- Closures over `let` loop variables capture each iteration's value.
- Arrow functions inherit `this`; regular functions do not.