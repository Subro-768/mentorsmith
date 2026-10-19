---
id: 15-file-handling
title: File Streams & Persistent Storage
order: 15
lesson_id: 15-file-handling
summary: fstream, ifstream, ofstream, binary I/O, and OS file descriptor management.
tags: files, fstream, binary-io, persistence
source_book: Object Oriented Programming with C++
source_author: Dhamodharan G, Balasubramanian, Priya K
source_chapter: 11
source_page: 55
---

# 15. File Streams & Persistent Storage

### File Streams
- `std::ifstream`: Read-only file stream.
- `std::ofstream`: Write-only file stream.
- `std::fstream`: Bidirectional file stream.

File streams close their file descriptor automatically in their destructor via RAII:

```cpp
{
    std::ofstream out("log.txt", std::ios::app);
    out << "Transaction complete
";
} // File closed immediately here
```
