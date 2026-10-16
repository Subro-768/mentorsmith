---
id: 03-input-output
title: Input and Output
order: 3
---

## Objectives
- Read values from standard input with `std::cin`.
- Write values with `std::cout` and format them.
- Explain why input can fail and how to detect it.
- Avoid the classic `cin`/`cout` flushing bug.

## Explanation
Standard input and output are *streams*. `std::cout` writes to the terminal,
`std::cin` reads from the keyboard.

```cpp
#include <iostream>
#include <string>

int main() {
    std::string name;
    std::cout << "What is your name? ";
    std::cin >> name;                      // reads one whitespace-delimited word
    std::cout << "Hello, " << name << '\n';
    return 0;
}
```

`>>` reads up to the next whitespace. To read a whole line including spaces,
use `std::getline`.

**The classic bug.** `std::cin >>` leaves the newline in the stream. So if you
mix the two, `getline` reads that leftover newline and returns an empty string:

```cpp
int age;
std::cin >> age;      // user types "20" then Enter
std::cin.ignore();    // discard the leftover newline
std::string rest;
std::getline(std::cin, rest);   // now this reads the real remainder
```

A more robust alternative, which discards all whitespace:

```cpp
std::cin >> std::ws;   // skip any pending whitespace before getline
std::getline(std::cin, rest);
```

**Always check whether input succeeded.** If the user types letters where a
number is expected, `>>` fails, puts `std::cin` into a bad state, and every
later read silently returns nothing — a common source of "my program does
nothing" bugs.

```cpp
int age;
if (!(std::cin >> age)) {
    std::cout << "That was not a number.\n";
    return 1;
}
```

**Formatting.** `std::cout` handles the common numeric types directly:

```cpp
double price = 19.5;
std::cout << price              << '\n';   // 19.5
std::cout << std::fixed
          << std::setprecision(2)
          << price              << '\n';   // 19.50
```

## Example
```cpp
#include <iomanip>
#include <iostream>
#include <string>

int main() {
    std::string item;
    int         quantity;
    double      unit_price;

    std::cout << "Item name: ";
    std::getline(std::cin >> std::ws, item);

    std::cout << "Quantity:  ";
    if (!(std::cin >> quantity)) {
        std::cout << "Quantity must be a whole number.\n";
        return 1;
    }

    std::cout << "Unit price: ";
    if (!(std::cin >> unit_price)) {
        std::cout << "Price must be a number.\n";
        return 1;
    }

    const double total = quantity * unit_price;
    std::cout << std::fixed << std::setprecision(2)
              << "Total: " << total << '\n';
    return 0;
}
```

## Knowledge checks
Q: What is left in the input stream after `std::cin >> n` when the user presses Enter?
A: The newline character, which then causes a following `std::getline` to read an empty string.
Q: Why test `if (!(std::cin >> value))` rather than reading and checking afterwards?
A: The check reads and converts in one step, so a failed read is detected immediately instead of letting a bad stream silently break every later read.
Q: How do you read a full line that contains spaces?
A: `std::getline(std::cin, line)`, preceded by `std::cin >> std::ws` or `ignore()` if a previous `>>` read is pending.

## Exercise
Ask for a student's name and their mark out of 100, then print a summary line
showing the name and the mark as a percentage to one decimal place. Handle the
case where the mark is not a number.

```cpp starter
#include <iomanip>
#include <iostream>
#include <string>

int main() {
    std::string name;
    double mark = 0.0;

    // Read the name with getline, then the mark with >>.
    // If the mark is not a number, print a clear message and return 1.
    // Print: "Alice scored 87.5%"
    return 0;
}
```

## Common mistakes
- **Mixing `>>` and `getline` without clearing the newline.** Produces an empty string where you expected real text.
- **Not checking whether a read succeeded.** The program then appears to hang or skip work with no error message.
- **Forgetting `#include <iomanip>`.** `std::fixed` and `std::setprecision` need it; without it the compiler says so.
- **Expecting `std::endl` to be required.** `'\n'` is faster and sufficient. `std::endl` also flushes the stream.

## Recap
- `std::cout` writes, `std::cin` reads; both are streams.
- `>>` stops at whitespace; `getline` reads a whole line.
- Clear leftover whitespace between a `>>` read and a `getline` read.
- Always test whether an input read succeeded.
- Use `<iomanip>` for `std::fixed` and `std::setprecision`.