---
id: 05-arrays-and-strings
title: Arrays and Strings
order: 5
---

## Objectives
- Declare and index arrays safely.
- Understand that C strings are arrays of `char` ending in `'\0'`.
- Use the `<string.h>` functions correctly.
- Avoid buffer overflows.

## Explanation
```c
int values[5];                        /* 5 uninitialised ints */
int totals[3] = {10, 20, 30};         /* initialised */
```

**Indexes run 0 to `size - 1`.** `values[5]` on a 5-element array is out of
bounds, and C does **not** check. It reads or writes memory that is not yours,
which is the root of many security bugs.

Use `sizeof` for the count:

```c
size_t count = sizeof(values) / sizeof(values[0]);
```

That works for real arrays but **not** for pointers, where it silently gives
the wrong answer.

**C strings are not objects.** A string is a `char` array whose last element is
the null terminator:

```c
char greeting[] = "Hello";    /* {'H','e','l','l','o','\0'} - 6 bytes */
char *name = "World";         /* pointer to a read-only literal */
```

That is why `sizeof(greeting)` is 6 but `strlen(greeting)` is 5.

Because `"World"` lives in read-only memory, writing through `name` is undefined
behaviour. Use `char name[] = "World";` when you intend to modify it.

**`<string.h>`** gives you the operations:

| Function | Purpose |
|---|---|
| `strlen(s)` | Length, not counting `'\0'` |
| `strcpy(dst, src)` | Copy — overflows if `dst` is smaller |
| `strncpy(dst, src, n)` | Copy at most `n` — may not null-terminate |
| `strcmp(a, b)` | Compare: 0 if equal, <0 or >0 otherwise |
| `strcat(dst, src)` | Append — overflows if there is no room |

**Buffer overflow.** `strcpy` copies as many bytes as the source holds, so a
short buffer overflows:

```c
char buffer[8];
strcpy(buffer, "a much longer string");   /* overflow */
```

Safer, and always null-terminating:

```c
snprintf(buffer, sizeof(buffer), "%s", source);
```

`snprintf` takes the buffer size, so it cannot write past the end. This is the
right habit.

**2D arrays** are arrays of arrays:

```c
int grid[3][4];
grid[row][column]
```

## Example
```c
/* arrays_and_strings.c */
#include <stdio.h>
#include <string.h>

int main(void) {
    int values[5] = {10, 20, 30, 40, 50};
    size_t count = sizeof(values) / sizeof(values[0]);
    size_t i;

    printf("count        : %zu\n", count);

    int total = 0;
    for (i = 0; i < count; ++i) {
        total += values[i];
    }
    printf("total        : %d\n", total);

    int largest = values[0];
    for (i = 1; i < count; ++i) {
        if (values[i] > largest) {
            largest = values[i];
        }
    }
    printf("largest      : %d\n", largest);

    char greeting[] = "Hello";
    printf("sizeof       : %zu bytes\n", sizeof(greeting));
    printf("strlen       : %zu chars\n", strlen(greeting));

    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%s %s", greeting, "world");
    printf("snprintf     : %s\n", buffer);
    printf("strcmp equal : %d\n", strcmp("abc", "abc"));

    /* A 2D array: 3 rows of 4 columns, all zero-initialised */
    int grid[3][4] = {0};
    grid[1][2] = 7;
    printf("grid[1][2]   : %d\n", grid[1][2]);

    /* Copying safely into a fixed buffer */
    char small[8];
    snprintf(small, sizeof(small), "long text here");
    printf("truncated    : %s\n", small);

    return 0;
}
```

## Knowledge checks
Q: Why is `sizeof(greeting)` 6 for `char greeting[] = "Hello";`?
A: The array stores 5 characters plus the null terminator, so it occupies 6 bytes.
Q: What happens if you index past the end of a C array?
A: Nothing is checked. You read or write memory that is not yours, which is undefined behaviour.
Q: Why prefer `snprintf` over `strcpy`?
A: `snprintf` takes the buffer size and cannot write past the end; `strcpy` copies until the source ends and will overflow a smaller buffer.
Q: Can you write to `char *name = "World";`?
A: No. String literals live in read-only memory; writing is undefined behaviour. Use `char name[] = "World";`.

## Exercise
Declare an array of five marks, print them, find the highest and lowest, and
compute the mean as a `double`. Then copy a long string into a 16-byte buffer
safely and print it.

```c starter
#include <stdio.h>

int main(void) {
    int marks[5] = {70, 85, 92, 60, 78};
    size_t count = sizeof(marks) / sizeof(marks[0]);
    size_t i;

    int total = 0;
    /* Print the marks, the highest, the lowest, and the mean as a double. */

    return 0;
}
```

## Common mistakes
- **Looping with `i <= count`,** reading one element past the end.
- **Using `sizeof` on a pointer** to compute an array length. Wrong.
- **`strcpy` into a buffer that is too small.** Use `snprintf`.
- **Forgetting that `strlen` excludes the terminator, so you must allocate one more byte.**
- **Treating a `char *` literal as writable.**

## Recap
- Indexes are 0 to `size - 1`, and C does not check.
- `count = sizeof(a) / sizeof(a[0])` works for arrays, not pointers.
- A C string ends in `'\0'`, so it occupies one more byte than its length.
- Use `snprintf` rather than `strcpy`.
- `char *p = "text"` is read-only; `char a[] = "text"` is writable.