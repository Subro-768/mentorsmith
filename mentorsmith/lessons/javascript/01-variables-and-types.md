---
id: 01-variables-and-types
title: Variables and Types
order: 1
---

## Objectives
- Declare variables with `const` and `let` and know when each is right.
- Use the primitives: `number`, `string`, `boolean`, `null`, `undefined`.
- Understand that JavaScript is dynamically typed.
- Avoid the number-versus-string coercion trap.

## Explanation
Prefer `const` by default and use `let` only when you must reassign:

```javascript
const name = "Ada";   // binding cannot be changed
let count = 0;        // binding can be reassigned
count += 1;
```

`var` is legacy. It is function-scoped rather than block-scoped, which causes
bugs that `let` and `const` do not have. Do not use it in new code.

**Primitives:**

| Type | Example | Notes |
|---|---|---|
| `number` | `42`, `3.14` | One type for integers and floats |
| `string` | `"Ada"` | Immutable |
| `boolean` | `true` | |
| `null` | `null` | Deliberately "no value" |
| `undefined` | — | Assigned by the engine when a value is missing |

There is no separate `int` and `double`, so `5 / 2` is `2.5` — matching Python
rather than C and C++.

**`typeof` and falsy values.** `typeof 42` is `"number"`. But `typeof null` is
`"object"`, a long-standing bug in the language that you simply have to know.

**Falsy values** are treated as false in a condition:

```javascript
false, 0, -0, 0n, "", null, undefined, NaN
```

Everything else is truthy — including `"0"`, `"false"` and `[]`. That last one
surprises people: an empty array is truthy.

**The coercion trap.** JavaScript converts types as needed:

```javascript
"5" + 3      // "53"   string concatenation wins
"5" - 3      // 2      arithmetic converts
"5" == 5     // true   loose equality coerces
"5" === 5    // false  strict equality does not
```

Always use `===` and `!==`. `==` applies coercion rules that were designed for
an era before `===` existed, and they produce surprises rather than conveniences.

**Check for missing values with `== null`:**

```javascript
if (value === null || value === undefined) { ... }
```

That is the one place `==` is correct and idiomatic, because it matches both
`null` and `undefined` in a single readable test.

## Example
```javascript
// variables_and_types.mjs
const name = "Ada";
let count = 0;

count += 1;
console.log(name, typeof name);
console.log(count, typeof count);

// One number type: no integer division
console.log(7 / 2);            // 3.5
console.log(7 % 2);            // 1
console.log(7 / 0);            // Infinity
console.log(typeof null);      // "object" - a famous language bug

// Falsy values
console.log(Boolean(0), Boolean(""), Boolean([]), Boolean("false"));
// false false true true

// Coercion traps
console.log("5" + 3);          // "53"
console.log("5" - 3);          // 2
console.log("5" == 5);         // true  - avoid
console.log("5" === 5);        // false - correct

// The idiomatic missing-value check
function describe(value) {
  if (value == null) return "missing";   // matches null and undefined
  return `present: ${value}`;
}
console.log(describe(null));      // missing
console.log(describe(undefined)); // missing
console.log(describe(0));         // present: 0
```

## Knowledge checks
Q: When should you use `let` instead of `const`?
A: Only when the binding genuinely needs to be reassigned. `const` prevents accidental reassignment and documents intent.
Q: What does `typeof null` return, and why is it surprising?
A: `"object"`. It is a long-standing bug in the language that cannot be changed without breaking existing code, so you simply need to know it.
Q: Is an empty array `[]` truthy?
A: Yes. All objects and arrays are truthy, even when empty. Use `array.length` to test for emptiness.
Q: Why prefer `===` over `==`?
A: `==` applies type coercion, so `"5" == 5` is true. `===` compares both value and type, which is almost always what you mean.

## Exercise
Create a `const` for a product name, a `let` for a quantity that starts at 1, a
`number` price, a `boolean` inStock, and a `null` discount. Print each value
with `typeof`, then increment the quantity and print the new stock message using
a template literal.

```javascript starter
const product = "Notebook";
let quantity = 1;
const price = 4.5;
const inStock = true;
let discount = null;

// Print each value with typeof. Then quantity += 2 and print a sentence.
```

## Common mistakes
- **Using `var`.** It is function-scoped and causes closure bugs. Use `const`/`let`.
- **Using `==`.** Coercion produces surprising results; use `===`.
- **Expecting integer division.** `7 / 2` is `3.5`.
- **Treating an empty array or an empty string as falsy.** Only `""` is falsy; `[]` is truthy.
- **Using `typeof x === "object"` to detect `null`.** Test `x === null` instead.

## Recap
- `const` by default, `let` when reassigning, never `var`.
- Primitives: `number`, `string`, `boolean`, `null`, `undefined`.
- One `number` type, so `/` is true division.
- Always `===` and `!==`; use `== null` for the missing-value check.
- Empty arrays are truthy.