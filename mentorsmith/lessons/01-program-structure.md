---
id: 01-program-structure
title: Program Structure
order: 1
---

## Objectives
- Recognise the required parts of a C++ program.
- Explain what `main` does and what its return value means.
- Compile and run a minimal program from the terminal.
- Read a compiler error message and locate the offending line.

## Explanation
A C++ program is compiled from one or more *translation units* into an
executable. The entry point is `main`, which the operating system calls when
the program starts. Execution begins at the first statement inside `main` and
stops when `main` returns.

Every `main` must return an `int`:

```cpp
int main() {
    return 0;
}
```

The value is an *exit status*. By convention `0` means success and any
non-zero value signals failure. A `main` that falls off the end without an
explicit `return` also returns `0`, but writing it explicitly is clearer.

Statements end with a semicolon. That is the single most common cause of a
compile error in a first program.

Anatomy of a small program:

```cpp
#include <iostream>   // 1. declaration: bring in the stream library

int main() {           // 2. entry point
    std::cout << "Hello\n";  // 3. statement
    return 0;          // 4. success
}
```

The `#include` line is a *preprocessor directive*. It tells the compiler to
paste the contents of `<iostream>` in before compiling, which is what makes
`std::cout` available. `<iostream>` is a standard header shipped with the
compiler — it is not a file in your project.

`std::` is a *namespace qualifier*. It says "look inside the namespace called
`std`", which keeps your names from colliding with the standard library's.

## Example
```cpp
#include <iostream>

int main() {
    std::cout << "C++ is a compiled language.\n";
    return 0;
}
```

Compile and run it:

```bash
g++ -std=c++17 -Wall main.cpp -o program
./program
```

## Knowledge checks
Q: What must a `main` function return?
A: An `int`. `0` conventionally means the program succeeded.
Q: What does the `#include <iostream>` line actually do?
A: It pastes the contents of that standard header in before compilation, providing declarations for `std::cout` and `std::cin`.
Q: What happens if you forget a semicolon?
A: The compiler reports a syntax error and points at the end of the offending line rather than where the statement began.

## Exercise
Write a program that prints three lines, in order:

```
Line one
Line two
Line three
```

Start from this skeleton and replace the comment:

```cpp starter
#include <iostream>

int main() {
    // Print "Line one", "Line two" and "Line three", each on its own line.
    // A "\n" character inside a string starts a new line when printed.
    return 0;
}
```

Then try deliberately deleting a semicolon and read the compiler error. Fix it
and note what the error pointed at versus where the mistake really was.

## Common mistakes
- **Missing semicolon.** The error usually points at the *next* line, which is confusing at first. The statement being parsed is the one before the reported line.
- **Printing without a newline.** `std::cout` does not add line breaks. `"Hello"` and `"Hello\n"` print differently.
- **Forgetting `return 0;`.** Modern C++ implies it, but leaving it in makes the intent explicit.
- **Writing `#include "iostream"`.** Quotes mean "look in my project first". Standard headers use angle brackets.

## Recap
- `int main()` is the entry point the OS calls.
- `return 0` from `main` reports success.
- `#include` is a preprocessor step, not a runtime import.
- `std::` qualifies names from the standard namespace.
- Statements need semicolons.