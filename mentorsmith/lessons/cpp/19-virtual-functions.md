---
id: 19-virtual-functions
title: Virtual Functions and Abstract Classes
order: 19
tier: advanced
---

## Objectives
- Explain what `virtual` changes about how a call is resolved.
- Say what happens when a virtual function is called from a constructor.
- Write a pure virtual function and an abstract class.
- Use the template-method shape: a fixed algorithm with a replaceable step.

## Explanation
A non-virtual function is chosen by the compiler from the static type of the
expression. A virtual function is chosen at run time from the object's real
type. That is dynamic dispatch.

```cpp
Base& ref = Derived{};
ref.speak();   // the derived version, if speak() is virtual
ref.fixed();   // the base version - not virtual
```

- The class with virtual functions gets a vtable; every object of it carries a pointer to that table. A virtual call reads the object's table, not the class's.
- During construction and destruction, the version belonging to the class currently being built or destroyed is used - so a virtual call from a constructor does **not** reach the derived class.
- `virtual double area() const = 0;` is a pure virtual function. A class with one is abstract and cannot be instantiated; a derived class that leaves one unimplemented is abstract too.
- An abstract class can still hold data and ordinary methods, so it is where a fixed algorithm lives while the steps vary.

## Example
```cpp
#include <iostream>

class Shape {
public:
    void draw() const {                       // fixed algorithm
        std::cout << "area = " << area() << "\n";   // replaceable step
    }
    virtual double area() const = 0;          // pure virtual
    virtual ~Shape() = default;
};

class Square : public Shape {
    double side_;
public:
    explicit Square(double side) : side_(side) {}
    double area() const override { return side_ * side_; }
};

int main() {
    Square s{3};
    s.draw();          // "area = 9"
}
```

## Knowledge checks
Q: What does `virtual` change?
A: Which body runs - the one belonging to the object's real type, decided at run time, rather than the one the compiler picks from the reference's type.
Q: Why does a virtual call from a constructor not reach the derived version?
A: During construction the object is not yet a derived object, so the class currently being constructed decides.
Q: What is a vtable?
A: A table of function pointers per class, with each object holding a pointer to it.
Q: What does `= 0` declare?
A: A pure virtual function, which makes the class abstract.
Q: Can an abstract class have data members?
A: Yes. It can hold state and ordinary methods; it just cannot be instantiated.
Q: How do you declare a destructor virtual?
A: `virtual ~Base() = default;` - and it is needed whenever objects are deleted through a base pointer.

## Exercise
Build an abstract `Playable` with a pure virtual `play()` and a concrete `describe()` that calls `play()`. Derive `Song` and `Podcast` from it. Store them in a `std::vector<std::unique_ptr<Playable>>` and call `describe()` on each. Then make `play()` non-virtual in the base and observe what changes.

```cpp starter
#include <iostream>
#include <memory>
#include <vector>

int main() {
    // Define Playable, Song and Podcast, then describe() each one.
}
```

## Common mistakes
- Forgetting `virtual` on the base function and wondering why the derived version is ignored.
- Forgetting `virtual` on the base destructor, and leaking.
- Overriding with a different signature, which creates an overload and leaves the base's version in place.
- Hiding a base function with the same name but different parameters.

## Recap
- `virtual` moves the decision from compile time to run time.
- A pure virtual function makes the class abstract.
- The base fixes the algorithm; the derived classes supply the steps.
