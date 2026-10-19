---
id: 18-assertions
title: Assertions and Design by Contract
order: 18
tier: advanced
---

## Objectives
- Write an assertion and enable it.
- Say why an assertion is not input validation.
- State a precondition, a postcondition and an invariant.
- Choose between an assertion and an exception.

## Explanation
An assertion states something that must be true at that point. If it is
false the program stops with an `AssertionError`.

```java
assert age >= 0 : "age cannot be negative";
```

- Assertions are **disabled by default**. Run with `java -ea` to enable them, `java -da` to disable them explicitly.
- An assertion is removed entirely when disabled, so nothing the program relies on may live inside one.
- `assert x = 5;` is legal Java and does something else entirely from what it looks like.

Design by contract gives a method three kinds of statement:
- a **precondition** - what the caller must guarantee,
- a **postcondition** - what the method guarantees on return,
- an **invariant** - what must hold between calls.

Use an exception for anything that can legitimately be wrong at runtime
(user input, a network reply). Use an assertion for the programmer's own
assumptions.

## Example
```java
double withdraw(double amount) {
    assert amount > 0 : "amount must be positive";
    assert balance - amount >= 0 : "would overdraw";
    balance -= amount;
    assert balance >= 0 : "postcondition: balance went negative";
    return balance;
}
```

## Knowledge checks
Q: Are assertions enabled by default?
A: No. They are enabled with `-ea` and disabled with `-da`.
Q: Why is an assertion the wrong tool for validating user input?
A: It disappears when assertions are off, so the bad value would go unchecked in production.
Q: What is the difference between a precondition and a postcondition?
A: A precondition is what the caller must ensure before the call; a postcondition is what the method guarantees after it.
Q: What does `assert x = 5;` do?
A: It assigns 5 to x and asserts the (non-boolean) value, which is a bug rather than a check.
Q: When would you use an exception instead of an assertion?
A: When the condition can genuinely be wrong at run time - bad input, a missing file, a failed network call.

## Exercise
Write a class `BankAccount` with a `withdraw` method. Add an assertion for the precondition (a positive amount), one for the account (sufficient balance) and one for the postcondition (the balance is still non-negative). Run the program once with `java -ea` and once without, and explain the difference in what you observe.

```java starter
public class Main {
    // Define BankAccount with withdraw() and its three assertions.

    public static void main(String[] args) {
        // Try to withdraw an invalid amount
    }
}
```

## Common mistakes
- Putting an input check inside an `assert`, so it vanishes in production.
- Assuming a bug cannot reach production because it was tested - it was tested with assertions on.
- Asserting on a value that is also being assigned.

## Recap
- Assertions are off unless you turn them on.
- They document and check the programmer's contract.
- They are not validation; exceptions are.
