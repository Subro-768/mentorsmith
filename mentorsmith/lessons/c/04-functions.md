---
id: 04-functions
title: Functions
order: 4
---

## Objectives
- Write functions with parameters and return values.
- Pass by value versus by pointer in C.
- Declare functions before use.
- Give every function exactly one job.

## Explanation
```c
int add(int a, int b) {
    return a + b;
}
```

C has **no references**. Every parameter is passed by value: the function
receives a copy. To let a function modify the caller's variable you pass a
pointer:

```c
void swap_values(int *a, int *b) {
    int temp = *a;
    *a = *b;
    *b = temp;
}

int main(void) {
    int x = 2, y = 1;
    swap_values(&x, &y);
    printf("%d %d\n", x, y);   /* 1 2 */
    return 0;
}
```

`&x` gives the address, `*a` reads through it. This is exactly how C++
references behave, spelled with pointers instead.

**To avoid copying a large value, take a pointer:**

```c
/* copies the whole array */
void bad(int values[100]);

/* no copy, read-only */
void good(const int *values, size_t count);
```

Always declare the parameter `const` when you only read through it.

**C requires a declaration before use**, which is stricter than C++. Two
solutions: define the function above `main`, or add a prototype:

```c
int add(int a, int b);        /* prototype: no body */

int main(void) {
    return add(1, 2);
}

int add(int a, int b) {       /* definition */
    return a + b;
}
```

**Arrays cannot be returned.** You cannot write `int make_array(void)`. Either
return a pointer to heap memory the caller must `free`, or pass in a buffer and
fill it. That constraint is a direct consequence of arrays being values.

**`void` versus no return.** A function that returns nothing is declared
`void`, and a bare `return;` is the only legal way out of it early.

## Example
```c
/* functions.c */
#include <stdio.h>

int add(int a, int b);
int triple(int x);

void swap_values(int *a, int *b) {
    int temp = *a;
    *a = *b;
    *b = temp;
}

int sum_of(const int *values, size_t count) {
    int total = 0;
    size_t i;
    for (i = 0; i < count; ++i) {
        total += values[i];
    }
    return total;
}

int add(int a, int b) {
    return a + b;
}

int triple(int x) {
    return x * 3;
}

int main(void) {
    int x = 2, y = 1;
    swap_values(&x, &y);
    printf("after swap : %d %d\n", x, y);

    int values[5] = {1, 2, 3, 4, 5};
    printf("sum         : %d\n", sum_of(values, 5));

    printf("add(3, 4)   : %d\n", add(3, 4));
    printf("triple(7)   : %d\n", triple(7));

    /* A function cannot change a caller's int without a pointer. */
    int n = 5;
    printf("before      : %d\n", n);

    return 0;
}
```

## Knowledge checks
Q: How do you let a function change the caller's variable in C?
A: Pass a pointer and modify through it with `*`. There are no references in C.
Q: What is the advantage of `const int *values` over `int values[100]`?
A: It avoids copying the whole array and documents that the function will not modify it.
Q: Why declare a function before calling it?
A: C requires a declaration before use; a prototype tells the compiler the signature without the body.
Q: Why can you not return an array from a C function?
A: An array type cannot be returned by value. Return a pointer to allocated memory instead, and the caller must free it.

## Exercise
Write three functions: `void swap_values(int*, int*)`, `int sum(const int*, size_t)`
and `int max_of(const int*, size_t)`. Then call them from `main` and print the
results.

```c starter
#include <stdio.h>
#include <stddef.h>

void swap_values(int *a, int *b) {
    /* Swap through the pointers. */
}

int sum(const int *values, size_t count) {
    /* Return the total. */
}

int max_of(const int *values, size_t count) {
    /* Return the largest value. */
}
```

## Common mistakes
- **Passing `&x` when the parameter is `int`** — a type mismatch.
- **Forgetting `*`** when using a pointer parameter.
- **Modifying a pointer's target through a `const` pointer,** which the compiler correctly rejects.
- **Returning a pointer to a local variable,** which dangles once the function returns.
- **Omitting the prototype,** causing an implicit declaration error.

## Recap
- C has no references; use pointers to modify the caller's data.
- `const T *` avoids copying and documents read-only use.
- Declare functions before use, or add prototypes.
- Arrays cannot be returned by value.
- `void` functions may only use bare `return;`.