---
id: 13-inheritance
title: Inheritance and Method Overriding
order: 13
tier: core
---

## Objectives
- Derive a class from another with `extends`.
- Call the parent's constructor with `super`.
- Override a method and explain how the right version is chosen at run time.
- Tell an override apart from an overload.

## Explanation
A subclass inherits the parent's fields and methods and can add or replace them.

```java
class Animal {
    String name;
    Animal(String name) { this.name = name; }
    void speak() { System.out.println("..."); }
}

class Dog extends Animal {
    Dog(String name) { super(name); }     // parent constructor runs first
    @Override
    void speak() { System.out.println(name + " says woof"); }
}
```

- `super(...)` must be the first statement of a subclass constructor. The parent is always constructed first.
- An override must match the parent's signature exactly. A different parameter list is an **overload**, and the parent's method still exists.
- `static` methods are chosen by the type of the reference at compile time; instance methods are chosen by the actual object at run time. That is why `Animal a = new Dog(); a.speak();` prints "woof".
- Java allows one superclass but many interfaces - see the next lesson.

## Example
```java
public class Main {
    public static void main(String[] args) {
        Animal[] animals = { new Dog("Rex"), new Cat("Mia") };
        for (Animal a : animals) {
            a.speak();     // each object picks its own version
        }
    }
}
```

## Knowledge checks
Q: What must be the first statement in a subclass constructor?
A: A call to the superclass constructor, `super(...)`, if one is needed at all.
Q: A subclass declares `void speak(String to)` while the parent has `void speak()`. Is it an override?
A: No. It is an overload - the signatures differ - so the parent's `speak()` still exists separately.
Q: Which version of a method runs when the reference is of the parent's type but the object is of the child's type?
A: For an instance method, the child's version. For a `static` method, the parent's version, because static methods are bound at compile time.
Q: Why can a class extend only one class but implement many interfaces?
A: Extending brings data along, and inheriting data from two parents is ambiguous. Interfaces carry no state, so several of them cause no conflict.

## Exercise
Create a class `Shape` with a `name` field and a method `describe()` that prints the name. Create a subclass `Circle` that adds a `radius` and overrides `describe()` to also print the radius. Create a second subclass `Square` the same way. Store a `Shape`, a `Circle` and a `Square` in an array and call `describe()` on each.

```java starter
public class Main {
    // Define Shape, then Circle and Square as subclasses of it.

    public static void main(String[] args) {
        // Put one of each into a Shape[] and call describe() on each.
    }
}
```

## Common mistakes
- Forgetting `super()` when the parent has no no-argument constructor - it will not compile.
- Calling an overridable method from a constructor: the child's version runs before the child's fields are set, so it sees zeros.
- Assuming a field is polymorphic. Fields always come from the type of the reference.

## Recap
- `extends` inherits; `super` reaches the parent.
- An override matches the signature exactly; an overload does not.
- Instance methods dispatch on the object, `static` methods on the reference.
