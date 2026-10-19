---
id: 16-exceptions-and-error-handling
title: Exceptions and Error Handling
order: 16
tier: core
---

## Objectives
- Throw and catch exceptions.
- Use custom exception types that carry useful information.
- Apply RAII so cleanup happens during unwinding.
- Choose between exceptions and returning an error value.

## Explanation
C++ reports runtime errors by *throwing* an exception. A `throw` transfers
control to a matching `catch` somewhere up the call stack, skipping the rest
of the intervening code.

```cpp
#include <iostream>
#include <stdexcept>
#include <string>

int main() {
    try {
        std::string input = "not a number";
        int value = std::stoi(input);       // throws std::invalid_argument
        std::cout << value << '\n';
    } catch (const std::exception& error) {
        std::cout << "Failed: " << error.what() << '\n';
        return 1;
    }
    return 0;
}
```

**Exception types** in `<stdexcept>`:

| Type | Raised for |
|---|---|
| `std::runtime_error` | General runtime problems |
| `std::invalid_argument` | Bad arguments to a function |
| `std::out_of_range` | Index or iterator out of bounds |
| `std::length_error` | Size exceeds an implementation limit |
| `std::overflow_error` | Value too large for the target type |

All derive from `std::exception`, which provides `what()` returning a
human-readable description.

**Custom exceptions** are worth it when the caller needs specific detail:

```cpp
class InsufficientFunds : public std::runtime_error {
public:
    InsufficientFunds(double requested, double available)
        : std::runtime_error("insufficient funds"),
          requested_(requested),
          available_(available) {}

    double requested() const { return requested_; }
    double available() const { return available_; }

private:
    double requested_;
    double available_;
};
```

**`catch` ordering matters.** Handlers are tried in order, so catch derived
types first:

```cpp
try {
    // ...
} catch (const InsufficientFunds& error) {   // specific first
    // ...
} catch (const std::runtime_error& error) {  // then broader
    // ...
} catch (const std::exception& error) {      // then broadest
    // ...
}
```

A handler written before the broader ones makes the broader ones unreachable,
and the compiler warns about this.

**RAII during unwinding.** When an exception propagates, local objects are
still destroyed properly — that is the single biggest advantage of C++ over
languages without destructors. So resources should be owned by objects:

```cpp
void process() {
    std::ofstream file("data.txt");
    if (!file) throw std::runtime_error("cannot open data.txt");

    risky_operation();       // if this throws, `file` is still closed

    if (!file) throw std::runtime_error("write failed");
}
```

You do not need `catch (...)` and a manual `close()` — the destructor handles
it. Reserve `catch (...)` for logging at a genuine boundary; it hides real
errors.

**Exceptions vs error codes.** Throwing is right for conditions the caller
cannot easily be expected to handle inline. Returning `bool` or an optional
is often clearer for expected outcomes, such as "user entered an invalid
value". Avoid throwing across a `noexcept` function, and never throw from a
destructor.

The key insight: exceptions separate *what went wrong* from *what to do about
it*, so the reporting layer stays separate from the decision layer.

