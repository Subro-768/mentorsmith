---
id: 07-functions
title: Functions
order: 7
---

## Objectives
- Declare and define a function.
- Pass arguments by value and by reference, and explain the difference.
- Use return values and default arguments.
- Choose sensible parameter and return types.

## Explanation
A function packages a piece of behaviour behind a name so it can be called
repeatedly and tested on its own.

```cpp
return_type name(parameters) {
    // body
}
```

```cpp
int add(int a, int b) {
    return a + b;
}
```

Every `return` must produce a value matching the return type — or nothing at
all, for `void` functions.

**Passing by value** copies the argument. The function cannot change the
caller's variable:

```cpp
void by_value(int x) {
    x = 99;            // only changes the local copy
}
```

**Passing by reference** (`int&`) gives the function access to the caller's
variable:

```cpp
void by_reference(int& x) {
    x = 99;            // really changes the caller's variable
}
```

`const int&` is the idiomatic way to pass a large object read-only: no copy is
made, but the function cannot modify it. This is the form you will want for
strings and vectors in almost every case.

```cpp
std::size_t count_words(const std::string& text);   // no copy, read-only
```

**Default arguments** must be the *trailing* parameters:

```cpp
double power(double base, int exponent = 2);   // power(2.0) == power(2.0, 2)
```

**Deciding what to return.** Returning a value is preferable when the caller
needs it. Do not rely on side effects on arguments when a return value would
be clearer — returning is easier to test.

**Declarations vs definitions.** If you define a function after the code that
calls it, the compiler needs to know it exists first. Either define functions
before use, or declare them at the top:

```cpp
int add(int a, int b);       // declaration - no body

int main() { return add(1, 2); }

int add(int a, int b) {      // definition - with body
    return a + b;
}
```

## Example
```cpp
#include <iomanip>
#include <iostream>
#include <string>

int         add(int a, int b);
std::string describe(int value);

double square(double x) {
    return x * x;
}

double power(double base, int exponent = 2) {
    double result = 1.0;
    for (int i = 0; i < exponent; ++i) {
        result *= base;
    }
    return result;
}

void increment(int& target) {
    ++target;                 // changes the caller's variable
}

int count_digits(int number) {
    int count = 0;
    do {
        ++count;
        number /= 10;
    } while (number != 0);
    return count;
}

std::string describe(int value) {
    if (value > 100) return "large";
    if (value > 10)  return "medium";
    return "small";
}

int main() {
    std::cout << "add(3, 4)      = " << add(3, 4) << '\n';
    std::cout << "square(1.5)    = " << square(1.5) << '\n';
    std::cout << "power(2.0)     = " << power(2.0) << '\n';
    std::cout << "power(2.0, 10) = " << power(2.0, 10) << '\n';

    int counter = 5;
    increment(counter);
    std::cout << "counter        = " << counter << " (changed by reference)\n";

    std::cout << "digits in 4820 = " << count_digits(4820) << '\n';
    std::cout << "describe(500)  = " << describe(500) << '\n';

    const double area = 3.14159 * square(2.0);
    std::cout << std::fixed << std::setprecision(3) << "area           = " << area << '\n';
    return 0;
}
```

## Knowledge checks
Q: What is the difference between `void f(int x)` and `void f(int& x)`?
A: The first receives a copy, so changes inside `f` are invisible to the caller. The second refers to the caller's variable and can change it.
Q: Why is `const std::string&` usually a better parameter than `std::string`?
A: It avoids copying the whole string while still preventing the function from modifying it.
Q: What happens if a non-void function reaches the end without a `return`?
A: It is undefined behaviour. Always return a value from a function declared with a non-void type.
Q: Why must default arguments come last in the parameter list?
A: Callers supply arguments left to right, so optional parameters can only be omitted once all later ones are also omitted.

## Exercise
Write three functions and use them from `main`:

1. `bool is_even(int n)` — returns `true` when `n` is divisible by 2.
2. `int count_digits(int n)` — returns how many digits `n` has. Use a `do while` so that `0` counts as one digit.
3. `void print_stars(int count)` — prints `count` asterisks followed by a newline, and does nothing when `count` is 0 or less.

```cpp starter
#include <iostream>

// Declare your three functions here.

// Define them here.

int main() {
    // Call each function and print its result.
    return 0;
}
```

## Common mistakes
- **Expecting pass-by-value to change the caller's variable.** It cannot.
- **Returning a reference to a local variable.** The local dies at `return`, leaving a dangling reference.
- **Mixing declaration order so the compiler cannot see a function.** Declare before use.
- **Returning `void` but using the result.** That is a compile error.
- **Copying large parameters by value.** Use `const T&`.

## Recap
- Functions take parameters and return values; `void` returns nothing.
- Pass by value to copy, by reference to modify, `const&` to read efficiently.
- Declare a function before calling it if it is defined later.
- Default arguments must be the trailing parameters.