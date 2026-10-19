---
id: 04-operators
title: Operators
order: 4
---

## Objectives
- Work with arithmetic, relational, and logical operators.
- Understand integer division versus floating point division.
- Use ternary operators.

## Explanation
Java supports standard arithmetic operators: `+`, `-`, `*`, `/`, `%` (modulo).

**Integer division:**
Dividing two integers truncates the decimal: `7 / 2` is `3`. To get `3.5`, at least one operand must be a floating-point number: `7.0 / 2` or `(double) 7 / 2`.

**Logical Operators:**
- `&&`: Logical AND (short-circuiting)
- `||`: Logical OR (short-circuiting)
- `!`: Logical NOT

**Ternary Operator:**
`condition ? valueIfTrue : valueIfFalse`

## Example
```java
public class Main {
    public static void main(String[] args) {
        int a = 10;
        int b = 3;
        System.out.println(a % b); // 1
        String status = (a > b) ? "greater" : "smaller";
        System.out.println(status);
    }
}
```

## Knowledge checks
Q: What is the result of 9 / 2 in Java?
A: 4, because both operands are integers and the fraction is truncated.
Q: What does the % operator return?
A: The remainder of integer division.
Q: What is short-circuit evaluation in &&?
A: If the left operand is false, the right operand is not evaluated.

## Exercise
Given an integer `score = 75`, use a ternary operator to set `result` to "Pass" if `score >= 50`, else "Fail", then print `result`.

```java starter
public class Main {
    public static void main(String[] args) {
        int score = 75;
        // Use ternary operator to determine Pass or Fail and print it
    }
}
```

## Common mistakes
- Expecting `1 / 2` to yield `0.5` instead of `0`.
- Confusing `=` (assignment) with `==` (comparison).

## Recap
- Integer division truncates towards zero.
- Ternary operator provides inline conditional expressions.
