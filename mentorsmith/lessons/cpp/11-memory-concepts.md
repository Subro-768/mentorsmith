---
id: 11-memory-concepts
title: Basic Memory Concepts
order: 11
tier: core
---

## Objectives
- Describe the stack, the heap and static storage.
- Explain how automatic variables are created and destroyed.
- Use `new` and `delete` correctly and understand the pitfalls.
- Recognise leaks, dangling pointers and double frees.

## Explanation
C++ stores objects in three main regions.

**Stack.** Local variables and function parameters live here. Memory is
allocated automatically when a function is called and reclaimed when it
returns. It is fast and orderly, but bounded — a huge local array can
overflow it.

```cpp
void demo() {
    int local = 42;      // stack - created on entry, destroyed on return
}                       // local no longer exists here
```

**Heap.** Memory requested explicitly with `new` and released with `delete`. It
is larger and outlives the function, at the cost of manual management.

```cpp
int* value = new int(42);   // heap
delete value;               // release it
value = nullptr;            // good hygiene afterwards
```

**Static storage.** Globals, `static` locals and string literals live for the
whole program.

**Raw `new`/`delete` rules.** These matter enough that modern C++ prefers to
avoid them:

- Every `new` needs exactly one matching `delete`. A missing delete is a
  **memory leak**; a second delete is a **double free**, which is undefined
  behaviour and often a crash.
- Never `delete` the same pointer twice.
- Never `delete` memory you did not allocate with `new`.
- If you allocate an array with `new[]`, release it with `delete[]`. Mixing
  them is undefined behaviour.
- A `delete` on a `nullptr` is safe and does nothing.
- Never delete a pointer that points to an automatic variable.

**Dangling pointers** point at memory that has been freed. The pointer value
still looks valid, which is what makes the bug so hard to find — the memory
may now belong to something else entirely.

Prefer **`std::unique_ptr`**, which releases memory automatically when it goes
out of scope:

```cpp
#include <memory>

auto value = std::make_unique<int>(42);   // heap int, freed automatically
std::cout << *value << '\n';
// no delete needed - the memory is reclaimed when `value` goes out of scope
```

`std::make_unique` is preferred over `new` because it cannot leak: if
construction fails, the allocation is freed for you.

**Containers manage their own memory.** `std::vector`, `std::string` and
`std::map` allocate on the heap internally and release it in their
destructors. In practice, using a container instead of a raw `new`-ed array
removes almost every leak from a program.

```cpp
std::vector<int> numbers(1000);   // heap-allocated, freed automatically
```

## Example
```cpp
#include <iostream>
#include <memory>

int* leaky_allocate() {
    int* value = new int(42);
    return value;          // BUG: the local pointer dies, memory leaks
}

void safe_delete() {
    int* value = new int(42);
    std::cout << "value is " << *value << '\n';
    delete value;
    value = nullptr;
    std::cout << "deleted safely\n";
}

void double_free() {
    int* value = new int(7);
    delete value;
    // delete value;     // UNCOMMENT: undefined behaviour, often a crash
}

int main() {
    // 1. Automatic storage: created and destroyed by scope.
    {
        int local = 42;
        std::cout << "stack local     = " << local << '\n';
    }

    // 2. Explicit heap allocation.
    safe_delete();
    double_free();

    // 3. RAII: the recommended approach.
    auto owned = std::make_unique<int>(99);
    std::cout << "unique_ptr owns = " << *owned << '\n';
    // Freed automatically here - nothing to remember.

    // 4. Containers manage their own memory.
    auto buffer = std::make_unique<int[]>(1000);
    buffer[999] = 7;
    std::cout << "buffer[999]     = " << buffer[999] << '\n';

    // 5. Deleting nullptr is safe.
    int* empty = nullptr;
    delete empty;
    std::cout << "delete nullptr  = no crash\n";

    // Deliberately not calling leaky_allocate(): it leaks on purpose.
    std::cout << "\nFor contrast, leaky_allocate() would leak its 4 bytes.\n";
    return 0;
}
```

## Knowledge checks
Q: What happens to a local variable when its enclosing function returns?
A: It is destroyed automatically and its stack memory is reclaimed. No explicit action is needed.
Q: What is the difference between a memory leak and a double free?
A: A leak is memory that was allocated and never released, so it stays lost for the program's lifetime. A double free is releasing the same memory twice, which is undefined behaviour.
Q: Why is `std::make_unique` preferred over `new`?
A: The returned smart pointer frees the memory automatically when it goes out of scope, and if construction throws the allocation is still released, so it cannot leak.
Q: What must match a `new[]` allocation?
A: A `delete[]`. Using plain `delete` on array memory is undefined behaviour.

## Exercise
Write three functions and observe their differences:

1. `int* leaks_memory()` — allocates with `new`, returns the pointer, never deletes.
2. `int* frees_memory()` — allocates with `new` and deletes before returning a *copy* of the value.
3. `std::unique_ptr<int> owns_memory()` — allocates with `make_unique` and returns the smart pointer.

```cpp starter
#include <iostream>
#include <memory>

int* leaks_memory() {
    // new an int holding 42 and return the raw pointer without deleting it.
}

int* frees_memory() {
    // new an int, read the value out, delete it, return a pointer to that value.
}

std::unique_ptr<int> owns_memory() {
    // return a make_unique<int>(42)
}

int main() {
    // Call all three. For the first two, dereference and print.
    // Remember to delete anything you own from the first two.
    // Watch how the third needs no manual cleanup.
    return 0;
}
```

## Common mistakes
- **Forgetting `delete`.** Memory is never reclaimed.
- **Deleting twice.** Undefined behaviour.
- **`delete` on a stack address.** Never free an automatic variable.
- **Mixing `new[]` with `delete`.** Must use `delete[]`.
- **Using a pointer after deleting it.** Dangling pointer; set it to `nullptr` afterwards.
- **Not calling `delete` on a factory-returned pointer.** The single most common real-world leak.

## Recap
- Stack: automatic, fast, freed on scope exit.
- Heap: explicit `new`/`delete`, manual, error-prone.
- `static` and globals live for the whole program.
- Leaks, dangling pointers and double frees are the three failures to watch.
- Prefer `std::unique_ptr`, containers and RAII over raw `new`.