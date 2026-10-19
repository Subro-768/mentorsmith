---
id: 03-input-output
title: Streams, Buffering & Modern Scanner I/O
order: 3
lesson_id: 03-input-output
summary: InputStream, Reader/Writer abstraction, Scanner regex parsing, and high-performance BufferedReader.
tags: io, streams, scanner, bufferedreader
source_book: Programming with Java: A Primer
source_author: E. Balagurusamy
source_chapter: 16.4
source_page: 290
---

# 3. Streams, Buffering & Modern Scanner I/O

### Byte Streams vs Character Streams
Java divides I/O into two parallel hierarchies:
- **Byte Streams (`InputStream` / `OutputStream`)**: Read/write raw 8-bit binary bytes.
- **Character Streams (`Reader` / `Writer`)**: Handle 16-bit Unicode characters with automatic character set encoding translation.

---

### Scanner vs `BufferedReader`
- `Scanner`: Convenient tokenization using regular expressions. Slower for massive data.
- `BufferedReader`: Buffers chunks of characters in a memory array. Significantly faster for reading high-volume lines.
