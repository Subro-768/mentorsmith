---
id: 05-conditions
title: Conditions
order: 5
---

## Objectives
- Write `if`, `else if` and `else` chains.
- Use `switch` where it genuinely fits.
- Avoid the classic assignment-in-condition bug.
- Structure branches so that the first true case wins.

## Explanation
An `if` runs a block only when its condition is true. Anything non-zero is
true; zero is false.

```cpp
if (score >= 90) {
    grade = 'A';
} else if (score >= 80) {
    grade = 'B';
} else if (score >= 70) {
    grade = 'C';
} else {
    grade = 'F';
}
```

Order matters enormously. In this chain a score of 95 matches the *first* test
and never reaches the others. If you reversed the chain to start at
`score >= 70`, everything would become an A. Always order from most specific
to least.

A common bug is a single `=` instead of `==`:

```cpp
if (x = 5) { ... }    // assigns 5 to x, and 5 is truthy - always runs
if (x == 5) { ... }   // correct
```

Modern compilers warn about this (`-Wall` gives *suggest parentheses around
assignment used as truth value*), which is one more reason to compile with
warnings on.

When comparing floating-point values, do not test for exact equality.
`0.1 + 0.2 == 0.3` is **false** in binary floating point, because neither
`0.1` nor `0.2` is exactly representable. Compare with a tolerance:

```cpp
if (std::abs(a - b) < 1e-9) { ... }
```

**`switch`** suits matching one value against a fixed list of constants:

```cpp
switch (choice) {
    case 1: std::cout << "New game\n";   break;
    case 2: std::cout << "Load game\n";   break;
    case 3: std::cout << "Quit\n";        break;
    default: std::cout << "Invalid\n";    break;
}
```

`break` is required. Without it, execution *falls through* into the next case,
which is occasionally intentional and usually a bug.

Note that `switch` only works on integral and enum types — not `double` and
not `std::string`.

## Example
```cpp
#include <cmath>
#include <iostream>

int main() {
    const double score = 85.0;
    char grade;

    if (score >= 90)       { grade = 'A'; }
    else if (score >= 80)  { grade = 'B'; }
    else if (score >= 70)  { grade = 'C'; }
    else if (score >= 60)  { grade = 'D'; }
    else                   { grade = 'F'; }

    std::cout << "Score " << score << " -> grade " << grade << '\n';

    const char letter = 'B';
    switch (letter) {
        case 'A': std::cout << "Excellent\n"; break;
        case 'B': std::cout << "Good\n";      break;
        case 'C': std::cout << "Average\n";   break;
        default:  std::cout << "See retake\n"; break;
    }

    const double a = 0.1 + 0.2;
    const double b = 0.3;
    std::cout << "0.1+0.2 == 0.3 ?          " << std::boolalpha << (a == b) << '\n';
    std::cout << "within 1e-9?               " << (std::abs(a - b) < 1e-9) << '\n';
    return 0;
}
```

## Knowledge checks
Q: Why must the chain start with `score >= 90` rather than `score >= 70`?
A: Because the first true condition wins and the rest are skipped. Starting at the lowest threshold would let every higher score match it too.
Q: What does `if (x = 5)` do differently from `if (x == 5)`?
A: The first assigns `5` to `x` and evaluates as true. The second compares `x` against `5` and can be false.
Q: Why is `0.1 + 0.2 == 0.3` false?
A: Neither `0.1` nor `0.2` can be represented exactly in binary floating point, so the sum is very slightly off from the stored `0.3`.
Q: What happens if you omit `break` in a `switch` case?
A: Execution falls through into the next case, running that block too.

## Exercise
Read a temperature and classify it: below 0 "freezing", 0 to 14 "cold", 15 to
24 "mild", 25 to 34 "warm", 35 and above "hot". Handle input that is not a
number.

```cpp starter
#include <iostream>

int main() {
    double temperature = 0.0;

    std::cout << "Temperature: ";
    if (!(std::cin >> temperature)) {
        std::cout << "Not a number.\n";
        return 1;
    }

    // Print the classification. An if / else if chain ordered from the
    // lowest threshold upwards also works here - just be deliberate.
    return 0;
}
```

## Common mistakes
- **Chains ordered from least to most specific.** Every value matches the first test.
- **Single `=` in a condition.** Assigns instead of comparing.
- **Comparing doubles with `==`.** Use a tolerance instead.
- **Missing `break` in `switch`.** Causes fall-through.
- **Unbalanced braces** when several statements share one line without braces.

## Recap
- Order condition chains most specific first.
- `=` assigns, `==` compares.
- Avoid exact `double` comparison; use a tolerance.
- `switch` needs `break` and only handles integral and enum types.