---
id: 04-arrays-and-objects
title: Arrays and Objects
order: 4
---

## Objectives
- Read and write array elements, and use the common array methods.
- Create and read object properties safely.
- Choose between an array, a plain object and a `Map`.
- Avoid mutating arrays in ways that surprise the reader.

## Explanation
**Arrays** hold ordered values:

```javascript
const marks = [70, 85, 92];
marks[0];              // 70
marks.length;          // 3
marks.push(60);        // append, returns new length
marks.pop();           // remove and return the last
```

The methods that do most of the work:

| Method | Does |
|---|---|
| `map(fn)` | New array, same length, transformed |
| `filter(fn)` | New array of items where `fn` is true |
| `reduce(fn, start)` | Collapse to a single value |
| `find(fn)` | First matching item, or `undefined` |
| `some(fn)` / `every(fn)` | Any match / all match |
| `sort(cmp)` | Sort **in place** and return the same array |
| `slice(a, b)` | Copy a range, end exclusive |
| `includes(v)` | Membership test |

```javascript
const doubled = marks.map(m => m * 2);         // [140, 170, 184]
const passing = marks.filter(m => m >= 80);    // [85, 92]
const total = marks.reduce((s, m) => s + m, 0);
const first = marks.find(m => m > 80);         // 85
const sorted = [...marks].sort((a, b) => a - b);
```

**`sort` mutates and needs a comparator.** `marks.sort()` sorts *strings* —
`[10, 9, 100].sort()` gives `[10, 100, 9]`. Always pass `(a, b) => a - b`.

**Spread avoids mutating**: `[...marks].sort(...)` sorts a copy.

**Objects** map keys to values:

```javascript
const person = { name: "Ada", age: 36 };
person.name;                  // "Ada"
person["age"];                // 36
person.city = "London";       // add
const missing = person.nickname;      // undefined, no error
person.nickname ??= "unknown";        // set if null/undefined
```

Use `Object.keys`, `Object.values` and `Object.entries` to iterate:

```javascript
for (const [key, value] of Object.entries(person)) {
  console.log(key, value);
}
```

`??` (nullish coalescing) substitutes only for `null` and `undefined`, unlike
`||` which also substitutes for `0`, `""` and `false`. That distinction matters:

```javascript
0 || "fallback"     // "fallback"  - probably not what you wanted
0 ?? "fallback"     // 0           - correct
```

**Destructuring** reads cleanly:

```javascript
const { name, age } = person;
const [first, ...rest] = marks;
```

**`Map` versus object.** Use a `Map` when keys are not strings, when you want
insertion order guaranteed, or when you need to delete frequently. `Map` keys
can be any value:

```javascript
const counts = new Map();
counts.set("Ada", 1);
counts.get("Ada");     // 1
counts.size;           // 1
```

Objects coerce keys to strings, so `{1: "a"}` and `{"1": "b"}` collide.

## Example
```javascript
// arrays_and_objects.mjs
const marks = [70, 85, 92, 60, 78];

console.log("length:", marks.length);
console.log("first:", marks[0], "last:", marks[marks.length - 1]);

console.log("doubled :", marks.map(m => m * 2));
console.log("passing :", marks.filter(m => m >= 80));
console.log("total   :", marks.reduce((s, m) => s + m, 0));
console.log("average :", marks.reduce((s, m) => s + m, 0) / marks.length);
console.log("first>80:", marks.find(m => m > 80));
console.log("any>90  :", marks.some(m => m > 90));
console.log("all>60  :", marks.every(m => m > 60));

// sort mutates: use a copy
const unsorted = [10, 9, 100];
console.log("bad sort :", [...unsorted].sort());                 // 10,100,9
console.log("good sort:", [...unsorted].sort((a, b) => a - b)); // 9,10,100
console.log("original :", unsorted, "(unchanged)");

// slice copies, end exclusive
console.log("slice 1:3:", marks.slice(1, 3));
console.log("includes 92:", marks.includes(92));

const person = { name: "Ada", age: 36 };
person.city = "London";
console.log("person   :", person);
console.log("missing  :", person.nickname);        // undefined

// ?? vs ||
const zero = 0;
console.log("0 || 'x' :", zero || "x");
console.log("0 ?? 'x' :", zero ?? "x");

// destructuring
const { name, age } = person;
const [first, ...rest] = marks;
console.log("destruct :", name, age, first, rest);

// entries
for (const [key, value] of Object.entries(person)) {
  console.log(`  ${key} = ${value}`);
}

// Map with non-string keys
const counts = new Map();
for (const mark of marks) {
  const band = mark >= 80 ? "high" : "low";
  counts.set(band, (counts.get(band) ?? 0) + 1);
}
console.log("map counts:", [...counts.entries()]);
```

## Knowledge checks
Q: What does `[10, 9, 100].sort()` produce, and why?
A: `[10, 100, 9]`. With no comparator, elements are compared as strings, and `"10"` sorts before `"9"`.
Q: When should you use `??` instead of `||`?
A: When you want to substitute only for `null` and `undefined`. `||` also substitutes for `0`, `""` and `false`.
Q: Does reading a property that does not exist throw?
A: No. It returns `undefined`.
Q: When is a `Map` better than a plain object?
A: When keys are not strings, when you need guaranteed insertion order, or when you delete frequently.

## Exercise
Build an array of five marks. Print the array, its length, the doubled values,
the values at least 80, the total and the mean. Then build an object counting
how many marks fall into each of two bands, and print it.

```javascript starter
const marks = [70, 85, 92, 60, 78];

// Print length, marks.map(m => m*2), marks.filter(m => m >= 80).
// Print the reduced total and the mean.
// Build an object of band -> count for "high" (>=80) and "low", then print it.
```

## Common mistakes
- **`sort()` with no comparator,** sorting lexicographically.
- **Forgetting that `sort` mutates** and modifying an array someone else holds.
- **Using `||` to default,** which replaces valid `0` and `""` values.
- **Iterating an object with `for...in`** when `Object.entries()` is clearer.
- **Using an array as a map** with non-numeric keys.

## Recap
- `map`, `filter`, `reduce`, `find`, `some`, `every` return new values.
- `sort` mutates and needs `(a, b) => a - b`.
- `slice` copies and excludes the end index.
- `??` replaces only `null`/`undefined`; `||` replaces all falsy values.
- Use a `Map` when keys are not strings.