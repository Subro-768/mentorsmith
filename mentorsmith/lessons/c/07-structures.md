---
id: 07-structures
title: Structures
order: 7
tier: core
---

## Objectives
- Declare and initialise a `struct`.
- Access members with `.` and `->`.
- Pass structs by pointer to avoid copying.
- Group related fields with a `typedef`.

## Explanation
```c
struct Point {
    int x;
    int y;
};
```

Define one, then create a variable:

```c
struct Point origin = {0, 0};
struct Point unit  = {1, 1};
```

In C, `struct` is part of the type name. That is why `typedef` exists:

```c
typedef struct {
    int x;
    int y;
} Point;

Point origin = {0, 0};     /* no "struct" needed */
```

`typedef struct Point { ... } Point;` is the same type, and what you use when
the struct must refer to itself (a linked list node).

**Member access.** `.` for a struct, `->` for a pointer to a struct:

```c
Point p = {3, 4};
printf("%d\n", p.x);          /* dot on a struct */

Point *pointer = &p;
printf("%d\n", pointer->x);   /* arrow on a pointer */
```

`pointer->x` is exactly `(*pointer).x`. Both allocate nothing.

**Passing structs.** Passing a large struct by value copies it. Pass a
pointer, and declare it `const` when you only read:

```c
void move_point(Point *p, int dx, int dy) {
    p->x += dx;
    p->y += dy;
}

double distance_squared(const Point *a, const Point *b);
```

**Arrays of structs** are contiguous and cache-friendly, which is why
`struct` arrays are preferred over parallel arrays:

```c
Student students[100];
students[0].mark = 93;
```

**Anonymous structs** let you nest fields under a name:

```c
typedef struct {
    int id;
    struct {
        int width;
        int height;
    } size;
} Item;

Item item;
item.size.width = 3;
```

**Returning a struct** is allowed and copies the result, which is fine for
small types:

```c
Point make_point(int x, int y) {
    Point p = {x, y};
    return p;
}
```

## Example
```c
/* structures.c */
#include <stdio.h>
#include <math.h>

typedef struct {
    int x;
    int y;
} Point;

typedef struct {
    Point start;
    Point end;
} Line;

typedef struct {
    char name[32];
    int  mark;
} Student;

Point make_point(int x, int y) {
    Point p;
    p.x = x;
    p.y = y;
    return p;
}

void move_point(Point *p, int dx, int dy) {
    p->x += dx;
    p->y += dy;
}

double distance_squared(const Point *a, const Point *b) {
    double dx = (double)(a->x - b->x);
    double dy = (double)(a->y - b->y);
    return dx * dx + dy * dy;
}

int main(void) {
    Point a = make_point(1, 2);
    Point b = {7, 9};

    printf("a = (%d, %d)\n", a.x, a.y);
    printf("b = (%d, %d)\n", b.x, b.y);

    a.x = 10;
    printf("after a.x = 10 -> a = (%d, %d)\n", a.x, a.y);

    Point *pointer = &a;
    pointer->y = 20;
    printf("after pointer->y = 20 -> a = (%d, %d)\n", a.x, a.y);

    move_point(&a, -5, -10);
    printf("after move -> a = (%d, %d)\n", a.x, a.y);

    printf("distance squared = %.0f\n", distance_squared(&a, &b));

    Line segment;
    segment.start.x = 0;
    segment.start.y = 0;
    segment.end.x = 3;
    segment.end.y = 4;
    printf("segment length  = %.0f\n",
           sqrt(distance_squared(&segment.start, &segment.end)));

    Student class_list[3] = {
        {"Ada", 93},
        {"Alan", 81},
        {"Grace", 74}
    };

    size_t i;
    int total = 0;
    for (i = 0; i < 3; ++i) {
        printf("%s (%d)\n", class_list[i].name, class_list[i].mark);
        total += class_list[i].mark;
    }
    printf("average = %.2f\n", (double)total / 3.0);

    return 0;
}
```

Compile with `-lm` for `sqrt`, since it lives in the math library:

```bash
gcc -std=c11 -Wall -Wextra structures.c -lm -o structures
```

## Knowledge checks
Q: When do you use `.` and when `->`?
A: `.` for a struct you have directly, `->` for a pointer to a struct. `->` is shorthand for `(*p).member`.
Q: What is `typedef` for?
A: It creates an alias so you can drop the `struct` keyword from variable declarations.
Q: Why pass a struct as a pointer?
A: Passing by value copies the whole struct on every call, which is wasteful for anything large. A pointer is one address.
Q: When can you use a `struct` in its own definition?
A: When it contains a pointer to itself, as a linked-list node does.

## Exercise
Define `struct Point` with `x` and `y`. Write `void move_point(Point*, int, int)`
and `double distance_squared(const Point*, const Point*)`. Move a point, then
print the squared distance from the origin.

```c starter
#include <stdio.h>

typedef struct {
    int x;
    int y;
} Point;

void move_point(Point *p, int dx, int dy) {
    /* Modify through the pointer. */
}

double distance_squared(const Point *a, const Point *b) {
    /* Return dx*dx + dy*dy as a double. */
}
```

## Common mistakes
- **Using `.` on a pointer,** which the compiler flags; use `->`.
- **Forgetting `const` on a read-only pointer parameter,** losing a safety check.
- **Copying large structs in a loop.**
- **Returning a pointer to a local struct,** which dangles.
- **Forgetting `-lm`** when using math functions.

## Recap
- `typedef struct { ... } Name;` removes the keyword repetition.
- `.` for a struct, `->` for a pointer to one.
- Pass large structs as `const T *`.
- Arrays of structs are compact and cache-friendly.
- Math functions need `-lm`.