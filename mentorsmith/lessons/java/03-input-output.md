---
id: 03-input-output
title: Input and Output
order: 3
---

## Objectives
- Read input from standard input using `java.util.Scanner`.
- Format output with `System.out.printf`.

## Explanation
To read input, create a `Scanner` object wrapping `System.in`:
```java
import java.util.Scanner;

Scanner scanner = new Scanner(System.in);
String line = scanner.nextLine();
int number = scanner.nextInt();
```

For formatted output, `System.out.printf` supports format specifiers like `%s` (string), `%d` (integer), and `%.2f` (floating point to 2 decimals).

## Example
```java
import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        if (scanner.hasNextLine()) {
            String name = scanner.nextLine();
            System.out.println("Hello, " + name);
        }
    }
}
```

## Knowledge checks
Q: Which class is commonly used for user input in console applications?
A: java.util.Scanner.
Q: What format specifier in printf formats a floating-point number to two decimal places?
A: %.2f.
Q: Why should you be careful when mixing nextInt() and nextLine()?
A: nextInt() does not consume the trailing newline character, leaving it for the subsequent nextLine().

## Exercise
Read an integer and print its square.

```java starter
import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        // Read integer and print its square
    }
}
```

## Common mistakes
- Forgetting `import java.util.Scanner;`.
- Calling `nextInt()` when input is not an integer, throwing `InputMismatchException`.

## Recap
- Use `Scanner` with `System.in` for console input.
- `printf` provides C-style string formatting.
