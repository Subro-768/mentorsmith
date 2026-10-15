---
id: 14-constructors-encapsulation
title: Constructors and Encapsulation
order: 14
---

## Objectives
- Write default, parameterised, copy and move constructors.
- Follow the rule of zero, three or five.
- Encapsulate data behind a controlled interface.
- Return a usable object from every constructor.

## Explanation
A constructor initialises an object when it is created. C++ distinguishes
several kinds.

**Default constructor** takes no arguments:

```cpp
class Counter {
public:
    Counter() : value_(0) {}                 // always leave it in a valid state
private:
    int value_ = 0;
};
```

**Parameterised constructor** takes arguments. Prefer a *member initialisation
list* over assigning in the body:

```cpp
class Rectangle {
public:
    Rectangle(double width, double height)
        : width_(width), height_(height) {}   // initialises directly
private:
    double width_;
    double height_;
};
```

```cpp
Rectangle bad(3.0, 4.0) {
    width_ = 3.0;       // width_ was default-constructed first,
    height_ = 4.0;      // then overwritten - wasteful, and wrong for
}                       // types that cannot be default-constructed
```

**Default arguments** can stand in for an overloaded constructor:

```cpp
class Temperature {
public:
    explicit Temperature(double celsius = 20.0);
    //             ^ explicit stops an implicit double -> Temperature conversion
};
```

Prefer `explicit` on single-argument constructors. Without it, a plain `double`
can silently become a `Temperature`, hiding bugs.

**Copy constructor** builds a new object from an existing one. The compiler
generates one if you do not write it, but write it explicitly if the class owns
a raw pointer or a resource:

```cpp
Rectangle(const Rectangle& other) = default;   // often this is correct
```

**Move constructor** transfers ownership instead of copying:

```cpp
Rectangle(Rectangle&& other) noexcept;         // rvalue reference
```

**Destructor** releases resources:

```cpp
~Rectangle() { /* clean up */ }
```

Prefer `= default` over writing a copy or move constructor by hand unless you
genuinely need custom behaviour. A hand-written copy constructor that forgets
the copy assignment operator causes *partial copying*: copy construction works,
but assignment leaves the two objects sharing state.

**The rule of zero / three / five.** If you declare any of destructor, copy
constructor, copy assignment or move operations, you are likely managing a raw
resource and should declare the rest. The far better answer is the **rule of
zero**: hold no raw resources at all.

```cpp
class Report {                 // rule of zero - nothing to declare
    std::string title_;
    std::vector<int> data_;    // these manage themselves
};
```

**Encapsulation** means keeping the internal representation private and
publishing an interface that protects it. Add a setter with validation and the
field can later change type without touching callers:

```cpp
class BankAccount {
public:
    bool deposit(double amount) {                 // validates
        if (amount <= 0.0) return false;
        balance_ += amount;
        return true;
    }
    bool withdraw(double amount) {
        if (amount <= 0.0 || amount > balance_) return false;   // prevents overdraft
        balance_ -= amount;
        return true;
    }
    double balance() const { return balance_; }
private:
    double balance_ = 0.0;
};
```

