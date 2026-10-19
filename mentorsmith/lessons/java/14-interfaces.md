---
id: 14-interfaces
title: Interfaces and Multiple Inheritance
order: 14
tier: core
---

## Objectives
- Declare an interface and implement it.
- Explain how an interface provides multiple inheritance without shared state.
- Use a `default` method and resolve a clash between two of them.
- Use the pattern form of `instanceof`.

## Explanation
An interface is a promise: "a class of this kind can do this". It holds no
data, so a class can implement several of them.

```java
interface Printable {
    void print();
    default String label() { return "printable"; }
}

class Invoice implements Printable {
    @Override public void print() { System.out.println("Invoice"); }
}
```

- Interface methods are `public` and `abstract` unless given a body. Fields in an interface are `public static final` constants.
- A `default` method lets several implementors share an implementation. If two interfaces offer the same `default`, the class must resolve it - by overriding it, or with `Named.super.label()`.
- `static` methods in an interface are not inherited; they are called as `InterfaceName.method()`.
- `if (obj instanceof Printable p) { p.print(); }` binds the pattern in the same statement, so no separate cast is needed.

## Example
```java
interface Named  { default String label() { return "item"; } }
interface Priced { default String label() { return "priced item"; } }

class Product implements Named, Priced {
    @Override public String label() { return Named.super.label(); }
}
```

## Knowledge checks
Q: Why can a class implement several interfaces when it can extend only one class?
A: Interfaces carry no data, so there is no state to inherit ambiguously. A class supplies the implementation instead.
Q: What are the access modifiers on a method declared in an interface?
A: Public and abstract, unless the method has a body (`default` or `static`).
Q: A class implements two interfaces that both define `default String label()`. What must it do?
A: Resolve the conflict - override `label()`, or name the one it wants with `InterfaceName.super.label()`.
Q: What is the difference between a `default` method and a `static` method in an interface?
A: A `default` method is inherited by every implementor and can be overridden; a `static` method is not inherited and is called through the interface name.
Q: Can an interface hold a field that each implementing object can change?
A: No. Its fields are `public static final` constants shared by every implementor.

## Exercise
Define an interface `Playable` with a `play()` method and a `default` method `describe()` returning "playing a track". Implement it in a class `Song`. Then define an interface `Recordable` with its own `describe()` default, implement both in `StudioTrack`, and resolve the conflict using `InterfaceName.super.method()`.

```java starter
public class Main {
    // Define Playable and Recordable, then StudioTrack implementing both.

    public static void main(String[] args) {
        // Create a StudioTrack and print its describe()
    }
}
```

## Common mistakes
- Forgetting `public` on the implementing method - it does not widen automatically, and the class will not compile.
- Expecting an interface to carry per-object state.
- Assuming a `default` method can be added to an interface without any implementor having to think about the clash.

## Recap
- Interfaces promise behaviour and hold no data.
- A class can implement many of them; that is Java's form of multiple inheritance.
- `default` methods share code; a clash must be resolved by the class.
