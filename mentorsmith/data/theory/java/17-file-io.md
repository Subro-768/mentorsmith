---
id: 17-file-io
title: File Streams, Readers & Writers
order: 17
lesson_id: 16-file-io
summary: InputStream and OutputStream, Reader and Writer, the try-with-resources pattern, and reading text line by line.
tags: io, streams, files, readers, writers
source_book: Programming with Java: A Primer
source_author: E. Balagurusamy
source_chapter: 16
source_page: 287
---

# 17. File Streams, Readers & Writers

Java splits its I/O into two hierarchies, and the split is the thing to
remember: **streams** work in bytes, **readers and writers** work in
characters.

```
InputStream ── FileInputStream, System.in
OutputStream ─ FileOutputStream, System.out

Reader ── FileReader, InputStreamReader
Writer ── FileWriter, OutputStreamWriter
```

### Bytes or characters?
A byte stream is a raw pipeline: whatever is in the file comes out, byte for
byte. A character stream decodes using a character set on the way in and
encodes on the way out. For text, use a character stream - a byte stream
will happily split a multi-byte character in half.

### Reading a file
```java
try (BufferedReader reader = new BufferedReader(new FileReader("notes.txt"))) {
    String line;
    while ((line = reader.readLine()) != null) {
        System.out.println(line);
    }
}
```

`BufferedReader` wraps a `Reader` and buffers it, which is what makes
line-by-line reading efficient. Reading byte-at-a-time from an unbuffered
stream is far slower than it needs to be.

### try-with-resources
The `try (...)` form closes every resource when the block ends, whether it
ended normally or by an exception. Written by hand, the same code needs a
`finally` block, and forgetting the `close()` there is a classic leak:

```java
try (BufferedReader reader = new BufferedReader(new FileReader("notes.txt"))) {
    ...
}   // closed here, even if the body threw
```

The resource is declared with `var` when the type is long:

```java
try (var in = new FileInputStream("data.bin")) { ... }
```

### Writing
```java
try (BufferedWriter writer = new BufferedWriter(new FileWriter("out.txt"))) {
    writer.write("first line");
    writer.newLine();
    writer.write("second line");
}   // flushed and closed
```

`FileWriter` truncates an existing file. To append, use
`new FileWriter("out.txt", true)`.

### Where things live
```java
File dir = new File("data");
if (!dir.exists() && !dir.mkdirs()) {
    throw new IOException("cannot create " + dir);
}
File file = new File(dir, "notes.txt");
if (file.exists()) {
    long size = file.length();
}
```

`mkdirs()` creates the whole path, unlike `mkdir()`, which creates only the
last component.

### The `Path` API
The newer `java.nio.file` API is worth preferring for new code:

```java
Path path = Path.of("data", "notes.txt");
List<String> lines = Files.readAllLines(path);
Files.write(path, List.of("a", "b"));
```

It is shorter, and it throws `IOException` rather than a checked exception
that is easy to swallow.

### Common mistakes
- Forgetting to close a stream: the file may not be flushed, and on Windows
  the file stays locked.
- Using `FileReader`/`FileWriter` without specifying a character set - the
  default charset varies by machine, and files written on one can be
  unreadable on another.
- Writing to a `FileWriter` for a file that already has content, and
  silently destroying it.
- Catching `IOException` and printing it, losing the real cause.

### Review questions
1. What is the difference between the stream hierarchy and the
   reader/writer hierarchy, and when do you need each?
2. Why is reading a text file with a byte stream risky?
3. What does try-with-resources do that a `finally` block does not?
4. Why does a `BufferedReader` make line-by-line reading much faster?
5. What does `new FileWriter(path, true)` change?
6. When would you use `mkdirs()` rather than `mkdir()`?
7. Why should you specify a character set explicitly when writing text?
8. Name one situation where `Files.readAllLines` is a worse choice than a
   `BufferedReader`, and why.

### Practice
Write a program that reads `numbers.txt` (one integer per line), doubles
each number and writes the results to `doubled.txt`. Then change it to
append rather than overwrite, and to skip any line that is not a number
without ending the program.
