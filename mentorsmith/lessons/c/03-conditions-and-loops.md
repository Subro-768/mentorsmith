---
id: 03-conditions-and-loops
title: Conditions and Loops
order: 3
---

## Objectives
- Write `if`, `else` and `switch` correctly.
- Use `while`, `do while` and `for`, and choose between them.
- Avoid off-by-one errors and infinite loops.
- Use `break` and `continue` deliberately.

## Explanation
Conditions are the same as in C++:

```c
if (score >= 90) {
    grade = 'A';
} else if (score >= 80) {
    grade = 'B';
} else {
    grade = 'F';
}
```

**In C, any non-zero value is true.** This matters because comparison operators
return `1` for true and `0` for false, so you can write:

```c
if (count) { ... }        /* true when count is not 0 */
```

but you must never write `if (count = 5)`, which assigns and is almost always a
bug. Compile with `-Wall` and the compiler will tell you.

**Loops.** All three forms from C++ exist:

```c
/* while: unknown count */
int n = 3;
while (n > 0) {
    printf("%d ", n);
    --n;
}

/* do while: at least one pass */
int value;
do {
    scanf("%d", &value);
} while (value <= 0);

/* for: known count */
for (int i = 0; i < 5; ++i) {
    printf("%d ", i);
}
printf("\n");
```

Declaring `i` inside the `for` header is C99 and later. It is the modern
idiom and it keeps the variable scoped to the loop.

**`switch` only works on integral types** — not floats, not strings:

```c
switch (choice) {
    case 1:  printf("New game\n"); break;
    case 2:  printf("Load game\n"); break;
    default: printf("Invalid\n");   break;
}
```

The `break` is required. Without it execution falls through into the next case.

**Off-by-one.** `for (i = 0; i < 5; ++i)` runs five times with `i` equal to 0..4.
Changing `<` to `<=` adds a sixth pass.

**`break` and `continue`** work as in C++. Use them sparingly; a loop with
several `break`s is often clearer as two simpler loops.

## Example
```c
/* conditions_and_loops.c */
#include <stdio.h>

int main(void) {
    int i;

    for (i = 1; i <= 5; ++i) {
        printf("%d ", i);
    }
    printf("\n");

    int n = 3;
    while (n > 0) {
        printf("countdown %d\n", n);
        --n;
    }

    int value = 0;
    do {
        ++value;
    } while (value < 3);
    printf("do while ran %d times\n", value);

    /* A truthy value: 42 is not zero, so this branch is taken. */
    int truthy = 42;
    if (truthy) {
        printf("non-zero is true in C\n");
    }

    /* switch on an integer */
    int choice = 2;
    switch (choice) {
        case 1:
            printf("New game\n");
            break;
        case 2:
            printf("Load game\n");
            break;
        default:
            printf("Invalid choice\n");
            break;
    }

    /* break and continue */
    for (i = 0; i < 6; ++i) {
        if (i == 3) {
            continue;              /* skip 3 */
        }
        if (i == 5) {
            break;                 /* stop before 5 */
        }
        printf("kept %d\n", i);
    }

    return 0;
}
```

## Knowledge checks
Q: Which values are true in C?
A: Any non-zero value. Zero is the only false value.
Q: How many times does `for (i = 0; i < 5; ++i)` run?
A: Five times, with `i` equal to 0 to 4.
Q: What happens if a `switch` case has no `break`?
A: Execution falls through into the next case and runs that code too.
Q: What is the difference between `break` and `continue`?
A: `break` exits the loop; `continue` skips to the next iteration.

## Exercise
Print the first 10 multiples of 7 with a `for` loop. Then use a `while` loop to
read integers until the user enters 0, keeping a count and sum, and print the
average as a `double`.

```c starter
#include <stdio.h>

int main(void) {
    int i;

    /* Part 1: for loop printing 7, 14, ... 70. */

    /* Part 2: while loop reading ints until 0.
       Remember: scanf needs an address, so &value. */

    return 0;
}
```

## Common mistakes
- **`if (x = 5)`** assigns instead of comparing.
- **`scanf("%d", value)`** without `&`. It must receive the address.
- **`<=` where you meant `<`,** adding an extra iteration.
- **Forgetting `break` in a `switch`.**
- **Comparing against `'\0'` in a loop** where you meant a digit `0`. They differ.

## Recap
- Non-zero is true; zero is false.
- `while` for unknown counts, `for` for known, `do while` for at-least-once.
- `for (int i = 0; ...)` scopes the counter and is the modern idiom.
- `switch` needs `break` and only handles integral types.
- `scanf` takes addresses.