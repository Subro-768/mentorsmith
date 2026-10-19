---
id: 07-methods
title: Methods
order: 7
---

## Objectives
- Define reusable static methods.
- Pass parameters and return values.
- Method overloading.

## Explanation
Methods group reusable logic under a name:
```java
public static int square(int x) {
    return x * x;
}
```

- If a method returns no value, its return type is `void`.
- Primitive parameters in Java are passed **by value** (a copy is passed).
- **Method Overloading**: You can define multiple methods with the same name if their parameter lists differ in type or count.

## Example
```java
public class Main {
    static int add(int a, int b) {
        return a + b;
    }

    static double add(double a, double b) {
        return a + b;
    }

    public static void main(String[] args) {
        System.out.println(add(2, 3));
        System.out.println(add(2.5, 3.5));
    }
}
```

## Knowledge checks
Q: What allows multiple methods in the same class to share the same name?
A: Method overloading, provided their parameter types or counts differ.
Q: Are arguments in Java passed by reference or by value?
A: Java is strictly pass-by-value (copies of primitives or copies of references are passed).
Q: What keyword indicates a method belongs to the class itself rather than instances?
A: static.

## Exercise
Write a static method `max(int a, int b)` that returns the larger of the two numbers. Call it in `main` with 12 and 25 and print the result.

```java starter
public class Main {
    // Define static int max(int a, int b)

    public static void main(String[] args) {
        // Call max(12, 25) and print result
    }
}
```

## Common mistakes
- Attempting to call non-static methods directly from static `main`.
- Forgetting a `return` statement along a code branch.

## Recap
- Methods modularize and reuse code.
- Overloading differentiates methods by signature.
