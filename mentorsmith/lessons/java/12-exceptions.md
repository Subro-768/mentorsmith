---
id: 12-exceptions
title: Exceptions and Error Handling
order: 12
tier: core
---

## Objectives
- Handle errors with `try`, `catch`, and `finally`.
- Throw exceptions with `throw`.
- Distinguish checked vs unchecked exceptions.

## Explanation
Exceptions represent runtime error conditions:
```java
try {
    int result = 10 / 0;
} catch (ArithmeticException e) {
    System.out.println("Cannot divide by zero: " + e.getMessage());
} finally {
    System.out.println("Always runs");
}
```

- **Checked exceptions**: Inherit from `Exception` (excluding `RuntimeException`). Must be caught or declared in method signature with `throws`.
- **Unchecked exceptions**: Inherit from `RuntimeException` (e.g. `NullPointerException`, `IndexOutOfBoundsException`).

## Example
```java
public class Main {
    public static void main(String[] args) {
        try {
            int num = Integer.parseInt("abc");
        } catch (NumberFormatException e) {
            System.out.println("Parsing failed");
        }
    }
}
```

## Knowledge checks
Q: Does a finally block execute if an exception occurs?
A: Yes, finally blocks always execute regardless of whether an exception was thrown or caught.
Q: What is the base class for exceptions that do not require mandatory handling?
A: RuntimeException (unchecked exceptions).
Q: What keyword is used to explicitly raise an exception?
A: throw.

## Exercise
Wrap parsing of string `"xyz"` with `Integer.parseInt` in a `try-catch` block. Catch `NumberFormatException` and print "Caught NumberFormatException".

```java starter
public class Main {
    public static void main(String[] args) {
        // try to parse "xyz", catch NumberFormatException and print message
    }
}
```

## Common mistakes
- Catching generic `Exception` and swallowing it silently without logging or handling.
- Forgetting that `finally` runs even if a `return` statement is hit inside `try`.

## Recap
- `try-catch` prevents crashes and handles errors gracefully.
- `finally` ensures cleanup runs.