## Example
```cpp
#include <iostream>
#include <string>
#include <utility>
#include <vector>

class Counter {
public:
    Counter() : value_(0) {}                    // never leave an invalid state
    explicit Counter(int start) : value_(start) {}

    void increment() { ++value_; }
    int value() const { return value_; }

    Counter(const Counter&) = default;          // rule of five, explicitly
    Counter& operator=(const Counter&) = default;
    Counter(Counter&&) noexcept = default;
    Counter& operator=(Counter&&) noexcept = default;
    ~Counter() = default;

private:
    int value_ = 0;
};

class Rectangle {
public:
    Rectangle(double width = 0.0, double height = 0.0)
        : width_(width), height_(height) {}

    double area() const { return width_ * height_; }

    bool is_valid() const { return width_ > 0.0 && height_ > 0.0; }

    Rectangle scaled(double factor) const {
        return Rectangle{width_ * factor, height_ * factor};  // rule of zero
    }

    std::string describe() const {
        return "Rectangle " + std::to_string(width_) + "x"
             + std::to_string(height_) + " area " + std::to_string(area());
    }

private:
    double width_;
    double height_;
};

class BankAccount {
public:
    explicit BankAccount(double opening_balance = 0.0) : balance_(opening_balance) {}

    bool deposit(double amount) {
        if (amount <= 0.0) return false;
        balance_ += amount;
        return true;
    }

    bool withdraw(double amount) {
        if (amount <= 0.0 || amount > balance_) return false;
        balance_ -= amount;
        return true;
    }

    double balance() const { return balance_; }

private:
    double balance_;
};

int main() {
    Counter zero;
    Counter from_value{10};
    std::cout << "default ctor     = " << zero.value() << '\n';
    std::cout << "parameterised    = " << from_value.value() << '\n';

    Counter copied = from_value;             // copy construction
    copied.increment();
    std::cout << "after copy+incr   = " << copied.value()
              << " (original still " << from_value.value() << ")\n";

    Counter moved = std::move(from_value);  // move construction
    std::cout << "moved-from value = " << from_value.value() << " (left in valid state)\n";

    const Rectangle rect{3.0, 4.0};
    std::cout << "\n" << rect.describe() << '\n';
    std::cout << "valid?           = " << std::boolalpha << rect.is_valid() << '\n';
    std::cout << "scaled x2        = " << rect.scaled(2.0).describe() << '\n';
    std::cout << "zero by default  = " << Rectangle{}.describe() << '\n';

    BankAccount account{100.0};
    std::cout << "\nbalance          = " << account.balance() << '\n';
    std::cout << "deposit 50 ok?   = " << account.deposit(50.0) << '\n';
    std::cout << "withdraw 500?    = " << account.withdraw(500.0) << " (rejected)\n";
    std::cout << "withdraw 50 ok?  = " << account.withdraw(50.0) << '\n';
    std::cout << "final balance    = " << account.balance() << '\n';
    return 0;
}
```

## Knowledge checks
Q: Why prefer a member initialisation list over assigning members in the constructor body?
A: It initialises members directly rather than default-constructing them and then overwriting. It is also the only option for members that cannot be default-constructed, such as `const` or reference members.
Q: What does `explicit` do on a single-argument constructor?
A: It prevents implicit conversion from that argument's type. It turns a silent, easy-to-miss conversion into a compile error.
Q: What is the rule of zero?
A: Declare no destructor, copy or move operations at all — because the class holds no raw resources. This is the best case.
Q: Why does a hand-written copy constructor risk partial copying?
A: If you write the copy constructor but leave copy assignment as the compiler default, the two can behave differently, so objects end up sharing or inconsistently duplicating state.
Q: How does encapsulation protect future changes?
A: If the internal representation is private, you can change it without altering the public interface, so existing callers keep working.

## Exercise
Write a `class Bookshelf` with a private `std::vector<std::string>` of titles,
an `explicit` constructor taking an initial vector, `add_book(const
std::string&)`, `contains(const std::string&) const`, `size() const`, and
`titles() const` returning a `const std::vector<std::string>&`. Add a
constructor that rejects an empty title. Note that holding a vector instead of
a raw pointer means you need no destructor, copy or move operations at all.

```cpp starter
#include <iostream>
#include <string>
#include <vector>

class Bookshelf {
public:
    // explicit constructor taking std::vector<std::string>
    // add_book(const std::string&) - reject empty titles, return bool
    // contains(const std::string&) const
    // size() const
    // titles() const returning const std::vector<std::string>&

private:
    std::vector<std::string> books_;
};

int main() {
    // Build a shelf, add several books (including one empty title to be
    // rejected), print size, print contents, check contains for a few titles.
    return 0;
}
```

## Common mistakes
- **Leaving a constructor able to create an invalid object.** Validate before assigning.
- **Omitting `explicit` on a one-argument constructor.** Allows surprising implicit conversions.
- **Assigning members in the constructor body.** Use the initialisation list.
- **Forgetting the destructor when owning a raw pointer.** Memory leaks. Better: hold a container instead.
- **Declaring a copy constructor but not copy assignment.** Causes partial copying.

## Recap
- Default, parameterised, copy and move constructors all have distinct roles.
- Use a member initialisation list; mark single-argument constructors `explicit`.
- Every constructor should leave the object in a valid state.
- Rule of zero is best; three or five only when you own raw resources.
- Encapsulation keeps the interface stable while the internals evolve.