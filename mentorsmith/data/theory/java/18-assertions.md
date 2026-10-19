---
id: 18-assertions
title: Assertions & Design by Contract
order: 18
lesson_id: 18-assertions
summary: The assert statement, preconditions and postconditions, and why assertions are not input validation.
tags: assertions, design-by-contract, preconditions, testing
source_book: Programming with Java: A Primer
source_author: E. Balagurusamy
source_chapter: 17
source_page: 329
---

# 18. Assertions & Design by Contract

An assertion states something that must be true at a particular point. If it
is false, the program stops immediately with an `AssertionError`, carrying
the message you wrote.

```java
assert age >= 0 : "age cannot be negative";
```

### The rules that matter
- **Assertions are disabled by default.** `java` runs with `-ea` to enable
  them; `java -da` disables them explicitly.
- **An assertion is not an input check.** It is removed entirely when
  disabled, so anything the program *relies* on must not live inside one.
- **Never assert on a value you also assign.** `assert x = 5;` is legal
  Java and does something entirely different from what it looks like.

### Preconditions, postconditions, invariants
Design by contract says a method has an agreement with its callers:

```java
/**
 * @param amount must be positive
 * @return the new balance
 */
double withdraw(double amount) {
    assert amount > 0 : "amount must be positive";
    assert balance - amount >= 0 : "would overdraw";
    balance -= amount;
    assert balance >= 0 : "postcondition: balance went negative";
    return balance;
}
```

- A **precondition** is what the caller must guarantee.
- A **postcondition** is what the method guarantees on return.
- An **invariant** is what must hold between calls - typically checked at
  the end of a method that could break it.

### Where they belong
Use assertions for conditions that are the *programmer's* responsibility:
a value that came from the code above, an internal invariant, a value that
should have been checked before the call. Use an exception for anything that
can legitimately be wrong at runtime - user input, a network reply, a file
that might not be there.

```java
if (amount <= 0) throw new IllegalArgumentException("amount must be positive");
```
That check runs in production. The assertion does not.

### What they are good for
- Catching a wrong assumption early, close to where it was made.
- Documenting the contract in a form the compiler checks.
- Turning on in test runs only, where you want every invariant enforced.

### Common mistakes
- Putting a user-input check inside an `assert` - it disappears in
  production and the bad value walks straight into the program.
- Using assertions to validate arguments that arrive from outside.
- Assuming assertions are on because they were tested. They are off unless
  `-ea` is passed, which is why a bug can appear only in production.
- Asserting something and then acting on the assumption in the same breath
  without a check that works either way.

### Review questions
1. Are assertions enabled by default? How are they turned on?
2. Why is an assertion the wrong tool for validating user input?
3. What happens to an `assert` statement when assertions are disabled?
4. Define precondition, postcondition and invariant, and give an example of
   each.
5. Why is `assert x = 5;` a bug rather than an assignment that also checks?
6. A method's precondition says the argument must be positive. Where should
   the check live, and what should it do when it fails?
7. When would you want assertions enabled in production, and what would
   that cost?
8. Give a precondition and a postcondition for a method that removes an
   item from a list.

### Practice
Write a class `BankAccount` with a `withdraw` method. Add an assertion for
the precondition (positive amount), one for the precondition of the
account (sufficient balance) and one for the postcondition (balance still
non-negative). Run it once with `java -ea` and once without, and explain
the difference in the behaviour you see.
