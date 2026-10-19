---
id: 12-structures
title: Structures
order: 12
tier: core
---

## Objectives
- Declare and use a `struct` to group related data.
- Access members with `.` and `->`.
- Initialise structs safely and pass them correctly to functions.
- Know when to move on to classes.

## Explanation
A `struct` groups related variables under one name. It is a simple way to model
an entity made of several values.

```cpp
struct Point {
    int x;
    int y;
};
```

Define it, then create a variable:

```cpp
Point origin{0, 0};                 // brace initialisation - preferred
Point unit{1, 1};
Point partial{};                    // zero-initialised, then set later
partial.x = 5;
```

Prefer braces over the older parenthesised form. `Point p{1, 2};` is checked at
compile time, whereas `Point p(1, 2);` can silently do something unexpected
when the constructor takes a different shape.

**Accessing members.** Use `.` when you have the object itself, and `->` when
you have a pointer to it:

```cpp
Point p{3, 4};
p.x = 10;                 // dot on an object

Point* pointer = &p;
pointer->x = 20;          // arrow on a pointer  (same as (*pointer).x)
```

The `->` operator exists precisely because `(*pointer).x` is unreadable.

**A struct has no private section** by default — every member is public.
Structs are meant for plain data bundles. That is the practical difference
from a class, which is about *behaviour plus controlled access* (covered in
lessons 13 and 14).

**Passing structs.** For a small struct, pass by value:

```cpp
void move_point(Point& p, int dx, int dy) {
    p.x += dx;
    p.y += dy;
}
```

For a larger struct, pass by `const` reference to avoid copying:

```cpp
double distance_squared(const Point& a, const Point& b);
```

**Returning** a small struct by value is fine and often clearer than filling
an output parameter:

```cpp
Point make_point(int x, int y) {
    return Point{x, y};
}
```

**Nested structs** are allowed and useful for grouping.

```cpp
struct Line {
    Point start;
    Point end;
};
```

One practical note: `std::cout << point;` does not compile, because the stream
operators know nothing about your type. Write a member function if you want to
print it, and teach `std::cout` about your type only when you genuinely need
it:

```cpp
#include <ostream>

std::ostream& operator<<(std::ostream& os, const Point& p) {
    return os << '(' << p.x << ", " << p.y << ')';
}
```

## Example
```cpp
#include <cmath>
#include <iostream>
#include <string>
#include <vector>

struct Point {
    int x;
    int y;
};

struct Line {
    Point start;
    Point end;
};

struct Student {
    std::string name;
    int         mark;
};

Point make_point(int x, int y) {
    return Point{x, y};
}

void move_point(Point& p, int dx, int dy) {
    p.x += dx;
    p.y += dy;
}

double distance_between(const Point& a, const Point& b) {
    const double dx = a.x - b.x;
    const double dy = a.y - b.y;
    return std::sqrt(dx * dx + dy * dy);
}

std::string grade_for(int mark) {
    if (mark >= 90) return "A";
    if (mark >= 80) return "B";
    if (mark >= 70) return "C";
    return "F";
}

int main() {
    Point a = make_point(1, 2);
    Point b{7, 9};

    std::cout << "a = (" << a.x << ", " << a.y << ")\n";
    std::cout << "b = (" << b.x << ", " << b.y << ")\n";

    a.x = 10;                    // dot on an object
    std::cout << "after a.x = 10 -> a = (" << a.x << ", " << a.y << ")\n";

    Point* pointer = &a;
    pointer->y = 20;             // arrow on a pointer
    std::cout << "after pointer->y = 20 -> a = (" << a.x << ", " << a.y << ")\n";

    move_point(a, -5, -10);
    std::cout << "after move      -> a = (" << a.x << ", " << a.y << ")\n";

    std::cout << "distance a..b  = " << distance_between(a, b) << '\n';

    const Line segment{ Point{0, 0}, Point{3, 4} };
    std::cout << "segment length  = " << distance_between(segment.start, segment.end) << '\n';

    std::vector<Student> class_list{
        { "Ada",   93 },
        { "Alan",  81 },
        { "Grace", 74 },
    };

    int total = 0;
    for (const Student& student : class_list) {
        std::cout << student.name << " (" << student.mark
                  << ") -> " << grade_for(student.mark) << '\n';
        total += student.mark;
    }
    std::cout << "average = "
              << static_cast<double>(total) / class_list.size() << '\n';
    return 0;
}
```

## Knowledge checks
Q: When do you use `.` and when do you use `->`?
A: `.` for an object you have directly, `->` for a pointer to an object. `->` is shorthand for `(*pointer).member`.
Q: What is the difference between a `struct` and a `class` in C++?
A: Purely defaults: `struct` members are public by default, `class` members are private by default. Either keyword can use the other's defaults.
Q: Why pass a larger struct as `const T&`?
A: To avoid copying the whole object on each call while still guaranteeing it is not modified.
Q: Why does `std::cout << point;` fail to compile?
A: The stream operators only know about built-in types. You must print members yourself or define an `operator<<` for your type.

## Exercise
Define a `struct Rectangle` with `width` and `height`. Write functions
`int area(const Rectangle&)`, `int perimeter(const Rectangle&)` and
`bool is_square(const Rectangle&)`. Read a width and height, build the
rectangle, and print all three results.

```cpp starter
#include <iostream>

struct Rectangle {
    int width;
    int height;
};

int area(const Rectangle& r) {
    // width * height
}

int perimeter(const Rectangle& r) {
    // 2 * (width + height)
}

bool is_square(const Rectangle& r) {
    // true only when width == height
}

int main() {
    int width = 0, height = 0;

    // Read both, rejecting non-numeric input with a message and return 1.
    // Build a Rectangle and print area, perimeter and whether it is a square.
    return 0;
}
```

## Common mistakes
- **Using `.` on a pointer.** The compiler suggests `->`.
- **Using `->` on an object.** Use `.`.
- **Returning a pointer to a local struct.** Dangling pointer.
- **Passing a large struct by value** in a loop, causing needless copies.
- **Expecting `struct` to hide its members.** Use `class` for encapsulation.

## Recap
- A struct groups related data; members are public by default.
- `.` for objects, `->` for pointers.
- Prefer brace initialisation `Point p{1, 2};`.
- Pass large structs as `const T&`.
- `std::cout` cannot print your struct without a custom `operator<<`.