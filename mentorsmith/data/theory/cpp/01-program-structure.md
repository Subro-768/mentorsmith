---
id: 01-program-structure
title: Program Structure & Compilation Model
order: 1
lesson_id: 01-program-structure
summary: The C++ translation unit, entry points, preprocessor mechanics, and compilation pipeline.
tags: compilation, translation-unit, preprocessor, entry-point
source_book: Object Oriented Programming with C++
source_author: Dhamodharan G, Balasubramanian, Priya K
source_chapter: 2
source_page: 3
---

# 1. Program Structure & Compilation Model

### The C++ Compilation Pipeline
Understanding C++ begins with recognizing that it is not interpreted or executed directly from text. Every C++ program travels through a rigorous multi-stage pipeline:

```
Source (.cpp) ──> Preprocessor ──> Compiler ──> Assembler ──> Linker ──> Binary
```

1. **Preprocessing (`cpp`)**: Evaluates directives starting with `#` (`#include`, `#define`, `#ifdef`). It textually replaces headers and strips comments.
2. **Compilation (`cc1plus`)**: Parses tokens, builds the Abstract Syntax Tree (AST), performs type checking, and generates native machine assembly.
3. **Assembly (`as`)**: Converts assembly into machine-readable object files (`.o` or `.obj`).
4. **Linking (`ld`)**: Resolves symbol references across multiple object files and static/dynamic libraries, uniting them into a single runnable executable.

---

### The `main` Function Contract
In standard C++, `main` is the distinct operating system entry point.

```cpp
int main(int argc, char* argv[]) {
    // Return status: 0 represents EXIT_SUCCESS
    return 0;
}
```

- **Return Type**: `main` must return `int`. Falling off the end implicitly returns `0` (guaranteed by ISO C++ standards since C++98), but explicit returns convey clarity.
- **Parameters**:
  - `argc`: Argument count (always $\ge 1$, where `argv[0]` is the invoked program name).
  - `argv`: An array of null-terminated C-strings representing arguments passed from the shell.

---

### Header Inclusion & Translation Units
Each source file (`.cpp`) along with all the headers it recursively includes constitutes a **Single Translation Unit (TU)**.

- **`<header>` vs `"header.h"`**:
  - Angle brackets `<...>` instruct the preprocessor to search standard library and system system include paths.
  - Double quotes `"..."` instruct the preprocessor to search relative to the current file first, falling back to system paths.
- **Header Guards & `#pragma once`**:
  Without guards, including a header multiple times causes redefinition errors:
  ```cpp
  #ifndef MODULE_NAME_H
  #define MODULE_NAME_H
  // Declarations
  #endif
  ```

---

### Namespaces: Preventing Symbol Collision
The C++ Standard Library is wrapped entirely within `namespace std`. 

```cpp
// Explicit scope resolution avoids namespace pollution:
std::cout << "Predictable and robust" << std::endl;
```
> **Best Practice Tip**: Avoid `using namespace std;` in header files. It leaks thousands of symbols into every translation unit that includes the header.
