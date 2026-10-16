---
id: 07-modules
title: Modules
order: 7
---

## Objectives
- Export and import named and default bindings.
- Choose the `.mjs` extension or `type: module` for ES modules.
- Avoid circular imports.
- Understand what importing a module actually does.

## Explanation
An ES module is a file whose exports are explicitly declared:

```javascript
// geometry.mjs
export const PI = 3.14159;

export function area(radius) {
  return PI * radius * radius;
}

export default class Shape { }
```

```javascript
// main.mjs
import { area, PI } from "./geometry.mjs";
import Shape from "./geometry.mjs";
import * as geometry from "./geometry.mjs";

console.log(area(2), PI, new Shape() instanceof Shape, geometry.area(3));
```

Three styles:

- **Named exports** — `{ area, PI }`. Explicit, and refactoring-safe.
- **Default export** — `import Shape from ...`. One per file, and the name can
  be anything at the import site, so it is easy to misread.
- **Namespace import** — `import * as geometry`. Useful for exploring.

**Prefer named exports.** A default export hides where a value came from, and a
wrong name fails late:

```javascript
import { area as circleArea } from "./geometry.mjs";   // rename on import
```

**Importing runs the module once.** Its top-level code executes the first time
anything imports it, then the module is cached. This is why modules are a good
place for constants and a bad place for side effects.

**File extensions are required in ES modules** for relative paths:

```javascript
import { area } from "./geometry.mjs";   // correct - extension included
import { area } from "./geometry";        // error in ES modules
```

This differs from CommonJS.

**Getting ES modules working.** Use the `.mjs` extension, or add
`"type": "module"` to `package.json`. Without one of those, Node treats `.js`
as CommonJS and `import` fails.

```bash
node main.mjs
```

**Dynamic import** loads a module at runtime and returns a promise — which is
how you conditionally load code:

```javascript
const { area } = await import("./geometry.mjs");
```

**Circular imports** (`a` imports `b`, `b` imports `a`) are fragile: the module
that is entered second may see unfinished bindings, producing `undefined` where
you expected a value. Break the cycle by extracting shared code into a third
module that both depend on, or by using dynamic `import()` inside the function
that needs it.

**Node built-ins** need the `node:` prefix so they are clearly distinguished
from your own files:

```javascript
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
```

## Example
```javascript
// geometry.mjs
export const PI = 3.14159;

export function area(radius) {
  if (radius < 0) throw new RangeError("radius cannot be negative");
  return PI * radius * radius;
}

export function circumference(radius) {
  return 2 * PI * radius;
}

export default function describeShape(name) {
  return `a ${name}`;
}
```

```javascript
// main.mjs
import Shape from "./geometry.mjs";
import { area, circumference, PI } from "./geometry.mjs";
import * as geometry from "./geometry.mjs";

console.log("named     :", area(2));
console.log("circumf.  :", circumference(2));
console.log("PI        :", PI);
console.log("namespace :", geometry.area(3));
console.log("default   :", Shape("circle"));

// renaming on import keeps the source name visible at the call site
import { area as circleArea } from "./geometry.mjs";
console.log("renamed   :", circleArea(1));

// a module runs once, then is cached
import { PI as cachedPI } from "./geometry.mjs";
console.log("cached    :", cachedPI === PI);

// dynamic import happens at runtime
const late = await import("./geometry.mjs");
console.log("dynamic   :", late.area(4));

try {
  area(-1);
} catch (error) {
  console.log("rejected  :", error.name, "-", error.message);
}
```

Run it:

```bash
node main.mjs
```

## Knowledge checks
Q: Why do ES modules require the file extension on relative imports?
A: The resolution rule is explicit and unambiguous, unlike CommonJS. It also means a `.js` file cannot be silently picked up when you meant `.mjs`.
Q: What happens when a module is imported twice?
A: Its top-level code runs once. The second import uses the cached, already-initialised module.
Q: Why prefer named exports over a default export?
A: Named exports say where a value came from, survive refactoring, and a wrong name fails immediately rather than resolving to `undefined`.
Q: What breaks with circular imports?
A: The second module entered may see unfinished bindings and get `undefined` where a value was expected.

## Exercise
Create `shapes.mjs` exporting `PI`, `circleArea(r)` and `default`
`describeShape(name)`. Then create `main.mjs` that imports all three, calls
each, and also imports the module as a namespace.

```javascript starter
// shapes.mjs
export const PI = 3.14159;
export function circleArea(r) {
  return PI * r * r;
}
export default function describeShape(name) {
  return `a ${name}`;
}
```

## Common mistakes
- **Forgetting `"type": "module"` or the `.mjs` extension,** so `import` fails.
- **Omitting the extension on a relative path.**
- **Using a default export and expecting the importing name to matter.**
- **Circular imports** producing `undefined`.
- **Using CommonJS `require`/`module.exports`** in a file that uses `import`.

## Recap
- Named exports are explicit; default exports are convenient but vague.
- Use `.mjs` or `"type": "module"`.
- Relative imports need the full extension.
- A module body runs once, then is cached.
- Break cycles by extracting shared code or using dynamic `import()`.