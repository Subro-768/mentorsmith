---
id: 02-types
title: Types and Storage
order: 2
---

## Objectives
- Use the basic C types and know their sizes.
- Choose `float` or `double` deliberately.
- Understand integer division and the usual conversions.
- Format values correctly with `printf`.

## Explanation
| Type | Typical size | Notes |
|---|---|---|
| `char` | 1 byte | One character, or −128..127 |
| `short` | 2 bytes | Rarely needed |
| `int` | 4 bytes | The default integer |
| `long` | 8 bytes on 64-bit Linux | Use `long long` for certainty |
| `float` | 4 bytes | About 7 significant digits |
| `double` | 8 bytes | About 15–17 significant digits |

Check rather than assume with `sizeof`:

```c
#include <stdio.h>

int main(void) {
    printf("%zu %zu %zu %zu\n",
           sizeof(char), sizeof(int), sizeof(long), sizeof(double));
    return 0;
}
```

`%zu` is the correct specifier for `sizeof`, which has type `size_t`.

**Integer division truncates.** This is C's most common surprise and it is the
same trap as in C++:

```c
int a = 7, b = 2;
printf("%d\n", a / b);     /* 3 */
printf("%.1f\n", a / (double)b);  /* 3.5 - cast first! */
printf("%d\n", a % b);     /* 1 - remainder */
```

**The usual arithmetic conversions.** When you mix types, C promotes the lower
rank one. `int + double` becomes `double`. But `char + int` is `int`, and
comparisons are safest when both sides have the same type.

**Signed and unsigned.** `unsigned int` cannot hold a negative value, so
comparing a signed value against an unsigned one is a classic bug:

```c
int size = 5;
unsigned int n = 3;
if (size > n) { ... }   /* fine */
size = -1;
if (size > n) { ... }   /* -1 converts to a huge unsigned -> true! */
```

Declare loop counters to match what you compare against:

```c
for (size_t i = 0; i < count; ++i) { ... }
```

**Format specifiers must match the type**, or you get garbage:

| Type | Specifier |
|---|---|
| `int` | `%d` |
| `unsigned int` | `%u` |
| `long` | `%ld` |
| `double` | `%f` (in `printf`) |
| `char *` | `%s` |
| pointer | `%p` |

Passing a `double` to `%d` is undefined behaviour, so it may print nonsense
rather than failing loudly.

## Example
```c
/* types.c */
#include <stdio.h>

int main(void) {
    int    a = 7;
    int    b = 2;
    double c = 7.0;

    printf("sizes: char=%zu int=%zu long=%zu double=%zu\n",
           sizeof(char), sizeof(int), sizeof(long), sizeof(double));

    printf("7 / 2            = %d\n", a / b);
    printf("7 %% 2            = %d\n", a % b);
    printf("7.0 / 2          = %.2f\n", c / b);
    printf("(double)7 / 2    = %.2f\n", (double)a / b);
    printf("1 / 3            = %.6f\n", 1.0 / 3.0);

    char letter = 'Z';
    printf("char             = %c, as int %d\n", letter, letter);

    float small = 1.0f / 3.0f;
    double better = 1.0 / 3.0;
    printf("float            = %.7f\n", small);
    printf("double           = %.15f\n", better);

    return 0;
}
```

## Knowledge checks
Q: What is the value of `7 / 2` when both are `int`?
A: `3`. Integer division discards the fractional part.
Q: Why use `sizeof` rather than assuming a type's size?
A: Sizes are implementation-defined; `sizeof` reports what this compiler actually uses.
Q: Why is comparing a negative `int` against an `unsigned int` dangerous?
A: The negative value converts to a huge unsigned number, so the comparison gives the opposite of what you expected.
Q: What does `%zu` format?
A: A `size_t`, which is what `sizeof` returns.

## Exercise
Declare an `int` numerator of 7 and denominator of 2, and print the integer
division result, the remainder, and the same division promoted to `double`.
Use the correct specifier for each and label every line.

```c starter
#include <stdio.h>

int main(void) {
    int numerator = 7;
    int denominator = 2;
    /* Print integer division, remainder, and the promoted result. */
    return 0;
}
```

Extension: print `sizeof` for `int`, `double` and `char` on one line.

## Common mistakes
- **Printing a `double` with `%d`.** Undefined behaviour; use `%f`.
- **Dividing two `int`s and expecting a fraction.** Cast one to `double`.
- **Comparing signed against unsigned.**
- **Assuming `int` is 64-bit.** Use `long long` when you need the range.
- **Using `%f` with `scanf` but `%lf` carelessly.** In `scanf`, `%f` reads a `float*` and `%lf` reads a `double*`.

## Recap
- Know your sizes, but verify with `sizeof`.
- Integer division truncates; cast to `double` to divide properly.
- Mismatched format specifiers are undefined behaviour.
- Signed/unsigned comparison is a common bug.
- `size_t` for sizes and indices, and `%zu` to print it.