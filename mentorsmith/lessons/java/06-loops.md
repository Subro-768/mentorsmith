---
id: 06-loops
title: Loops
order: 6
tier: foundation
---

## Objectives
- Master `for`, `while`, and `do-while` loops.
- Use `break` and `continue`.
- Understand enhanced for-each loops.

## Explanation
Loops repeat execution while a condition is true:

```java
// Traditional for loop
for (int i = 0; i < 5; i++) {
    System.out.println(i);
}

// While loop
while (condition) {
    // runs while true
}

// Do-while loop
do {
    // runs at least once
} while (condition);
```

- `break` exits the loop immediately.
- `continue` skips the remainder of the current iteration.

## Example
```java
public class Main {
    public static void main(String[] args) {
        for (int i = 1; i <= 3; i++) {
            System.out.println("Count: " + i);
        }
    }
}
```

## Knowledge checks
Q: When is a do-while loop preferred over a while loop?
A: When the body must execute at least once before checking the condition.
Q: What does the continue keyword do?
A: It jumps directly to the next iteration of the surrounding loop.
Q: What is an off-by-one error?
A: A loop iterating one time too few or too many due to < vs <= boundary confusion.

## Exercise
Use a loop to print the first 5 multiples of 3 (3, 6, 9, 12, 15), each on a new line.

```java starter
public class Main {
    public static void main(String[] args) {
        // Print 3, 6, 9, 12, 15 using a loop
    }
}
```

## Common mistakes
- Creating accidental infinite loops by forgetting to increment loop counters.
- Semicolon immediately after `for(...) ;` making the body empty.

## Recap
- `for` is best for counting iterations.
- `while` is best when the stopping condition is dynamic.
