---
id: 06-loops
title: Loops
order: 6
---

## Objectives
- Use `while`, `do while` and `for` appropriately.
- Predict how many times each loop body runs.
- Avoid infinite loops and off-by-one errors.
- Use `break`, `continue` and range-based `for` correctly.

## Explanation
C++ has three loops. Pick the one that matches the loop's purpose.

**`while` — repeat while a condition holds.** Use when the number of
iterations is not known in advance.

```cpp
int n;
std::cout << "Enter a positive number: ";
std::cin >> n;
while (n > 0) {
    std::cout << n << ' ';
    --n;                     // without this, the loop never ends
}
```

That missing decrement is the classic infinite loop. Any `while` must make
progress toward its exit condition on every pass.

**`do while` — run once, then repeat.** Use when the body must run at least
once, such as menu-driven input validation.

```cpp
char choice;
do {
    std::cout << "Enter A or B: ";
    std::cin >> choice;
} while (choice != 'A' && choice != 'B');
```

Note the semicolon after the closing `while ( ... )`.

**`for` — count.** Use when you know the number of iterations.

```cpp
for (int i = 0; i < 5; ++i) {
    std::cout << i << ' ';
}
```

The three parts are: initialise once, test before each iteration, then update.
`i < 5` runs five times with `i` equal to 0, 1, 2, 3 and 4. Writing `i <= 5`
would run six times — the **off-by-one error**.

**Range-based `for`** walks a container and is the clearest way to iterate
anything iterable:

```cpp
std::vector<int> scores = {80, 90, 75};
for (int score : scores) {
    std::cout << score << ' ';
}
```

Use `const auto&` when you only need to read:

```cpp
for (const auto& item : items) {   // no copy, cannot modify
    std::cout << item << '\n';
}
```

**`break`** leaves the loop immediately. **`continue`** skips to the next
iteration. Both are easy to overuse — a loop with several `break`s is often
clearer as two simpler loops.

**Watch your loop variable's type.** With `int i` and a limit of `scores.size()`
(which returns `std::size_t`), comparing a signed `int` against an unsigned
value triggers a compiler warning, and `i = -1` would never satisfy the test.

## Example
```cpp
#include <iostream>
#include <vector>

int main() {
    // for: known count
    std::cout << "Counting 1 to 5: ";
    for (int i = 1; i <= 5; ++i) {
        std::cout << i << ' ';
    }
    std::cout << '\n';

    // while: unknown count
    int countdown = 3;
    while (countdown > 0) {
        std::cout << "T-minus " << countdown << '\n';
        --countdown;
    }

    // do while: at least one pass
    int number = -5;
    do {
        std::cout << "do while ran with " << number << '\n';
        ++number;
    } while (number < 0);

    // range-based for
    const std::vector<int> scores = {80, 90, 75, 92};
    int total = 0;
    for (int score : scores) {
        total += score;
    }
    std::cout << "Average = "
              << static_cast<double>(total) / scores.size() << '\n';

    // break and continue
    for (int score : scores) {
        if (score < 80) {
            continue;                  // skip this one
        }
        if (score > 90) {
            std::cout << "Found a high score: " << score << '\n';
            break;                     // stop entirely
        }
    }
    return 0;
}
```

## Knowledge checks
Q: How many times does `for (int i = 0; i < 5; ++i)` run its body?
A: Five times, with `i` equal to 0, 1, 2, 3 and 4.
Q: What is the difference between `while` and `do while`?
A: `do while` always executes its body at least once before testing the condition; `while` tests first.
Q: What goes wrong if a `while` loop body never changes the condition variable?
A: The loop is infinite — it runs forever because the exit condition never becomes false.
Q: What does `continue` do, and what does it differ from `break` in?
A: `continue` jumps to the next iteration, skipping the rest of the current pass. `break` exits the loop entirely.

## Exercise
Print the first 10 multiples of 7 using a `for` loop. Then, in a second loop,
read numbers from the user until they enter `0`, keeping a running count and
sum, and print the average once they do.

```cpp starter
#include <iostream>

int main() {
    // Part 1: for loop printing 7, 14, 21 ... up to 70.
    std::cout << "Multiples of 7: ";

    // Part 2: while loop.
    //   Read ints until 0 is entered.
    //   Track count and sum, then print the average as a double.
    //   Handle the case where the very first number is 0 (avoid / 0).
    return 0;
}
```

## Common mistakes
- **Off-by-one.** `i <= n` runs one extra time compared with `i < n`.
- **Infinite loops** from a missing increment or decrement.
- **Forgetting the semicolon** after a `do while` condition.
- **Modifying the container** while iterating over it with a range-based loop.
- **Comparing a signed loop counter against `size_t`.** Prefer `for (std::size_t i = 0; ...)` when indexing.

## Recap
- `while` for unknown counts, `for` for known counts, `do while` for at-least-once.
- Every `while` must advance toward its exit condition.
- `<` vs `<=` is the off-by-one decision — work it out explicitly.
- `break` exits, `continue` skips to the next iteration.
- `for (const auto& x : container)` iterates without copying.