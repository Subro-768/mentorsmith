---
id: 06-error-handling
title: Error Handling
order: 6
---

## Objectives
- Distinguish the error types JavaScript gives you.
- Use `try`/`catch`/`finally` and `throw`.
- Write error messages that say what to do next.
- Know when *not* to use exceptions.

## Explanation
JavaScript has several error types, and knowing which you have tells you what
to do:

| Type | Cause |
|---|---|
| `TypeError` | Wrong type or shape (`undefined.x`) |
| `RangeError` | Value outside the allowed range |
| `ReferenceError` | Name does not exist |
| `SyntaxError` | The code does not parse |
| `Error` | The general case you raise yourself |

```javascript
try {
  const result = JSON.parse(text);
  console.log(result);
} catch (error) {
  if (error instanceof SyntaxError) {
    console.log("That was not valid JSON.");
  } else {
    throw error;                  // do not swallow what you do not understand
}
} finally {
  console.log("always runs");
}
```

**Throw your own errors with a useful message:**

```javascript
function withdraw(balance, amount) {
  if (amount <= 0) {
    throw new RangeError("amount must be greater than zero");
  }
  if (amount > balance) {
    throw new RangeError(`cannot withdraw ${amount} from a balance of ${balance}`);
  }
  return balance - amount;
}
```

The message should tell the caller what to fix. `"Error"` helps nobody.

**`finally` always runs**, including when the error propagates. Use it for
cleanup.

**Re-throwing to add context** while keeping the original:

```javascript
try {
  JSON.parse(text);
} catch (error) {
  throw new Error(`could not parse the config: ${error.message}`, { cause: error });
}
```

The second argument sets `cause`, which keeps the original error reachable.

**Do not swallow errors.** An empty `catch` that does nothing hides real bugs
and is the single most common way a JavaScript program becomes undebuggable:

```javascript
try { risky(); } catch { }        // BAD: everything vanishes
```

If a particular failure is genuinely expected and recoverable, handle it
specifically. Otherwise re-throw.

**Prefer returning a result object** when failure is an ordinary outcome, not
an exceptional one. Parsing user input is routine; a network outage is not:

```javascript
function tryParse(text) {
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch {
    return { ok: false, error: "invalid JSON" };
  }
}
```

**Assertion helper.** To require a value and fail loudly if it is missing,
which is useful in tests:

```javascript
function mustBeDefined(value, label = "value") {
  if (value === undefined || value === null) {
    throw new Error(`${label} is missing`);
  }
  return value;
}
```

**Errors and async.** In an `async` function, `throw` rejects the returned
promise, so you need `await` plus `try`/`catch` — a bare `catch` on a
non-awaited promise will not run. That is covered in the async lesson.

## Example
```javascript
// error_handling.mjs
class ValidationError extends Error {
  constructor(message, field) {
    super(message);
    this.name = "ValidationError";
    this.field = field;
  }
}

function withdraw(balance, amount) {
  if (typeof amount !== "number") {
    throw new TypeError("amount must be a number");
  }
  if (amount <= 0) {
    throw new RangeError("amount must be greater than zero");
  }
  if (amount > balance) {
    throw new ValidationError(
      `cannot withdraw ${amount} from a balance of ${balance}`,
      "amount"
    );
  }
  return balance - amount;
}

function parseConfig(text) {
  try {
    return JSON.parse(text);
  } catch (error) {
    // Add context but keep the original reachable.
    throw new Error(`could not parse the config: ${error.message}`, { cause: error });
  }
}

console.log("valid   :", withdraw(100, 40));

try {
  withdraw(100, 500);
} catch (error) {
  console.log("name    :", error.name);
  console.log("message :", error.message);
  console.log("field   :", error.field);
}

try {
  withdraw(100, "50");
} catch (error) {
  console.log("type    :", error instanceof TypeError);
}

// Distinguishing error types
try {
  parseConfig("{ not json");
} catch (error) {
  console.log("context :", error.message);
  console.log("cause   :", error.cause instanceof SyntaxError);
}

// Expected failure returns a value instead of throwing
function tryParse(text) {
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch (error) {
    return { ok: false, error: "invalid JSON" };
  }
}
console.log("tryParse ok  :", tryParse('{"a":1}'));
console.log("tryParse bad :", tryParse("{ nope"));

// finally always runs
let cleaned = false;
try {
  throw new Error("boom");
} catch {
  console.log("caught the boom");
} finally {
  cleaned = true;
  console.log("cleaned up in finally:", cleaned);
}
```

## Knowledge checks
Q: Why should an empty `catch` block be avoided?
A: It discards the error, hiding genuine bugs and making the program impossible to debug. Handle what you understand and re-throw the rest.
Q: What does the `cause` option on `new Error(...)` do?
A: Attaches the original error, so the underlying cause stays reachable instead of being lost.
Q: When is returning an error value better than throwing?
A: When failure is an ordinary, expected outcome such as invalid user input, where the caller branches on the result anyway.
Q: When does `finally` run?
A: On every path: after a normal return, after a caught error, and while an error propagates outward.

## Exercise
Write `parseAge(text)` that converts a string to an integer age, throwing a
`TypeError` for non-numeric text and a `RangeError` for anything outside 0 to
150. Then call it with a valid value, a non-numeric string, and a negative
number, catching each case separately.

```javascript starter
function parseAge(text) {
  // Number() it; throw TypeError if NaN
  // throw RangeError if < 0 or > 150
  // otherwise return the integer
}

for (const input of ["36", "abc", "-5"]) {
  try {
    console.log(input, "->", parseAge(input));
  } catch (error) {
    console.log(input, "-> rejected:", error.name, error.message);
  }
}
```

## Common mistakes
- **An empty `catch` block,** swallowing every failure.
- **`catch` with no parameter,** which makes it easy to ignore the error by accident.
- **Re-throwing without context,** losing what the caller needs to know.
- **Throwing strings or numbers** instead of `Error` objects.
- **Assuming `catch` fires for a promise rejection** without `await`.

## Recap
- Catch specific error types; re-throw what you do not understand.
- Throw `Error` subclasses with messages that say what to fix.
- `finally` always runs; use it for cleanup.
- `cause` preserves the original error.
- For routine failures, return a result object instead of throwing.