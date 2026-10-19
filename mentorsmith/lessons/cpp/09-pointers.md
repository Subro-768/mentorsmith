---
id: 09-pointers
title: Pointers
order: 9
tier: core
---

## Objectives
- Explain what a pointer is and what `&` and `*` do.
- Declare and initialise pointers safely.
- Dereference a pointer to read and write through it.
- Initialise to `nullptr` and avoid dereferencing it.

## Explanation
A pointer is a variable that stores a memory address. Two operators matter:

- `&value` — the **address-of** operator. Gives the address where a value lives.
- `*pointer` — the **dereference** operator. Gives the value stored at that address.

```cpp
int number = 42;
int* address_of_number = &number;   // address of number

std::cout << number          << '\n';   // 42
std::cout << address_of_number << '\n'; // some address, e.g. 0x7ffd...
std::cout << *address_of_number << '\n'; // 42 again, read through the pointer
```

Dereferencing lets you modify the original variable, because the pointer and
the variable refer to the same memory:

```cpp
*address_of_number = 99;
std::cout << number;    // 99 - the original changed
```

**Always initialise a pointer.** An uninitialised pointer contains whatever
bytes happened to be in that memory — often garbage. Dereferencing it may
crash or corrupt unrelated data.

```cpp
int* p = &number;    // good - points at a real object
int* q;              // BAD - uninitialised
int* r = nullptr;    // good - explicitly points at nothing
```

Modern C++ prefers `nullptr` over the old `NULL` or `0`, because neither can
act as a "real" pointer and `nullptr` has its own type.

**Always check before dereferencing:**

```cpp
if (r != nullptr) {
    std::cout << *r << '\n';
}
```

Dereferencing `nullptr` is undefined behaviour and usually a segmentation
fault. `&value == nullptr` is *always false* — an address of a real object can
never be null, so that test is a common logical error worth recognising.

**`const` with pointers.** Position matters and changes the meaning:

```cpp
const int* p1 = &number;   // pointer to const int - cannot change the value
int* const p2 = &number;   // const pointer to int - cannot be repointed
const int* const p3 = &number;  // neither may change
```

In practice `const T*` is what you want most of the time: read through the
pointer, but do not modify the pointee.

**Passing a pointer to a function** gives the function the ability to modify
the caller's variable without copying it:

```cpp
void swap_values(int* a, int* b) {
    const int temp = *a;
    *a = *b;
    *b = temp;
}

int x = 1, y = 2;
swap_values(&x, &y);    // x == 2, y == 1
```

This is what `std::swap` does, and it explains why the standard library's
swap-like functions take references rather than pointers.

## Example
```cpp
#include <iostream>

void swap_values(int* a, int* b) {
    const int temp = *a;
    *a = *b;
    *b = temp;
}

void increment(int* target) {
    if (target != nullptr) {
        ++(*target);
    }
}

int main() {
    int number = 42;
    int* address = &number;

    std::cout << "number            = " << number << '\n';
    std::cout << "address of number = " << &number << '\n';
    std::cout << "address variable  = " << address << '\n';
    std::cout << "value via *       = " << *address << '\n';
    std::cout << "same address?     = " << std::boolalpha << (&number == address) << '\n';

    *address = 99;
    std::cout << "after *address=99 = " << number << '\n';

    int* nothing = nullptr;
    std::cout << "nothing is null?  = " << (nothing == nullptr) << '\n';
    if (nothing != nullptr) {
        std::cout << *nothing << '\n';    // skipped, correctly
    } else {
        std::cout << "safely skipped a null pointer\n";
    }

    int x = 1, y = 2;
    swap_values(&x, &y);
    std::cout << "after swap        = " << x << ", " << y << '\n';

    increment(&x);
    std::cout << "after increment   = " << x << '\n';
    return 0;
}
```

## Knowledge checks
Q: What does `&number` give, and what does `*address` give?
A: `&number` gives the address where `number` is stored. `*address` gives the value stored at the address held in `address`.
Q: Why initialise pointers to `nullptr` rather than leaving them uninitialised?
A: An uninitialised pointer holds arbitrary garbage, and dereferencing it is undefined behaviour. `nullptr` makes the "points at nothing" state explicit and testable.
Q: Is `&number == nullptr` ever true?
A: No, never. The address of a real object cannot be null, so testing `&value == nullptr` is always false and usually a mistake.
Q: In `const int* p`, what is const?
A: The pointee. The value at the address cannot be modified through `p`, but `p` itself can be repointed.

## Exercise
Declare three `int` variables, and three pointers pointing at them. Use
dereference to set each variable to 100, 200 and 300. Print each variable
through its pointer. Then swap the *values* using a pointer-based swap function.

```cpp starter
#include <iostream>

void swap_values(int* a, int* b) {
    // Swap the values the two pointers refer to.
}

int main() {
    int first = 0, second = 0, third = 0;
    int* p_first = nullptr;   // point these at first, second, third
    int* p_second = nullptr;
    int* p_third = nullptr;

    // Set each variable through its pointer: 100, 200, 300.
    // Print each variable by dereferencing its pointer.
    // Then call swap_values(p_first, p_second) and print the result.
    return 0;
}
```

## Common mistakes
- **Dereferencing `nullptr` or an uninitialised pointer.** Undefined behaviour, usually a crash.
- **Testing `&value == nullptr`.** Always false.
- **Mixing up `*` declaration syntax:** `int* p` declares a pointer, `int *p` is identical. Writing `int* p, q` makes `q` an `int`, not a pointer.
- **Forgetting that modifying through a pointer modifies the original.** Often intended, occasionally a surprise.
- **Using `NULL` or `0` instead of `nullptr`.** Prefer `nullptr`.

## Recap
- A pointer stores an address; `&` takes an address, `*` reads one.
- Always initialise to `nullptr` and check before dereferencing.
- Writing through a pointer changes the original object.
- `&value == nullptr` is always false.
- `const T*` protects the pointee; `T* const` protects the pointer.