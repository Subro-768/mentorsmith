---
id: 01-program-structure
title: Program Structure
order: 1
---

## Objectives
- Write a C program that compiles and runs.
- Explain `main`, `int main(void)` and the exit status.
- Use `#include` correctly and understand what it actually does.
- Read a compiler diagnostic and find the real mistake.

## Explanation
A C program has a `main` function the operating system calls:

```c
#include <stdio.h>

int main(void) {
    printf("Hello from C\n");
    return 0;
}
```

Compile and run:

```bash
gcc -std=c11 -Wall -Wextra program.c -o program
./program
```

**`int main(void)`** — the two words matter. `int` is the return type. `(void)`
means the function takes no parameters, which is different from `( )` where an
empty list means "unspecified arguments". Always write `(void)`.

`return 0` reports success. Any non-zero value reports failure.

**`#include <stdio.h>`** pastes the contents of that header in before compiling.
`stdio.h` declares `printf` and friends. The angle brackets mean "look in the
system's include directories"; quotes mean "look in this directory first".

C has no built-in console: every line of output comes from the standard library.
`printf` comes from `<stdio.h>`, which is why the `#include` is required.

**C is strict.** Unlike C++, a C compiler rejects things C++ accepts:

- implicit function declarations
- forgetting to return from a non-void function
- using a variable before declaring it

Those are why `-Wall -Wextra` matter, and why some warnings are promoted to
errors in this course.

## Example
```c
/* program_structure.c */
#include <stdio.h>

int main(void) {
    printf("C is compiled, not interpreted.\n");
    printf("A line: %d\n", 42);
    return 0;
}
```

`%d` is a conversion specifier. Getting the specifier wrong — `%d` for a
`double`, say — is undefined behaviour, which is a real source of crashes.

## Knowledge checks
Q: Why write `int main(void)` instead of `int main()`?
A: `(void)` states explicitly that the function takes no arguments, so the compiler checks calls. `()` leaves the arguments unspecified.
Q: What does `#include <stdio.h>` do?
A: It pastes the header's declarations in before compiling, which is what makes `printf` usable.
Q: What does `return 0` from `main` mean?
A: It becomes the process exit status. By convention 0 means success.
Q: Why use `-Wall -Wextra`?
A: They surface the mistakes C cannot safely accept, such as implicit declarations and missing returns.

## Exercise
Write a program that prints three labelled lines: your name, a number, and a
sum. Then remove a semicolon, compile, and read what the compiler says.

```c starter
#include <stdio.h>

int main(void) {
    /* Print "Name: <your name>", "Value: 7" and "Double: 14". */
    return 0;
}
```

## Common mistakes
- **Forgetting `#include <stdio.h>`.** Every `printf` becomes an error.
- **Using `console.log`.** That is JavaScript; C uses `printf`.
- **Mismatched format specifiers,** which is undefined behaviour, not a warning.
- **Writing `()` instead of `(void)`.**
- **Expecting C++ conveniences.** There is no `std::string`, no references, no default arguments.

## Recap
- `int main(void)` with `return 0`.
- `#include` is a preprocessor step bringing in declarations.
- Output comes from `<stdio.h>`.
- Compile with `-Wall -Wextra` and read the first error, not the last.