## Example
```cpp
#include <iostream>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

class InsufficientFunds : public std::runtime_error {
public:
    InsufficientFunds(double requested, double available)
        : std::runtime_error("insufficient funds"),
          requested_(requested), available_(available) {}

    double requested() const { return requested_; }
    double available() const { return available_; }

private:
    double requested_;
    double available_;
};

class BankAccount {
public:
    explicit BankAccount(double opening_balance) : balance_(opening_balance) {
        if (opening_balance < 0.0) {
            throw std::invalid_argument("opening balance cannot be negative");
        }
    }

    void withdraw(double amount) {
        if (amount <= 0.0) {
            throw std::invalid_argument("withdrawal amount must be positive");
        }
        if (amount > balance_) {
            throw InsufficientFunds(amount, balance_);   // specific type
        }
        balance_ -= amount;
    }

    void deposit(double amount) {
        if (amount <= 0.0) {
            throw std::invalid_argument("deposit amount must be positive");
        }
        balance_ += amount;
    }

    double balance() const { return balance_; }

private:
    double balance_ = 0.0;
};

int checked_value(int index, const std::vector<int>& values) {
    if (index < 0 || index >= static_cast<int>(values.size())) {
        throw std::out_of_range("index " + std::to_string(index)
                              + " outside 0.." + std::to_string(values.size() - 1));
    }
    return values[static_cast<std::size_t>(index)];
}

// The file is closed by its destructor even if risky_operation() throws.
void save(const std::string& path, const std::vector<int>& values) {
    std::ofstream file(path);
    if (!file) {
        throw std::runtime_error("cannot open '" + path + "' for writing");
    }
    for (int value : values) {
        file << value << '\n';
    }
    if (!file) {
        throw std::runtime_error("failed while writing '" + path + "'");
    }
}

int main() {
    // 1. Basic catch by base type.
    try {
        int value = std::stoi("not a number");
        std::cout << value << '\n';
    } catch (const std::invalid_argument& error) {
        std::cout << "1) bad input: " << error.what() << '\n';
    }

    // 2. A domain-specific exception carrying extra data.
    try {
        BankAccount account{100.0};
        account.withdraw(250.0);
    } catch (const InsufficientFunds& error) {
        std::cout << "2) asked for " << error.requested()
                  << " but only " << error.available() << " available\n";
    } catch (const std::exception& error) {
        std::cout << "2) other failure: " << error.what() << '\n';
    }

    // 3. Constructor validation.
    try {
        BankAccount bad{-5.0};
        std::cout << "3) unreachable\n";
    } catch (const std::invalid_argument& error) {
        std::cout << "3) rejected: " << error.what() << '\n';
    }

    // 4. Bounds checking with a descriptive message.
    const std::vector<int> scores{70, 85, 92};
    try {
        std::cout << "4) value at 9 = " << checked_value(9, scores) << '\n';
    } catch (const std::out_of_range& error) {
        std::cout << "4) out of range: " << error.what() << '\n';
    }
    std::cout << "4) value at 1 = " << checked_value(1, scores) << " (fine)\n";

    // 5. RAII: the file closes even though risky_operation() may throw.
    try {
        save("/nonexistent-directory-xyz/scores.txt", scores);
        std::cout << "5) saved\n";
    } catch (const std::exception& error) {
        std::cout << "5) save failed: " << error.what() << '\n';
    }

    // 6. Recovering and continuing after a handled failure.
    BankAccount account{50.0};
    try {
        account.withdraw(500.0);
    } catch (const InsufficientFunds&) {
        std::cout << "6) withdrawal refused, account still usable\n";
    }
    account.deposit(25.0);
    std::cout << "6) balance now = " << account.balance() << '\n';
    return 0;
}
```

## Knowledge checks
Q: What is the order of `catch` handlers checked in?
A: In the order they are written, first match wins. So the most derived type must come before its bases, or the broader handler makes the narrower ones unreachable.
Q: Why do you rarely see `catch (...)` used for cleanup?
A: Because local objects are destroyed automatically during stack unwinding, so RAII handles cleanup. A catch-all only hides errors if it swallows them.
Q: When is returning an error value better than throwing?
A: For expected, routine outcomes such as invalid user input, where the caller must branch on the result anyway. Reserve exceptions for conditions that are genuinely exceptional.
Q: What happens to local objects when an exception propagates?
A: Their destructors are called in reverse order of construction, during stack unwinding, so RAII resources are released correctly.

## Exercise
Write a class `Rectangle` that validates its constructor arguments and throws
on invalid input: width and height must both be positive, otherwise throw
`std::invalid_argument`. Add an `area()` method and a `scale(double)` method
that throws `std::invalid_argument` for a non-positive factor. Then write a
`main` that catches each failure type separately and reports it clearly.

```cpp starter
#include <iostream>
#include <stdexcept>

class Rectangle {
public:
    Rectangle(double width, double height) {
        // Throw std::invalid_argument if width <= 0 or height <= 0.
        // Store the validated values.
    }

    double area() const { return width_ * height_; }

    void scale(double factor) {
        // Throw std::invalid_argument if factor <= 0.
        // Multiply both dimensions.
    }

private:
    double width_ = 0.0;
    double height_ = 0.0;
};

int main() {
    // Construct a valid rectangle and print its area.
    // Try an invalid one and catch std::invalid_argument.
    // Try an invalid scale and catch it too.
    // Show that after handling, the original rectangle still works.
    return 0;
}
```

## Common mistakes
- **Catching a broad type before a narrow one.** Makes the narrow handler unreachable.
- **Throwing by value.** Always `throw SomeError(...)`; never `throw err;`.
- **Throwing from a destructor.** The program is already unwinding; this forces `std::terminate`.
- **Using `catch (...)` and ignoring it.** Silently swallows real errors.
- **Not including `<stdexcept>`.** The types are not available.
- **Throwing for routine validation** where returning a `bool` would read better.

## Recap
- `throw` transfers control to the nearest matching `catch`.
- Standard types live in `<stdexcept>` and derive from `std::exception`.
- Catch derived types before their bases.
- RAII guarantees cleanup during unwinding, so `catch (...)` is rarely needed.
- Choose exceptions for exceptional conditions, return values for routine ones.