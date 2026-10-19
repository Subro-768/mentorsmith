---
id: 14-interfaces
title: Interfaces, Multiple Inheritance & Default Methods
order: 14
lesson_id: 14-interfaces
summary: What an interface promises, how a class implements several of them, and why a default method still needs a conflict rule.
tags: interfaces, multiple-inheritance, default-methods, abstract
source_book: Programming with Java: A Primer
source_author: E. Balagurusamy
source_chapter: 10
source_page: 181
---

# 14. Interfaces, Multiple Inheritance & Default Methods

A class inherits *state* - fields and implementations. An interface inherits
nothing; it **promises** that a class can do something. That is why a class
can implement several interfaces while extending only one class: the
ambiguity of inheriting state from two parents never arises, because the
interfaces carry no state.

```java
interface Printable {
    void print();                       // implicitly public abstract
    default String describe() {         // a shared, optional implementation
        return "printable";
    }
}

class Invoice implements Printable {
    @Override public void print() { System.out.println("Invoice"); }
}
```

### An interface is a contract
Every method in an interface is `public` and `abstract` unless it is given a
body (`default` or `static`). A class that implements an interface must
implement every abstract method, or declare itself `abstract`.

```java
interface A { void go(); }
interface B { void go(); }

class Both implements A, B {
    public void go() { }    // one method satisfies both
}
```

That last example is the whole point: a class that inherits from two
unrelated classes would have to choose which `go()` to inherit, or have both
and be unable to tell them apart. With interfaces there is nothing to
choose - the class supplies the method.

### Fields in an interface are constants
```java
interface Config { int MAX = 100; }
```
`MAX` is `public static final` whatever it looks like. It belongs to the
interface, not to any implementing class, so it cannot be used to carry
per-object state.

### Default and static methods
`default` gives an interface a body, so a class implementing several
interfaces does not have to write the same method twice:

```java
interface Named  { default String label() { return "item"; } }
interface Priced { default String label() { return "priced item"; } }

class Product implements Named, Priced {
    @Override public String label() { return Named.super.label(); }
}
```

When two interfaces both supply a `default` method, the class **must**
resolve the clash itself - either by overriding it, or by naming the winner
with `InterfaceName.super.method()`. Left unresolved, it is a compile error.
A `static` method in an interface is not inherited at all and is called as
`InterfaceName.method()`.

### `instanceof` and pattern matching
```java
if (obj instanceof Printable p) {   // Java 16+
    p.print();
}
```
The pattern form avoids the separate cast that used to follow every
`instanceof`, and the compiler proves the cast is safe.

### Common mistakes
- Forgetting `public` on the implementing method: it does not widen
  automatically, so the class fails to compile.
- Expecting an interface to hold state - it cannot.
- Adding a `default` method to an interface that is already implemented
  elsewhere: existing implementations keep compiling, but two interfaces
  offering the same default now clash.
- Assuming a class can extend two classes. It cannot.

### Review questions
1. Why can a class implement several interfaces but extend only one class?
2. What are the access defaults for a method declared in an interface? What
   about a `default` method?
3. A field is declared in an interface. Which class does it belong to, and
   can it be changed per object?
4. Two interfaces both define `default String label()`. A class implements
   both without overriding `label()`. What happens, and what are the two
   ways to fix it?
5. How does a `default` method differ from a `static` method in an
   interface, with respect to inheritance and how it is called?
6. What does `Named.super.label()` do, and when is it required?
7. How does the pattern form of `instanceof` remove a common source of
   runtime errors?
8. A class implements an interface but omits one of its abstract methods.
   What happens at compile time, and what are the two ways out?

### Practice
Define an interface `Playable` with a `play()` method and a `default`
method `describe()` that returns "playing a track". Implement it in a class
`Song`. Then define a second interface `Recordable` with its own
`describe()` default, implement both in a class `StudioTrack`, and resolve
the conflict using `InterfaceName.super.method()`.
