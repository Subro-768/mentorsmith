---
id: 10-references
title: References
order: 10
---

## Objectives
- Declare a reference with `&` and initialise it at declaration.
- Explain why a reference must be initialised and cannot be reseated.
- Pass arguments by reference to avoid copying and allow modification.
- Choose between pointers and references correctly.

## Explanation
A reference is an *alias* — a second name for an existing object. Once bound,
it stays bound forever.

```cpp
int number = 42;
int& alias = number;     // alias IS number, not a copy

alias = 99;
std::cout << number;     // 99 - the original changed
```

Three rules distinguish references from pointers:

1. **A reference must be initialised when declared.** `int& r;` does not compile.
2. **A reference cannot be reseated.** `r = someOtherVar;` assigns *through* `r`, it does not make `r` refer to `something else`. There is no equivalent of pointer arithmetic or reassignment.
3. **A reference cannot be null.** Every reference must bind to a real object.

The third rule is the important safety difference: because a reference cannot
be "empty", code using one does not need null checks.

**References as function parameters** are the idiomatic way to avoid copying
and optionally to allow modification:

```cpp
void increment(int& target) { ++target; }              // modifies the caller
int  count_digits(int number) { ... }                  // takes a copy; number is small

std::size_t length_of(const std::string& text) {       // the best common form
    return text.size();                                // no copy, read-only
}
```

`const T&` deserves special mention. For a large type such as
`std::vector` or `std::string`, passing by value copies the whole object on
every call. `const T&` passes a reference the callee cannot modify — fast and
safe. This is the default parameter form for anything non-trivial.

Returning references is possible but risky: a reference to a local variable
becomes dangling the moment the function returns.

```cpp
const std::string& bad() {
    std::string local = "gone";
    return local;       // DANGLING - local is destroyed on return
}
```

**Which should I use?**

| Situation | Use |
|---|---|
| Parameter should read a value without copying | `const T&` |
| Parameter should modify the caller's variable | `T&` |
| Parameter may legitimately be "nothing" | `T*` (check for `nullptr`) |
| Reassign or point into an array | `T*` |
| Local alias inside a function | `T&` |

In short: prefer references by default, and reach for a pointer when you need
optionality, reseating, or array traversal.

## Example
```cpp
#include <iostream>
#include <string>
#include <vector>

void increment(int& target) {
    ++target;
}

void describe(const int& value) {
    std::cout << "value is " << value << " (read-only parameter)\n";
}

std::size_t total_length(const std::vector<std::string>& words) {
    std::size_t total = 0;
    for (const std::string& word : words) {   // const ref: no copy per word
        total += word.size();
    }
    return total;
}

int main() {
    int counter = 10;

    int& alias = counter;      // alias is another name for counter
    alias = 99;
    std::cout << "counter after alias = 99 : " << counter << '\n';

    increment(counter);
    std::cout << "after increment      : " << counter << '\n';

    describe(counter);

    int second = 5;
    // counter = second;   // this would ASSIGN 5 to counter, not reseat alias
    alias = 99;            // so alias is still 99 afterwards
    std::cout << "second untouched     : " << second << '\n';
    std::cout << "alias still          : " << alias << '\n';

    const std::vector<std::string> words{"hello", "world", "again"};
    std::cout << "total characters    : " << total_length(words) << '\n';
    return 0;
}
```

## Knowledge checks
Q: What happens when you write `alias = someOtherVariable` where `alias` is a reference?
A: It assigns the value of `someOtherVariable` *through* `alias`, changing the original object `alias` is bound to. It does not rebind the reference.
Q: Why can a reference never be null?
A: A reference must be initialised and must bind to a real object, so there is no "empty" state to represent. This is why reference parameters need no null checks.
Q: Why is `const std::string&` preferred over `std::string` for a read-only parameter?
A: It avoids copying the entire string on every call while guaranteeing the function cannot modify it.
Q: What is a dangling reference?
A: A reference to an object that has already been destroyed — for example one returned to a local variable. Using it is undefined behaviour.

## Exercise
Write a function `void normalise(int& value)` that doubles a positive number and
negates a negative one, in place. Write `void swap_refs(int& a, int& b)` that
swaps two values. Then write `void unsafe_swap(int* a, int* b)` doing the same
via pointers, and confirm both produce identical results.

```cpp starter
#include <iostream>

void normalise(int& value) {
    // If value > 0, double it. If value < 0, negate it. Leave 0 alone.
}

void swap_refs(int& a, int& b) {
    // Swap through the two references.
}

void unsafe_swap(int* a, int* b) {
    // Swap through the two pointers.
}

int main() {
    int x = 5, y = -3;
    // normalise both, print them, swap them, print again.
    return 0;
}
```

## Common mistakes
- **Declaring a reference without initialising it.** A compile error.
- **Expecting a reference to be reseatable.** Assignment writes through the alias.
- **Passing a temporary to a non-const reference.** Cannot bind; use `const T&` instead.
- **Returning a reference to a local.** Dangling reference, undefined behaviour.
- **Using `&` for both address-of and reference declaration.** Context decides; `int& r` declares a reference, `&x` takes an address.

## Recap
- A reference is a permanent alias, not a copy.
- It must be initialised, cannot be reseated, and cannot be null.
- `T&` lets a function modify the caller's variable; `const T&` avoids copies safely.
- Returning references to locals creates dangling references.
- Prefer references; use pointers when you need optionality or reseating.