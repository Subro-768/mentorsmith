---
id: 18-operator-overloading
title: Operator Overloading
order: 18
tier: advanced
---

## Objectives
- Overload a binary operator as a member function.
- Write a unary operator, and tell pre-increment from post-increment.
- Choose between a member overload and a free function.
- Explain the copy-assignment pitfall.

## Explanation
C++ lets a class decide what `+` means for it. The overload is a function
named `operator` followed by the symbol.

```cpp
class Vec2 {
    double x{}, y{};
public:
    Vec2(double x, double y) : x(x), y(y) {}
    Vec2 operator+(const Vec2& other) const {
        return Vec2(x + other.x, y + other.y);
    }
};
```

- A member overload has the left operand as `*this`, so only the right operand converts implicitly. A free function takes both, so either side can.
- `operator++()` returns a reference to the modified object; `operator++(int)` returns a copy of the old value. Getting them the wrong way round is a real bug.
- An operator that takes its parameter by value and returns by value copies the object twice, and `operator=` can end up calling itself. Take the parameter by const reference and return `*this` by reference.
- `explicit operator double()` is better than an implicit one, which quietly creates ambiguous overload sets.

## Example
```cpp
#include <iostream>

class Vec2 {
    double x_, y_;
public:
    Vec2(double x, double y) : x_(x), y_(y) {}
    double x() const { return x_; }
    double y() const { return y_; }
    Vec2 operator+(const Vec2& other) const {
        return Vec2(x_ + other.x_, y_ + other.y_);
    }
    void print() const { std::cout << x_ << "," << y_ << "\n"; }
};

Vec2 operator*(double k, const Vec2& v) {   // free: 2 * v works
    return Vec2(v.x() * k, v.y() * k);
}

int main() {
    Vec2 a{1, 2}, b{3, 4};
    Vec2 c = a + b;
    c.print();
    (2 * a).print();
}
```

## Knowledge checks
Q: How does the compiler pick between two `operator+` overloads?
A: By the types of the operands, applying implicit conversions where needed.
Q: When is a free-function overload better than a member one?
A: When symmetry matters - so the left-hand operand can also convert.
Q: What must post-increment return, and what must pre-increment return?
A: Post-increment returns a copy of the old value; pre-increment returns a reference to the modified object.
Q: Why take the parameter by const reference?
A: To avoid copying the object, and to stop the operator modifying it.
Q: What is wrong with `Vec2& operator=(const Vec2& o) { x = o.x; y = o.y; return *this; }`?
A: Nothing - that is the correct form. The wrong form returns by value and takes by value.
Q: Which operators cannot be overloaded?
A: `&&`, `||`, `,` and `.`.

## Exercise
Write a `Complex` class with `+`, `-`, `operator*` for complex times complex, `operator==` and `operator<<` for printing. Then add a free function so that `2 * c` compiles, and explain why that needs to be a free function.

```cpp starter
#include <iostream>

class Complex {
    // Real and imaginary parts, the operators above, and a print helper.
};

int main() {
    // Complex a(1, 2), b(3, 4); print a + b and 2 * a
}
```

## Common mistakes
- Forgetting `const` on the parameters, so the operator cannot be used with a const object.
- Returning a reference to a local temporary.
- Mixing up pre- and post-increment.
- Writing `operator=` when the compiler's own was already correct.

## Recap
- An overload is a function with a special name.
- Member or free: the free form allows conversion on the left.
- `const` reference in, `*this` by reference out.
