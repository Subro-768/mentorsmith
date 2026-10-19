---
id: 03-input-output
title: Stream I/O Architecture & Formatting
order: 3
lesson_id: 03-input-output
summary: Deep dive into iostream, stream states, buffering, cin extraction pitfalls, and fast I/O.
tags: iostream, streams, cin, cout, formatting
source_book: Object Oriented Programming with C++
source_author: Dhamodharan G, Balasubramanian, Priya K
source_chapter: 11
source_page: 55
---

# 3. Stream I/O Architecture & Formatting

### The I/O Stream Hierarchy
C++ models input and output as abstract sequential flows of bytes through the `iostream` class hierarchy:
- `std::cin`: Standard input stream (buffered).
- `std::cout`: Standard output stream (buffered).
- `std::cerr`: Standard error stream (unbuffered, immediately flushed).
- `std::clog`: Standard logging stream (buffered error stream).

---

### Stream Extraction & State Flags
Streams maintain internal state bits:
- `goodbit`: No error occurred.
- `failbit`: Logical conversion error (e.g., trying to read an integer from characters `"hello"`).
- `badbit`: Irrecoverable loss of stream data or hardware fault.
- `eofbit`: End of file reached.

```cpp
int age;
if (!(std::cin >> age)) {
    std::cin.clear(); // Clear error flags
    std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '
'); // Discard bad input
}
```

---

### Fast Competitive Programming I/O
By default, `std::cin` syncs with standard C `stdio` (`scanf`/`printf`) and is tied to `std::cout`. In high-throughput systems:
```cpp
std::ios_base::sync_with_stdio(false);
std::cin.tie(nullptr);
```
This decouples the streams and drastically cuts I/O overhead.
