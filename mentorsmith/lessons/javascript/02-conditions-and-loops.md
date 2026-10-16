---
id: 02-conditions-and-loops
title: Conditions and Loops
order: 2
---

## Objectives
- Write `if`, `else` and `switch`.
- Use `for`, `for...of` and `while` correctly.
- Choose `for...of` over `for...in` for arrays.
- Avoid the classic loop-closure bug.

## Explanation
Conditions read much like C++:

```javascript
if (score >= 90) {
  grade = "A";
} else if (score >= 80) {
  grade = "B";
} else {
  grade = "F";
}
```

**Loops.** `for...of` iterates over the *values* of an iterable, which is what
you almost always want:

```javascript
for (const mark of marks) {
  console.log(mark);
}

for (const [index, value] of marks.entries()) {
  console.log(index, value);
}
```

`for...in` iterates over *keys*, and is a bug magnet on arrays because it also
walks inherited enumerable properties. Use `Object.keys()` or `Object.entries()`
for objects:

```javascript
for (const key of Object.keys(person)) {
  console.log(key, person[key]);
}
```

Classic loops:

```javascript
for (let i = 0; i < 5; i++) { ... }

let n = 3;
while (n > 0) { n--; }

do { ... } while (condition);      // runs at least once
```

**`for...in` is wrong for arrays:**

```javascript
for (const i in [10, 20]) { ... }   // i is "0", "1" - strings!
```

**The closure-in-loop bug.** `let` in a `for` head gives each iteration its own
binding; `var` does not:

```javascript
const fns = [];
for (let i = 0; i < 3; i++) fns.push(() => i);
console.log(fns.map(f => f()));    // [0, 1, 2] - correct

const bad = [];
for (var j = 0; j < 3; j++) bad.push(() => j);
console.log(bad.map(f => f()));    // [3, 3, 3] - classic bug
```

This is a real reason to prefer `let` over `var`.

`break` and `continue` work as expected, and you can label loops:

```javascript
outer:
for (let i = 0; i < 3; i++) {
  for (let j = 0; j < 3; j++) {
    if (i * j > 4) break outer;
  }
}
```

## Example
```javascript
// conditions_and_loops.mjs
const marks = [70, 85, 92, 60, 78];

function gradeFor(mark) {
  if (mark >= 90) return "A";
  if (mark >= 80) return "B";
  if (mark >= 70) return "C";
  return "F";
}

for (const mark of marks) {
  console.log(mark, gradeFor(mark));
}

const total = marks.reduce((sum, mark) => sum + mark, 0);
console.log("total:", total, "average:", total / marks.length);

// for...of with the index
for (const [index, mark] of marks.entries()) {
  console.log(`${index}: ${mark}`);
}

// for...in is wrong for arrays - it yields keys as strings
for (const key in marks) {
  console.log("key:", key, typeof key);   // "0", "1" ... as strings
}
for (const value of marks) {
  console.log("value:", value, typeof value);  // numbers
}

// while with a countdown
let countdown = 3;
while (countdown > 0) {
  console.log("countdown", countdown);
  countdown--;
}

// let gives each iteration its own closure binding
const fns = [];
for (let i = 0; i < 3; i++) fns.push(() => i);
console.log("closures:", fns.map(f => f()));   // [0, 1, 2]

// break and continue
for (const value of [1, 2, 3, 4, 5]) {
  if (value === 3) continue;
  if (value === 5) break;
  console.log("kept", value);
}

// switch on a primitive
const choice = 2;
switch (choice) {
  case 1:
    console.log("new game");
    break;
  case 2:
    console.log("load game");
    break;
  default:
    console.log("invalid");
}
```

## Knowledge checks
Q: When should you use `for...of` rather than `for...in`?
A: `for...of` iterates over values and works on any iterable. `for...in` iterates over keys and also walks inherited properties, which makes it a bug magnet for arrays.
Q: What does the loop-closure bug look like?
A: With `var` in the `for` head, every captured closure sees the final value — `[3, 3, 3]` instead of `[0, 1, 2]`. Using `let` gives each iteration its own binding.
Q: When does `do...while` run its body?
A: At least once, because the condition is tested after the body.
Q: What does `break` do inside `switch`?
A: It exits the `switch`. Without it, execution falls through to the next case.

## Exercise
Print the even numbers from 1 to 10 with a `for` loop. Then use `for...of` to
print each mark in an array in reverse using `entries()`, and use a `while` loop
to count down from 5.

```javascript starter
const marks = [70, 85, 92, 60];

// Part 1: for loop printing 2, 4, 6, 8, 10.
// Part 2: for...of with entries() printing marks in reverse index order.
// Part 3: while loop counting down from 5 to 1.
```

## Common mistakes
- **`for...in` over an array,** yielding string indices and inherited properties.
- **Using `var` in a loop and capturing it in a closure.**
- **Writing `i = 0` in the `for` header,** which assigns instead of declaring.
- **Assuming `continue` runs the update expression.** It jumps to the update, but skipping it can loop forever.
- **Forgetting that `===` compares types** when checking loop counters from `parseInt`.

## Recap
- `for...of` for values, `for...in` only for keys of an object.
- `let` in the `for` head fixes the closure bug; `var` does not.
- `while` for unknown counts, `for` for known, `do...while` for at-least-once.
- `break` and `continue` behave as in C++, and loops can be labelled.
- `switch` needs `break`.