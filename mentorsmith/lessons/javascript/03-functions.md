---
id: 03-functions
title: Functions
order: 3
---

## Objectives
- Declare functions with `function`, `const` and arrow syntax.
- Pass arguments, default parameters and rest parameters.
- Return values, including early returns.
- Understand that JavaScript passes objects by reference and primitives by value.

## Explanation
Three equivalent ways to write a function:

```javascript
function add(a, b) { return a + b; }

const add = function (a, b) { return a + b; };

const add = (a, b) => a + b;
```

**Arrow functions** have two differences that matter, and both come from not
having their own `this`:

1. **They cannot be called as constructors.** `new (() => {})` throws.
2. **They inherit `this` from where they are defined**, which makes them the
   right choice for callbacks and the wrong choice for object methods that need
   their own `this`.

**Parameters.** Defaults, destructuring and rest all work:

```javascript
function greet(name = "there") { return `Hello, ${name}`; }
greet();             // "Hello, there"

function total(...values) { return values.reduce((s, v) => s + v, 0); }
total(1, 2, 3);      // 6

const { first, last } = person;          // destructure an object
const [x, y] = [10, 20];                 // destructure an array
```

**Objects are passed by reference, primitives by value.** Passing a primitive
gives the callee a copy; passing an object lets the callee mutate what the caller
holds:

```javascript
function tryToChange(n) { n = 99; }        // no effect on the caller
function tryToMutate(o) { o.count = 99; }  // DOES change the caller's object

let number = 5;
tryToChange(number);
console.log(number);        // 5

const settings = { count: 1 };
tryToMutate(settings);
console.log(settings.count);  // 99
```

This is the same distinction Python draws between rebinding and mutating, and
it is *not* the same as C++'s by-value/by-reference, because there is no way to
pass an object by value cheaply and no address-of syntax.

**Returning objects** is idiomatic, and literal shorthand saves typing:

```javascript
function makePoint(x, y) {
  return { x, y };            // same as { x: x, y: y }
}
```

**Arrow functions and `return`.** A concise body returns implicitly; a block
body does not:

```javascript
const a = x => x * 2;                 // returns 4 for x=2
const b = x => { x * 2 };             // returns undefined
```

Forgetting this is a common and silent bug.

## Example
```javascript
// functions.mjs
function greet(name = "there") {
  return `Hello, ${name}`;
}

const square = (x) => x * x;
const cube = (x) => x * x * x;

function sumAll(...values) {
  return values.reduce((total, value) => total + value, 0);
}

function makePoint(x, y) {
  return { x, y };               // shorthand for { x: x, y: y }
}

function describe({ name, age }) {  // destructured parameter
  return `${name} is ${age}`;
}

function tryToChange(n) {
  n = 99;                          // rebinds a copy
}

function tryToMutate(options) {
  options.enabled = false;         // mutates the caller's object
}

console.log(greet(), "|", greet("Ada"));
console.log(square(4), cube(3));
console.log("sum:", sumAll(1, 2, 3));

const point = makePoint(3, 4);
console.log("point:", point);

console.log(describe({ name: "Ada", age: 36 }));

let number = 5;
tryToChange(number);
console.log("number unchanged:", number);          // 5

const settings = { enabled: true, retries: 3 };
tryToMutate(settings);
console.log("settings mutated:", settings);        // enabled: false

// The implicit-return trap
const implicit = (x) => x * 2;
const explicit = (x) => { x * 2; };
console.log("implicit return:", implicit(2));      // 4
console.log("explicit return:", explicit(2));      // undefined
```

## Knowledge checks
Q: When can you not use an arrow function?
A: As a constructor with `new`, and as an object method that needs its own `this`, because arrows inherit `this` from their definition site.
Q: How are objects passed compared to primitives?
A: Objects are passed by reference, so the callee can mutate what the caller holds. Primitives are passed by value, giving the callee a copy.
Q: Why does `(x) => { x * 2 }` return `undefined`?
A: A concise arrow body returns implicitly, but a block body needs an explicit `return`.
Q: What does a default parameter do when the argument is `undefined`?
A: It substitutes the default. Note that passing `null` explicitly does *not* trigger the default.

## Exercise
Write `add(a, b = 0)`, `sumAll(...values)` using `reduce`, and
`makePerson(name, age)` returning an object. Then call each and print the
results.

```javascript starter
function add(a, b = 0) {
  // return a + b
}

function sumAll(...values) {
  // reduce to a total, starting from 0
}

function makePerson(name, age) {
  // return an object with those properties
}
```

## Common mistakes
- **Forgetting `return` inside a block-bodied arrow function.**
- **Using an arrow function as a constructor,** which throws.
- **Expecting a primitive parameter change to be visible,** which it is not.
- **Using `arguments` in an arrow function,** where it refers to the enclosing scope.
- **Declaring `const add` and also `function add`,** which is a redeclaration error.

## Recap
- Three declaration forms; arrows have no `this` of their own.
- Defaults, rest and destructuring all work in parameters.
- Objects pass by reference, primitives by value.
- Concise arrows return implicitly; block bodies need `return`.
- `{ x, y }` is shorthand for `{ x: x, y: y }`.