---
id: 06-pointers
title: Pointers
order: 6
tier: core
---

## Objectives
- Declare pointers with `*` and initialise them to a real address.
- Use `&` and `*` correctly.
- Pass pointers to functions and dereference safely.
- Use `NULL` and check before dereferencing.

## Explanation
A pointer stores an address.

```c
int number = 42;
int *address = &number;

printf("%d\n", number);        /* 42 */
printf("%d\n", *address);      /* 42 - read through the pointer */
*address = 99;
printf("%d\n", number);        /* 99 - the original changed */
```

`&number` is the address-of operator. `*address` dereferences.

**The declaration trap.** In `int *p, q;` only `p` is a pointer — `q` is an
`int`. The `*` binds to the name, not the type:

```c
int *p, q;        /* p is int*, q is int  */
int *p, *q;       /* both are pointers */
```

When in doubt, write `int *p; int *q;`.

**Always initialise.** An uninitialised pointer holds garbage, and dereferencing
it is undefined behaviour:

```c
int *p;           /* BAD */
int *q = NULL;    /* GOOD: points at nothing */
int *r = &number; /* GOOD */
```

Use `NULL`, not `0`, and never dereference without checking:

```c
if (q != NULL) {
    printf("%d\n", *q);
}
```

Testing an address against `NULL` is always false, which is a common bug:

```c
if (&number == NULL) { ... }   /* never true */
```

**Pointer arithmetic.** Adding an `int *` by one advances by `sizeof(int)`
bytes, not one byte:

```c
int values[4] = {10, 20, 30, 40};
int *p = values;
printf("%d %d\n", *p, *(p + 2));   /* 10 30 */
printf("%d\n", *++p);               /* 20 */
```

Only `p + n` is valid — you cannot invent addresses outside the array.

**Pointers in signatures.** `const` communicates intent and prevents
accidents:

```c
void print_all(const int *values, size_t count);  /* read-only */
void fill(int *values, size_t count);              /* modifies */
```

**`void *`** is a generic pointer that can hold any address. You must cast it
before dereferencing.

## Example
```c
/* pointers.c */
#include <stdio.h>
#include <stddef.h>

void increment(int *target) {
    if (target != NULL) {
        ++(*target);
    }
}

void swap_values(int *a, int *b) {
    int temp = *a;
    *a = *b;
    *b = temp;
}

int main(void) {
    int number = 42;
    int *address = &number;

    printf("number       = %d\n", number);
    printf("address      = %p\n", (void *)address);
    printf("via pointer  = %d\n", *address);

    *address = 99;
    printf("after write  = %d\n", number);

    int *nothing = NULL;
    printf("nothing NULL = %s\n", nothing == NULL ? "yes" : "no");
    if (nothing != NULL) {
        printf("%d\n", *nothing);      /* correctly skipped */
    } else {
        printf("safely skipped a null pointer\n");
    }

    int x = 1, y = 2;
    swap_values(&x, &y);
    printf("after swap   = %d %d\n", x, y);
    increment(&x);
    printf("after inc    = %d\n", x);

    /* Pointer arithmetic advances by the size of the element */
    int values[4] = {10, 20, 30, 40};
    int *p = values;
    printf("first        = %d\n", *p);
    printf("third        = %d\n", *(p + 2));
    ++p;
    printf("after ++p    = %d\n", *p);

    /* Declaring two pointers needs two stars */
    int *pa = &x;
    int *pb = &y;
    printf("two pointers = %d %d\n", *pa, *pb);

    return 0;
}
```

## Knowledge checks
Q: In `int *p, q;`, what is `q`?
A: An `int`, not a pointer. The `*` binds to the name `p` only.
Q: Why initialise a pointer to `NULL`?
A: An uninitialised pointer holds garbage and dereferencing it is undefined behaviour. `NULL` makes the "points at nothing" state explicit and testable.
Q: Is `&number == NULL` ever true?
A: Never. The address of a real object cannot be null, so this test is always false and is usually a bug.
Q: What does `p + 1` do when `p` is an `int *`?
A: Advances the pointer by `sizeof(int)` bytes, so `*(p + 1)` is the next element.

## Exercise
Declare three `int` variables and three pointers. Set each variable to 100,
200 and 300 through its pointer, print them, then swap the values of the first
two using a pointer-based swap function.

```c starter
#include <stdio.h>

void swap_values(int *a, int *b) {
    /* Swap through the pointers. */
}

int main(void) {
    int first = 0, second = 0, third = 0;
    int *p_first = NULL;      /* point these at first, second, third */
    int *p_second = NULL;
    int *p_third = NULL;

    /* Set each through its pointer, print, then swap and print again. */
    return 0;
}
```

## Common mistakes
- **Writing `int *p, q;` expecting both to be pointers.**
- **Dereferencing `NULL` or an uninitialised pointer.**
- **Comparing `&value` against `NULL`.** Always false.
- **Doing pointer arithmetic beyond the array,** which is undefined behaviour.
- **Passing an array name and expecting a copy.** An array name decays to a pointer.

## Recap
- A pointer holds an address; `&` takes one, `*` reads one.
- `int *p, q;` declares only `p` as a pointer.
- Initialise to `NULL` or a real address, and check before dereferencing.
- `&value == NULL` is always false.
- `const T *` in a signature documents read-only use.