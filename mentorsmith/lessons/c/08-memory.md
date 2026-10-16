---
id: 08-memory
title: Memory Management
order: 8
---

## Objectives
- Allocate with `malloc` and free with `free`.
- Match every allocation with exactly one free.
- Recognise leaks, dangling pointers and double frees.
- Explain why the caller's array cannot grow inside a function.

## Explanation
Stack memory is automatic: local variables and parameters are created on entry
and reclaimed on return.

```c
void demo(void) {
    int local = 42;      /* stack */
}                        /* local is gone */
```

Heap memory is manual. Allocate with `malloc`, release with `free`:

```c
int *value = malloc(sizeof(int) * 10);
if (value == NULL) {
    /* allocation failed */
    return;
}
value[0] = 42;
free(value);
value = NULL;            /* hygiene: a freed pointer is not usable */
```

`malloc` returns `void *`, which C converts implicitly to any pointer type.

**Always check the result.** Allocation can fail, and using `NULL` is a crash.

**Every `malloc` needs exactly one `free`:**

- Too few frees: a **memory leak**
- Too many: a **double free**, which is undefined behaviour
- Using after a free: a **dangling pointer**

The pointer value still looks valid after `free`, which is why these bugs are
hard to find. The memory now belongs to someone else.

**Size arithmetic must be right.** This is the classic bug:

```c
int *values = malloc(10 * sizeof(int));    /* correct: 10 ints */
```

```c
int *values = malloc(10);                  /* WRONG: 10 bytes = 2 ints */
```

Write `malloc(count * sizeof(*values))`, where `sizeof(*values)` is the size of
what the pointer points to — this cannot go wrong if the type changes.

**You cannot grow a caller's array.** A function cannot change the length of an
array it was given, because it only has a pointer to the first element and no
way to update the caller's size:

```c
void grow(int *values, int *count);   /* the caller's count cannot be updated */
```

The usual solution is to allocate a new, larger array, copy into it, and free the
old one — and return the new pointer so the caller can use it.

**`calloc` zeroes memory**, which `malloc` does not:

```c
int *values = calloc(10, sizeof(int));   /* all bytes set to 0 */
```

**Other functions:** `realloc` resizes an existing block (and may move it, so
always use the returned pointer), `free(NULL)` is safe and does nothing.

## Example
```c
/* memory.c */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int *leaky_allocate(void) {
    int *value = malloc(sizeof(int));
    *value = 42;
    return value;              /* BUG: the local pointer dies, memory leaks */
}

int *frees_memory(void) {
    int *value = malloc(sizeof(int));
    *value = 42;
    int copy = *value;
    free(value);
    printf("freed safely, value was %d\n", copy);
    return NULL;
}

int *make_values(size_t count) {
    /* sizeof(*values) cannot go stale if the type changes */
    int *values = malloc(count * sizeof(*values));
    if (values == NULL) {
        return NULL;           /* allocation failed - caller must check */
    }
    size_t i;
    for (i = 0; i < count; ++i) {
        values[i] = (int)i * 2;
    }
    return values;
}

int *grown_copy(const int *values, size_t count) {
    size_t new_count = count * 2;
    int *bigger = malloc(new_count * sizeof(*bigger));
    if (bigger == NULL) {
        return NULL;
    }
    memcpy(bigger, values, count * sizeof(*bigger));
    size_t i;
    for (i = count; i < new_count; ++i) {
        bigger[i] = -1;
    }
    return bigger;
}

int main(void) {
    /* 1. Automatic storage: created and destroyed by scope */
    {
        int local = 42;
        printf("stack local = %d\n", local);
    }

    /* 2. Explicit allocation, checked, then freed */
    int *values = make_values(4);
    if (values == NULL) {
        printf("allocation failed\n");
        return 1;
    }
    size_t i;
    for (i = 0; i < 4; ++i) {
        printf("values[%zu] = %d\n", i, values[i]);
    }

    /* 3. Growing requires a new block and a copy */
    int *bigger = grown_copy(values, 4);
    if (bigger != NULL) {
        printf("grown first free slot = %d\n", bigger[4]);
        free(bigger);
    }

    free(values);
    values = NULL;
    printf("freed values\n");

    /* 4. calloc zeroes */
    int *zeroed = calloc(3, sizeof(int));
    printf("calloc [0] = %d (zeroed)\n", zeroed[0]);
    free(zeroed);

    /* 5. free(NULL) is safe */
    free(NULL);
    printf("free(NULL) = no crash\n");

    /* 6. int *p = NULL; free(p);  is also safe */

    /* deliberately not calling leaky_allocate(): it leaks on purpose */
    printf("\nleaky_allocate() would leak 4 bytes.\n");

    return 0;
}
```

Find leaks with:

```bash
gcc -std=c11 -Wall -Wextra -fsanitize=address,leak memory.c -o memory
./memory
```

## Knowledge checks
Q: What happens if you `free` a pointer twice?
A: Undefined behaviour, usually a crash. There is no portable way to make it safe.
Q: Why is `malloc(10)` wrong when you want 10 ints?
A: It allocates 10 *bytes*, not 10 ints. Write `malloc(10 * sizeof(int))`.
Q: Why check the result of `malloc`?
A: Allocation can fail. Using `NULL` is a crash; ignoring the failure loses data silently.
Q: Why can a function not make the caller's array grow?
A: It only receives a pointer to the first element and has no way to update the caller's length variable.

## Exercise
Write three functions: `int *alloc_array(size_t)` returning a checked
allocation, `void fill(int *, size_t)` setting each element to its index
doubled, and `void release(int *)` that frees and sets nothing (returning NULL
requires returning `int *`). Call them, print, and free.

```c starter
#include <stdlib.h>
#include <stdio.h>

int *alloc_array(size_t count) {
    /* malloc and return NULL on failure */
}

void fill(int *values, size_t count) {
    /* set values[i] = i * 2 */
}
```

## Common mistakes
- **`malloc(10)` instead of `malloc(10 * sizeof(int))`.** Allocate the wrong number of bytes.
- **Not checking for `NULL`.**
- **Freeing twice, or freeing a stack address.**
- **Ignoring the pointer returned by `realloc`,** which invalidates the old pointer.
- **Using a pointer after freeing it.**

## Recap
- Stack is automatic; heap is manual.
- `malloc(count * sizeof(*p))`, checked for `NULL`.
- Exactly one `free` per allocation; a dangling pointer still looks valid.
- A caller's array cannot grow in place.
- `calloc` zeroes; `free(NULL)` is safe.
- Compile with `-fsanitize=address,leak` to find real leaks.