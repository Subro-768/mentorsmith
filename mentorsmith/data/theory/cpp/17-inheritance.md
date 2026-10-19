---
id: 17-inheritance
title: Inheritance & the Shapes It Can Take
order: 17
lesson_id: 17-inheritance
summary: Deriving a class, constructor order, access under inheritance, and the five shapes - single, multilevel, multiple, hierarchical and hybrid.
tags: inheritance, derived-class, virtual, access, oop
source_book: Object Oriented Programming with C++
source_author: Dhamodharan G, Balasubramanian, Priya K
source_chapter: 8
source_page: 41
---

# 17. Inheritance & the Shapes It Can Take

Inheritance reuses a class by deriving a new one from it. The derived class
gets the base's data and behaviour, and can add its own or override what it
inherits.

```cpp
class Animal {
protected:
    std::string name;
public:
    explicit Animal(std::string n) : name(std::move(n)) {}
    virtual void speak() const { std::cout << "...\n"; }
    virtual ~Animal() = default;      // see the next chapter
};

class Dog : public Animal {
public:
    explicit Dog(std::string n) : Animal(std::move(n)) {}
    void speak() const override { std::cout << name << " says woof\n"; }
};
```

### Construction order
The base class is constructed **before** the derived class's body runs, so
the base's members are ready when the derived constructor executes. The
derived constructor's initialiser list is where you pass what the base
needs:

```cpp
Dog(std::string n) : Animal(std::move(n)) {}   // base first, always
```

Skipping the base initialiser when the base has no default constructor is a
compile error - a base is never left uninitialised.

### Destructors run in reverse
Members are destroyed in reverse order of construction, and the derived
destructor runs **before** the base destructor. A derived destructor that
fails to call the base's leaves the base's resources unreleased.

### Access under inheritance
| Base member | Derived class | Outside |
|---|---|---|
| `private` | not accessible | not accessible |
| `protected` | accessible | not accessible |
| `public` | accessible | accessible |

`private` really is invisible to the derived class, which is why the base
often offers a `protected` accessor instead.

### The five shapes
- **Single**: one base, one derived.
- **Multilevel**: `C : B : A` - `C` gets `A`'s members through `B`.
- **Multiple**: two bases. Legal in C++, and the reason it needs
  disambiguation.
- **Hierarchical**: several derived classes share one base.
- **Hybrid**: multiple plus multilevel.

```cpp
class Printable { public: virtual void print() const = 0; };
class Serializable { public: virtual std::string serialise() const = 0; };

class Report : public Printable, public Serializable {
public:
    void print() const override { }
    std::string serialise() const override { return "{}"; }
};
```

### The diamond problem
When two paths reach the same base, the base is constructed **twice**, and
an ambiguous reference to it appears:

```cpp
class B { public: int x = 1; };
class D1 : public B { };
class D2 : public B { };
class D  : public D1, public D2 { };
// d.B::x is ambiguous; d.x is an error
```

Virtual inheritance makes the shared base exist once:

```cpp
class D1 : virtual public B { };
class D2 : virtual public B { };
```

### Common mistakes
- Forgetting `virtual` on the base destructor: deleting through a base
  pointer then runs the wrong destructor, and the derived object's members
  are never released.
- Omitting the base from the initialiser list when the base has no default
  constructor.
- Accessing a `private` base member from a derived class - it is not
  inherited, only the base can see it.
- Multiple inheritance without virtual bases, then wondering why a member
  is ambiguous.

### Review questions
1. In what order are the base and derived constructors run, and the
   destructors?
2. Why is a base member marked `protected` rather than `public` when only
   derived classes need it?
3. Which access specifier keeps a member completely hidden from derived
   classes?
4. Name the five inheritance shapes and sketch each in one line.
5. What problem does virtual inheritance solve, and what is the cost?
6. Why must the base class destructor be `virtual`?
7. A derived class has a member with the same name as a base member. Which
   one is used, and how do you name the other explicitly?
8. Why does C++ allow multiple inheritance of classes when most other
   languages do not?

### Practice
Write `Shape` with a `virtual area()` and a `virtual` destructor. Derive
`Circle` and `Rectangle` from it. Store them in a `std::vector<Shape*>`,
delete through the vector, and confirm with a print in each destructor that
the derived destructor really does run.
