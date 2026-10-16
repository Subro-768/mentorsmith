---
id: 13-classes-and-objects
title: Classes and Objects
order: 13
---

## Objectives
- Define a class and distinguish a class from an object.
- Write member functions, including ones defined inside and outside the body.
- Use access specifiers correctly.
- Follow the principle that data should be private with public behaviour.

## Explanation
A **class** is a blueprint; an **object** is one instance built from it. The
class describes what an object *knows* (data members) and what it can *do*
(member functions).

```cpp
class Counter {
public:
    void increment();     // behaviour - public
private:
    int value = 0;        // state - private
};
```

Two forms of member function definition:

```cpp
class Counter {
public:
    void increment() { ++value; }          // inside the body: implicit inline

    void reset();                          // declared here
private:
    int value = 0;
};

void Counter::reset() {                    // outside: use Class::function
    value = 0;
}
```

Short functions defined inside the class body are treated as `inline`. Define
longer ones outside the class so the class stays readable.

**Access specifiers.**

| Specifier | Meaning |
|---|---|
| `public` | Accessible from anywhere |
| `private` | Accessible only within the class (default for `class`) |
| `protected` | Accessible within the class and derived classes (default for `struct`) |

The important design habit: **keep data private and expose behaviour**. This
lets you change the internal representation later without breaking callers,
and it means invalid states cannot be created from outside.

```cpp
class Temperature {
public:
    double celsius() const { return celsius_; }
    void set_celsius(double value);        // validates before storing
private:
    double celsius_ = 0.0;
};
```

Trailing underscores on member names (`celsius_`) are a common convention that
distinguishes members from parameters with the same name.

**`const` on a member function** means it will not modify the object:

```cpp
double celsius() const { return celsius_; }
```

Add `const` wherever possible. It documents intent and lets the compiler catch
mistakes.

**The `this` pointer** inside a method refers to the current object. You rarely
need it explicitly, but it is what makes chaining possible:

```cpp
Counter& bump() { ++value; return *this; }

counter.bump().bump().bump();      // value increased by 3
```

Returning `*this` by reference is what enables the fluent style used by
stream operators and many modern APIs.

**Each object has its own data.** Two `Counter` objects do not share `value`.

## Example
```cpp
#include <iostream>
#include <string>

class Counter {
public:
    void increment() { ++value_; }
    void decrement() {
        if (value_ > 0) --value_;        // guard against going below zero
    }
    int value() const { return value_; } // const: will not modify

    Counter& bump() {                   // returns *this by reference
        ++value_;
        return *this;
    }

    void reset() { value_ = 0; }        // defined outside the class

private:
    int value_ = 0;
};

class Rectangle {
public:
    Rectangle(double width, double height)
        : width_(width), height_(height) {}     // member initialisation list

    double area() const { return width_ * height_; }
    double perimeter() const { return 2.0 * (width_ + height_); }
    bool is_square() const { return width_ == height_; }

    void scale(double factor) {
        width_ *= factor;
        height_ *= factor;
    }

    std::string describe() const {
        return "Rectangle " + std::to_string(area());
    }

private:
    double width_;
    double height_;
};

void Counter::reset() {
    value_ = 0;
}

int main() {
    Counter first;
    Counter second;                    // a separate object with its own value_

    first.increment();
    first.increment();
    first.increment();
    std::cout << "first  = " << first.value() << '\n';
    std::cout << "second = " << second.value() << " (independent)\n";

    first.decrement();
    first.decrement();
    first.decrement();
    std::cout << "after 3 decrements = " << first.value() << " (floored at 0)\n";

    first.bump().bump();
    std::cout << "after chained bumps = " << first.value() << '\n';

    first.reset();
    std::cout << "after reset = " << first.value() << '\n';

    Rectangle rect{4.0, 6.0};
    std::cout << "\narea      = " << rect.area() << '\n';
    std::cout << "perimeter = " << rect.perimeter() << '\n';
    std::cout << "square?   = " << std::boolalpha << rect.is_square() << '\n';
    std::cout << rect.describe() << '\n';

    rect.scale(2.0);
    std::cout << "after scale(2) area = " << rect.area() << '\n';
    return 0;
}
```

## Knowledge checks
Q: What is the difference between a class and an object?
A: The class is the blueprint describing data and behaviour. An object is a concrete instance created from that blueprint, each with its own copy of the data.
Q: Why mark a read-only member function `const`?
A: It promises the function will not modify the object. That documents intent, allows the compiler to catch mistakes, and lets the function be called on const objects.
Q: What is a member initialisation list and why prefer it?
A: The `Field(args)` list after a constructor's signature. It initialises members directly, whereas assigning in the body creates members first and overwrites them.
Q: What does returning `*this` by reference allow?
A: Chaining, so calls like `obj.bump().bump()` work on the same object.

## Exercise
Create a `class Temperature` storing a Celsius value. Provide:

1. a public constructor taking a Celsius value,
2. `celsius() const` and `fahrenheit() const` getters,
3. `set_celsius(double)` with validation that rejects values below absolute zero,
4. a public `describe() const` returning a readable string.

Keep the single field private.

```cpp starter
#include <iostream>
#include <string>

class Temperature {
public:
    // Constructor taking celsius.

    // Getters: celsius(), fahrenheit()

    // set_celsius(double) - reject below -273.15, report via return bool

    // describe() const returning std::string

private:
    double celsius_ = 0.0;
};

int main() {
    Temperature t{25.0};
    std::cout << t.celsius() << " C = " << t.fahrenheit() << " F\n";

    // Try setting an invalid value and report the rejection.
    // Then set a valid one and print the description.
    return 0;
}
```

## Common mistakes
- **Leaving data members public.** Nothing can then guarantee they stay valid.
- **Forgetting `const` on read-only methods.** Prevents calling them on const objects.
- **Using `this->member` when plain `member` works.** Usually a sign the intent is unclear.
- **Shadowing a member with a parameter of the same name.** Initialise with `member_(member)`.
- **Assuming objects share data.** Each instance has its own copy.

## Recap
- A class is a blueprint; objects are instances with independent data.
- Keep data private, expose behaviour.
- Mark read-only member functions `const`.
- Use a member initialisation list in constructors.
- Return `*this` by reference to enable chaining.