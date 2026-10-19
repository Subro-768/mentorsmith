---
id: 01-program-structure
title: Program Structure
order: 1
---

## Objectives
- Understand the basic structure of a Java application.
- Learn the purpose of public class Main and the main method.
- Output text using System.out.println.

## Explanation
In Java, every line of executable code must be inside a class. By convention and toolchain requirement, if your file is named `Main.java`, it contains `public class Main`.

The execution starts at the `main` method with the exact signature:
`public static void main(String[] args)`

- `public`: Accessible from anywhere by the JVM.
- `static`: Can be invoked without creating an instance of the class.
- `void`: Does not return any exit code; termination is controlled by exiting or exceptions.
- `String[] args`: Command-line arguments.

To print output to standard out, Java provides `System.out.println()`.

## Example
```java
public class Main {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
}
```

## Knowledge checks
Q: Why must the class be named Main?
A: In Java, a public class must match the name of the file (Main.java).
Q: What does void mean in the main method signature?
A: It means the method does not return a value.
Q: What method prints text with an automatic newline in Java?
A: System.out.println().

## Exercise
Write a program that prints "Welcome to Java" followed by "MentorSmith Studio" on separate lines.

```java starter
public class Main {
    public static void main(String[] args) {
        // Print Welcome to Java and MentorSmith Studio on separate lines
    }
}
```

## Common mistakes
- Misspelling `String[] args` or forgetting `static`.
- Using single quotes for strings (single quotes are only for single char literals).
- Forgetting the ending semicolon `;`.

## Recap
- Java applications enter through `public static void main(String[] args)`.
- Code must reside inside a class matching the filename.
