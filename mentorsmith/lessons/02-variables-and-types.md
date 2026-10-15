---
id: 02-variables-and-types
title: Variables and Types
order: 2
---

## Objectives
- Declare variables with meaningful names.
- Choose between the common built-in types.
- Explain what "scope" is and why a variable stops existing.
- Read an initialisation and understand why initialisation matters.

## Explanation
A variable is a named piece of memory with a type. The type decides three
things: how many bytes are reserved, how the bits are interpreted, and which
operations are legal on the value.

The core built-in types:

| Type | Typical size | Use it for |
|---|---|---|
| `int` | 4 bytes | Whole numbers, counts, indexes |
| `double` | 8 bytes | Fractional numbers, measurements |
| `char` | 1 byte | A single character, or a small integer |
| `bool` | 1 byte | `true` or `false` |
| `long long` | 8 bytes | Whole numbers too large for `int` |

Declare and initialise in one step. This is preferred over separating the two:

```cpp
int age = 30;            // good
int height;              // fine when you assign later
int width = 100, depth = 50;  // two variables, one line
```

`const` marks a value that must never change after initialisation. Use it by
default for anything that is logically fixed — it turns a silent bug into a
compile error:

```cpp
const double pi = 3.14159265358979;
// pi = 3.0;   // error: assignment of read-only variable
```

**Scope** is the region of code where a name is visible. A variable declared
inside a function exists only until that function returns. Declaring variables
close to first use keeps scope small, which prevents accidental access to a
value that belongs somewhere else.

```cpp
int global = 5;          // visible everywhere - avoid unless necessary

int main() {
    int local = 10;      // visible only inside main
    {
        int inner = 20;  // visible only inside these braces
    }
    // inner is not accessible here
}
```

Name variables after what they mean, not their type. `total_price` beats
`int_d`; `student_count` beats `i2`.

## Example
```cpp
#include <iostream>

int main() {
    const int    items    = 3;
    const double unit_cost = 4.50;

    double total = items * unit_cost;

    std::cout << "Items:     " << items << '\n';
    std::cout << "Unit cost: " << unit_cost << '\n';
    std::cout << "Total:     " << total << '\n';
    return 0;
}
```

## Knowledge checks
Q: Why is `const double pi = 3.14;` better than `double pi = 3.14;` here?
A: Because `pi` never changes. `const` lets the compiler catch any accidental reassignment instead of letting it slip through.
Q: What is the difference between `int` and `double`?
A: `int` stores whole numbers exactly; `double` stores an approximation using binary floating point.
Q: What happens to a local variable when its function returns?
A: It goes out of scope and can no longer be named or accessed.

## Exercise
Create three variables for a rectangle — `width`, `height` and `area` — where
width is 7, height is 3, and `area` is the product of the two. Print all three
on separate lines.

```cpp starter
#include <iostream>

int main() {
    const int width = 7;
    const int height = 3;
    // Declare `area`, compute width * height, then print width, height and area.
    return 0;
}
```

Extension: declare a second variable called `area` inside a nested block with a
different value, and notice that C++ allows it because the scopes do not
overlap.

## Common mistakes
- **Assuming `int` stores fractions.** `5 / 2` is `2` with two `int`s, but `2.5` with two `double`s. This integer division surprises almost everyone once.
- **Unused variables.** `g++ -Wall` warns about them; the warning is real, not noise.
- **Redeclaring in the same scope.** A second `int width = 5;` in the same block is a compile error.
- **Single-letter names outside tiny loops.** You cannot read `w` or `h` meaningfully a week later.

## Recap
- A variable is named memory with a type; the type governs size, meaning and legal operations.
- `const` prevents reassignment and is worth using by default.
- Scope limits where a name is visible; keep it as small as practical.
- `int` division truncates; `double` division does not.
- Name variables for meaning.