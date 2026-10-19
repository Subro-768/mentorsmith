---
id: 19-virtual-functions
title: Virtual Functions, Dynamic Binding & Pure Virtual Classes
order: 19
lesson_id: 19-virtual-functions
summary: How a virtual function changes which body runs, why the destructor must be virtual, and how an abstract class is built from pure virtual functions.
tags: virtual, dynamic-binding, abstract-class, pure-virtual, vtable
source_book: Object Oriented Programming with C++
source_author: Dhamodharan G, Balasubramanian, Priya K
source_chapter: 9
source_page: 51
---

# 19. Virtual Functions, Dynamic Binding & Pure Virtual Classes

A **non-virtual** function is chosen by the compiler from the static type of
the expression. A **virtual** function is chosen at run time from the
object's real type. That single difference is the whole of dynamic
dispatch.

```cpp
class Base {
public:
    virtual void speak() const { std::cout << "base\n"; }
    void fixed()  const { std::cout << "base\n"; }
};

class Derived : public Base {
public:
    void speak() const override { std::cout << "derived\n"; }
    void fixed()  const { std::cout << "derived\n"; }
};

Base& ref = Derived{};
ref.speak();   // "derived"  - virtual
ref.fixed();   // "base"     - not virtual
```

`override` on the derived declaration is not required, but it is worth
writing: the compiler then rejects a signature that does not actually
override anything, which catches a typo that would otherwise quietly
create a new function.

### How the dispatch works
The compiler gives a class with virtual functions a **vtable** - a table of
function pointers - and every object with such a class gets a hidden
pointer to it. A virtual call becomes: read the object's vtable, take the
slot for this function, call it. The class is not consulted; the object
decides.

That pointer is one more thing every object carries, which is why classes
without virtual functions are slightly smaller and slightly faster.

### The constructor/destructor rule
During construction and destruction, C++ calls the version belonging to the
class **currently being constructed or destroyed**, not the most-derived
one. Calling a virtual function from a constructor therefore runs the
base's version - a well-known source of surprise.

### The destructor must be virtual
```cpp
Base* p = new Derived{};
delete p;     // wrong without a virtual destructor: Derived's destructor never runs
```

Declare the base destructor `virtual` (or `virtual ~Base() = default;`)
whenever the class is meant to be used polymorphically. Since C++11, an
inherited destructor is implicitly virtual, so `~Derived()` alone already
makes the base's destructor virtual - but writing it out in the base is
clearer.

### Pure virtual functions and abstract classes
A pure virtual function has no body and makes the class abstract:

```cpp
class Shape {
public:
    virtual double area() const = 0;     // pure virtual
    virtual ~Shape() = default;
};
```

An abstract class cannot be instantiated. It exists to be derived from, and
it can hold data and non-virtual methods as well. If a derived class fails
to implement every pure virtual function, it is abstract too.

This gives the classic "template method" shape: the base fixes the
algorithm, the derived classes supply the steps.

```cpp
class Shape {
public:
    void draw() const {          // not virtual: the algorithm is fixed
        std::cout << "area = " << area() << "\n";   // virtual: the step is not
    }
    virtual double area() const = 0;
};
```

### Common mistakes
- Forgetting `virtual` on the base function, and wondering why the derived
  version is ignored.
- Forgetting `virtual` on the base destructor, and leaking the derived
  object's members.
- Calling a virtual function from a constructor.
- Overriding with a different signature, which creates an overload instead
  and leaves the base's version in place.
- Hiding a base function with the same name but a different parameter list.

### Review questions
1. What does `virtual` change about how a call is resolved?
2. Why does a virtual call during construction not reach the derived
   class's version?
3. What is a vtable, and what does each object carry when its class has
   virtual functions?
4. Why must a base destructor be virtual when objects are deleted through a
   base pointer?
5. What does `= 0` mean in a function declaration, and what is it called?
6. Can an abstract class have data members and ordinary methods?
7. What is the "template method" pattern, and which part is virtual?
8. A derived class declares a function with the same name as a base
   function but different parameters. What happens to the base's function?

### Practice
Build a small hierarchy: an abstract `Playable` with a pure virtual
`play()` and a concrete `describe()` that calls `play()`. Derive `Song`
and `Podcast` from it. Store them in `std::vector<std::unique_ptr<Playable>>`
and call `describe()` on each. Then make `play()` non-virtual in the base
and observe what changes.
