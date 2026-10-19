---
id: 05-conditions
title: Conditions
order: 5
---

## Objectives
- Branch execution using `if`, `else if`, and `else`.
- Switch statements.
- Compare Strings safely using `.equals()`.

## Explanation
Control flow allows executing code based on boolean expressions:
```java
if (score >= 90) {
    grade = "A";
} else if (score >= 80) {
    grade = "B";
} else {
    grade = "C";
}
```

**Crucial rule for Strings:**
Never use `==` to compare String contents! `==` tests object reference identity (memory address). Always use `.equals()`:
`if (name.equals("Alice")) { ... }`

`switch` matches discrete values (int, char, String, enums).

## Example
```java
public class Main {
    public static void main(String[] args) {
        String command = "start";
        if (command.equals("start")) {
            System.out.println("Starting engine...");
        } else {
            System.out.println("Unknown command");
        }
    }
}
```

## Knowledge checks
Q: Why shouldn't you compare Strings using ==?
A: == compares object memory references, not character content; .equals() compares text content.
Q: Can a switch statement evaluate String variables in modern Java?
A: Yes, since Java 7 switch supports String cases.
Q: What happens if a break statement is omitted in a traditional switch case?
A: Execution falls through to the next case block.

## Exercise
Check if a variable `int temp = 22` is above 30 ("Hot"), between 15 and 30 inclusive ("Warm"), or below 15 ("Cold"). Print the result.

```java starter
public class Main {
    public static void main(String[] args) {
        int temp = 22;
        // Print Hot, Warm, or Cold based on temp
    }
}
```

## Common mistakes
- Comparing `str == "hello"` which can randomly evaluate to false for dynamically allocated strings.
- Missing braces causing only the first following statement to be conditional.

## Recap
- Use `if-else` for boolean ranges and `switch` for distinct values.
- Always use `a.equals(b)` for string equality.
