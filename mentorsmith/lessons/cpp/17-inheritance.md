---
id: 17-inheritance
title: Inheritance and Derived Classes
order: 17
tier: core
---

## Objectives
- Derive a class with `public Base`.
- Pass what the base needs through the constructor's initialiser list.
- Say which base members a derived class can reach.
- Name the five shapes of inheritance and the diamond problem.

## Explanation
Inheritance reuses a class by deriving a new one from it.

```cpp
class Animal {
protected:
    std::string name;
public:
    explicit Animal(std::string n) : name(std::move(n)) {}
    virtual void speak() const { std::cout << "...\n"; }
    virtual ~Animal() = default;
};

class Dog : public Animal {
public:
    explicit Dog(std::string n) : Animal(std::move(n)) {}
    void speak() const override { std::cout << name << " says woof\n"; }
};
```

- The base is constructed **before** the derived constructor's body runs, and the derived destructor runs **before** the base's.
- `private` base members are not visible to the derived class; `protected` ones are.
- The shapes are single, multilevel, multiple, hierarchical and hybrid.
- The diamond problem: two paths to one base construct it twice and make the base ambiguous. `virtual` inheritance fixes it.

## Example
```cpp
#include <iostream>
#include <string>

class Printable    { public: virtual void print() const = 0; };
class Serializable { public: virtual std::string serialise() const = 0; };

class Report : public Printable, public Serializable {
public:
    void print() const override { std::cout << "report\n"; }
    std::string serialise() const override { return "{}"; }
};

int main() {
    Report r;
    r.print();
    std::cout << r.serialise() << "\n";
}
```

## Knowledge checks
Q: In what order are the base and derived constructors run?
A: The base first, always. The destructors run in the opposite order.
Q: Why is a base member often `protected` rather than `public`?
A: So only the class and its derived classes can reach it, not the whole program.
Q: Which access specifier hides a member from derived classes entirely?
A: `private`.
Q: What is the diamond problem?
A: A class derived from two classes that share a base gets that base constructed twice, and referring to its members is ambiguous.
Q: How do you fix the diamond problem?
A: Derive the intermediate classes from the shared base virtually - `class D1 : virtual public B`.
Q: Why must the base destructor be virtual?
A: So deleting through a base pointer still runs the derived destructor.

## Exercise
Write `Shape` with a `virtual area()` and a `virtual` destructor. Derive `Circle` and `Rectangle` from it, each storing what it needs and overriding `area()`. Put `Circle*` and `Rectangle*` into a `std::vector<Shape*>`, delete through the vector, and print something from each destructor to prove the derived destructors ran.

```cpp starter
#include <iostream>
#include <memory>
#include <vector>

int main() {
    // Define Shape, Circle and Rectangle, then delete them through a vector.
}
```

## Common mistakes
- Forgetting `virtual` on the base destructor, and leaking the derived object's members.
- Omitting the base from the initialiser list when the base has no default constructor.
- Reaching for a `private` base member from a derived class - it is not inherited.

## Recap
- `class D : public B` derives; the initialiser list feeds the base.
- Base first, derived second - and the reverse for destruction.
- `virtual` inheritance removes the diamond.
