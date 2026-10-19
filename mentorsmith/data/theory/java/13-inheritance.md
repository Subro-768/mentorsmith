---
id: 13-inheritance
title: Inheritance, Overriding & the `super` Call
order: 13
lesson_id: 13-inheritance
summary: Extending classes, constructor chaining, method overriding, and the difference between static hiding and dynamic binding.
tags: inheritance, extends, super, overriding, polymorphism
source_book: Programming with Java: A Primer
source_author: E. Balagurusamy
source_chapter: 8.11
source_page: 137
---

# 13. Inheritance, Overriding & the `super` Call

Inheritance lets a new class say "I am one of those, plus this". The subclass
gets the parent's fields and methods, and can replace the ones it wants to
behave differently.

```java
class Animal {
    String name;
    Animal(String name) { this.name = name; }
    void speak() { System.out.println("..."); }
}

class Dog extends Animal {
    Dog(String name) { super(name); }   // the parent's constructor runs first
    @Override
    void speak() { System.out.println(name + " says woof"); }
}
```

### Constructor order is fixed
`super(...)` must be the **first statement** of a subclass constructor. The
parent's constructor always runs before the subclass body, so a parent's
fields are already set when the subclass constructor continues. A subclass
that declares no constructor at all gets a default one that calls
`super()` - which is why a parent with no no-argument constructor makes the
subclass fail to compile unless it passes arguments up.

### Overriding needs a matching signature
An override has to match the parent's method exactly: same name, same
parameter types, same return type. Changing a parameter type creates an
**overload**, not an override, and the parent's version is still there.

```java
void speak()          // overrides Animal.speak()
void speak(String to) // a new, separate method - this is an overload
```

The `@Override` annotation is not required, but it is worth writing anyway:
the compiler then rejects a signature that does not actually override
anything, which catches a typo that would otherwise silently create a second
method.

### Static binding vs dynamic binding
This is the part that catches people out.

| | resolved at |
|---|---|
| `static` methods | compile time, by the **type of the reference** |
| instance methods | run time, by the **actual object** |

```java
Animal a = new Dog();
a.speak();        // "woof"  - the object is a Dog
Animal.speak();   // whatever Animal's static version does - the reference is an Animal
```

The same split applies to `private` methods (which cannot be overridden at
all, only hidden) and to fields, which are never polymorphic: a field is
always read from the type of the reference.

### The three shapes of inheritance
- **Single**: one parent.
- **Multilevel**: `C extends B extends A` - `C` inherits from `B`, not
  directly from `A`, though it gets `A`'s members through `B`.
- **Hierarchical**: several children share one parent.

Java has no multiple inheritance of classes. When a class needs behaviour
from two unrelated parents, that is what interfaces are for - see the next
chapter.

### Common mistakes
- Calling an overridable method from a constructor: the subclass override
  runs before the subclass's own fields are initialised, so it sees zeros.
- Forgetting `super()` in a parent with only a parameterised constructor.
- Assuming an override changes the parent's behaviour for existing objects -
  it does not; the parent's method still exists and is still called on
  parent-typed references.

### Review questions
1. Why must `super(...)` be the first statement in a subclass constructor,
   and what breaks if it is not?
2. A parent class has only `Parent(int n)`. What compile error does a
   subclass with no constructor produce, and why?
3. Give a parent method and a child method that have the same name but
   different parameter types. Is the child's an override?
4. A variable is declared as `Animal a = new Dog()`. Which version of a
   `static` method runs for `a.speak()`? Which for `a.instanceMethod()`?
   Why the difference?
5. Why is a field never polymorphic, even when the method that uses it is?
6. A constructor calls a method that the subclass overrides. What state does
   the override see, and why is that a problem?
7. Java has no multiple inheritance of classes. What problem does that
   solve, and what mechanism exists instead?
8. In `class C extends B extends A`, is `C` a subclass of `A`? Does `C`
   inherit `A`'s methods directly or through `B`?

### Practice
Write a `Shape` class with a `name` field and a `describe()` method that
prints the name. Write a `Circle` subclass that adds a `radius` and
overrides `describe()` to include it. Then write a `Square` subclass. Put
them in an array of `Shape` and call `describe()` on each - what does the
output show about when the override is chosen?
