---
id: 02-variables-and-types
title: Variables and Types
order: 2
---

## Objectives
- Declare primitive and reference variables.
- Learn int, double, boolean, char, and String.
- Understand the `final` keyword and type casting.

## Explanation
Java is strongly typed. Primitive types include `int` (32-bit integer), `double` (64-bit floating point), `boolean` (`true` or `false`), and `char` (single Unicode character in single quotes).

`String` is a reference type representing immutable text.

Use `final` before a variable type to make it an immutable constant:
`final double PI = 3.14159;`

Type casting allows converting between types:
- Widening (automatic): `int` to `double`
- Narrowing (explicit cast): `(int) 3.99` evaluates to `3`

## Example
```java
public class Main {
    public static void main(String[] args) {
        int count = 5;
        double price = 9.99;
        boolean available = true;
        String item = "Book";
        System.out.println(item + " costs $" + price);
    }
}
```

## Knowledge checks
Q: What is the difference between float and double in Java?
A: double has 64 bits of precision while float has 32 bits; double is the default literal type.
Q: How do you declare a constant variable in Java?
A: Prefix the declaration with the final keyword.
Q: What happens when you cast (int) 7.8?
A: It truncates the decimal part, resulting in 7.

## Exercise
Declare an integer `quantity = 3` and a double `unitPrice = 4.5`. Compute the total cost and print it.

```java starter
public class Main {
    public static void main(String[] args) {
        int quantity = 3;
        double unitPrice = 4.5;
        // Compute and print total
    }
}
```

## Common mistakes
- Assigning double values directly to int without an explicit cast.
- Using `==` to compare Strings instead of `.equals()`.

## Recap
- Primitive types store raw values (`int`, `double`, `boolean`, `char`).
- `final` creates immutable constants.
