---
id: 18-operator-overloading
title: Operator Overloading for Your Own Types
order: 18
lesson_id: 18-operator-overloading
summary: Overloading unary and binary operators as member functions, the copy-assignment pitfall, and conversion operators.
tags: operator-overloading, unary, binary, copy-assignment, implicit-conversion
source_book: Object Oriented Programming with C++
source_author: Dhamodharan G, Balasubramanian, Priya K
source_chapter: 7
source_page: 38
---

# 18. Operator Overloading for Your Own Types

C++ lets a class say what `+` means for it. The overload is an ordinary
function whose name is `operator` followed by the symbol.

```cpp
class Vec2 {
    double x{}, y{};
public:
    Vec2(double x, double y) : x(x), y(y) {}

    Vec2 operator+(const Vec2& other) const {
        return Vec2(x + other.x, y + other.y);
    }
};

Vec2 a{1, 2}, b{3, 4};
Vec2 c = a + b;      // (4, 6)
```

### Member or free function?
A member overload has the left-hand operand as `*this`, so it works on
implicit conversions of the right-hand operand only. A free function takes
both operands as parameters, so either side can convert.

```cpp
Vec2 operator*(double k, const Vec2& v);   // free: 2 * v works
```

Rule of thumb: member for the natural operations on the type, free when
symmetry matters.

### Unary operators
```cpp
Vec2 operator-() const { return Vec2(-x, -y); }   // negation
bool  operator!() const { return x == 0 && y == 0; }
Vec2& operator++();    // pre-increment: modifies in place
Vec2  operator++(int); // post-increment: returns the old value
```

The pre/post difference is not a matter of taste: `++v` must return a
reference to the modified object, while `v++` must return a copy of the old
value. Getting these the wrong way round is a real bug.

### The copy-assignment pitfall
An operator that takes its parameter **by value** and returns **by value**
silently copies the object twice, and the copy-assignment operator can end
up calling itself:

```cpp
Vec2& operator=(const Vec2& other) {   // correct
    x = other.x; y = other.y;
    return *this;
}
```

Returning `*this` by reference is the convention; the compiler-generated
copy assignment already does the right thing, so the common case is to
delete it rather than write it.

### Conversion operators
```cpp
explicit operator double() const { return length(); }
```

Mark it `explicit` unless you genuinely want the class to convert silently.
An implicit conversion operator is one of the easiest ways to create an
ambiguous overload set.

### The rules worth knowing
- You cannot overload `&&`, `||`, `,` or `.`.
- You cannot create a new operator; you can only give meaning to the
  existing ones.
- `operator[]`, `operator()` and `operator->` are the ones that make a
  class behave like a built-in.
- At least one operand of a binary operator must be your class.

### Common mistakes
- Forgetting `const` on the parameters, so the operator cannot be used with
  a `const` object.
- Returning a reference to a local temporary.
- Mixing up pre- and post-increment semantics.
- Writing `operator=` when the default one was fine, and introducing a
  self-assignment bug.

### Review questions
1. How does the compiler decide which `operator+` to use when the
   operands have different types?
2. When is a free-function overload better than a member overload?
3. What must a post-increment operator return, and what must a
   pre-increment operator return?
4. Why is `operator=` returning `*this` by reference the convention?
5. What goes wrong if an operator takes its parameter by value?
6. Why is `explicit` recommended on a conversion operator?
7. Which operators cannot be overloaded at all?
8. How do you make a class indexable with `[]`?

### Practice
Write a `Complex` class with `+`, `-`, `operator*` (complex times complex),
`operator==` and `operator<<` for printing. Then write `2 * c` as a free
function to show why a free overload can extend the left-hand side.
