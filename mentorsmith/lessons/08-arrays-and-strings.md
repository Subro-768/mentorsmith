---
id: 08-arrays-and-strings
title: Arrays and Strings
order: 8
---

## Objectives
- Declare and use a fixed-size C-style array.
- Understand the relationship between `std::array` and C arrays.
- Use `std::string` for text and `std::vector` for growable sequences.
- Avoid buffer overflows and off-by-one indexing.

## Explanation
An array stores a fixed number of elements of one type, contiguously in memory.
The size must be a compile-time constant:

```cpp
int scores[5];                       // 5 uninitialised ints - garbage values
int totals[3] = {10, 20, 30};        // initialised
std::string names[2] = {"Ada", "Alan"};
```

C++11 introduced `std::array`, which behaves like a C array but knows its own
size and supports range-based iteration. Prefer it:

```cpp
#include <array>

std::array<int, 5> scores{};
scores[0] = 90;                        // zero-initialised, unlike a raw array
std::cout << scores.size();            // 5, no sizeof division needed
for (int s : scores) std::cout << s << ' ';
```

**Indexing starts at 0.** For a 5-element array the valid indexes are 0 to 4.
`scores[5]` is out of bounds — it reads or writes memory that is not yours.
C++ does *not* check array bounds at runtime, so this is a real source of
crashes and security bugs, not just a compile warning. Use `.at(i)` on
`std::vector` or `std::array` when you want a bounds check that throws.

**`std::string`** handles text safely and manages its own memory:

```cpp
#include <string>

std::string name = "Ada";
name += " Lovelace";              // concatenate
name.size();                      // length as std::size_t
name[0];                          // 'A' - unchecked, may be out of range
name.at(0);                       // 'A' - checked, throws if out of range
bool empty = name.empty();
```

Note the size difference: `s.size()` returns `std::size_t`, an *unsigned* type.
Comparing `int i < s.size()` produces a signed/unsigned warning and is a bug
waiting to happen. Either declare `i` as `std::size_t` or cast explicitly.

**`std::vector`** is the growable array. Use this whenever the size is not known
when you write the code:

```cpp
#include <vector>

std::vector<int> scores{80, 90, 75};
scores.push_back(92);             // grow by one
scores.at(0) = 81;                // checked access
for (std::size_t i = 0; i < scores.size(); ++i) {
    std::cout << i << ": " << scores.at(i) << '\n';
}
```

## Example
```cpp
#include <array>
#include <iostream>
#include <numeric>
#include <string>
#include <vector>

int main() {
    std::array<int, 5> marks{70, 85, 92, 60, 78};

    std::size_t total = 0;
    for (int mark : marks) {
        total += static_cast<std::size_t>(mark);
    }
    const double average = static_cast<double>(total) / marks.size();
    std::cout << "marks: " << marks.size()
              << " | average: " << average << '\n';

    std::string word = "tutor";
    std::cout << "\"" << word << "\" has " << word.size() << " characters\n";
    std::cout << "first letter: " << word.at(0)
              << ", last letter: " << word.at(word.size() - 1) << '\n';

    std::vector<std::string> topics{"variables", "loops", "functions"};
    topics.push_back("pointers");
    std::cout << "topics: " << topics.size() << '\n';
    for (const std::string& topic : topics) {
        std::cout << "  - " << topic << '\n';
    }

    const int sum = std::accumulate(marks.begin(), marks.end(), 0);
    std::cout << "accumulated sum: " << sum << '\n';
    return 0;
}
```

## Knowledge checks
Q: What are the valid indexes for a 5-element array?
A: 0 through 4. Index 5 is out of bounds and is not checked at runtime.
Q: Why prefer `std::array<int, 5>` over `int arr[5]`?
A: `std::array` knows its own size, zero-initialises with `{}`, and supports range-based iteration without a separate length variable.
Q: What does `.at(9)` do when the container has only 5 elements?
A: It throws `std::out_of_range` instead of reading unrelated memory. Plain `operator[]` does not check.
Q: Why does comparing `int i < name.size()` generate a warning?
A: `size()` returns the unsigned `std::size_t`, and comparing a signed `int` against an unsigned value can behave wrongly for negative `i`.

## Exercise
Build a `std::vector<int>` from five marks entered by the user. Print them in
original order, then print them in reverse, then print the highest and lowest.
Use `.at()` for indexing and check that each entry is a number.

```cpp starter
#include <iostream>
#include <vector>

int main() {
    std::vector<int> marks;

    // Read 5 marks, appending each with push_back.
    // Reject (with a message and return 1) any entry that is not an integer.

    // Print them in order, in reverse, then print the max and min.
    return 0;
}
```

Extension: replace the loop that finds the maximum with `std::max_element`
from `<algorithm>` and compare the two approaches.

## Common mistakes
- **Iterating `i <= size()`.** Valid range is `i < size()`.
- **Using `sizeof(arr) / sizeof(arr[0])`.** That trick works only on real arrays; it is wrong for pointers and unnecessary with `std::array`.
- **Assuming `std::string` indexing is bounds-checked.** It is not — use `.at()`.
- **Comparing signed loop counters against `.size()`.** Prefer `std::size_t`.
- **Mixing `>>` and `getline` when reading a line of words.** Clear the stream first.

## Recap
- Raw arrays have a fixed compile-time size and no bounds checking.
- `std::array` adds size awareness and safe initialisation.
- Index from 0 to `size() - 1`.
- `std::vector` is the right default when the size is not fixed.
- Prefer `.at()` when you want a checked access.