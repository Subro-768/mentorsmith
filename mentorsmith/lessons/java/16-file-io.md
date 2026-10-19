---
id: 16-file-io
title: File Input and Output
order: 16
tier: core
---

## Objectives
- Tell a byte stream apart from a character stream.
- Read a text file line by line with `BufferedReader`.
- Use try-with-resources so files are always closed.
- Write to a file and append to it.

## Explanation
Java has two I/O hierarchies. **Streams** work in bytes; **readers and
writers** work in characters. For text, use a character stream - a byte
stream can split a multi-byte character in half.

```java
try (BufferedReader reader = new BufferedReader(new FileReader("notes.txt"))) {
    String line;
    while ((line = reader.readLine()) != null) {
        System.out.println(line);
    }
}
```

- `try (...)` closes every resource when the block ends, even if it ended with an exception. The hand-written version needs a `finally`, and forgetting the `close()` there is a classic leak.
- `BufferedReader` buffers, which is what makes line-by-line reading fast.
- `new FileWriter(path)` truncates; `new FileWriter(path, true)` appends.
- The newer `java.nio.file` API is shorter: `Files.readAllLines(path)` and `Files.write(path, lines)`.

## Example
```java
try (BufferedWriter writer = new BufferedWriter(new FileWriter("out.txt"))) {
    writer.write("first line");
    writer.newLine();
    writer.write("second line");
}
```

## Knowledge checks
Q: When do you need a character stream rather than a byte stream?
A: For text. A byte stream can split a multi-byte character between two reads.
Q: What does try-with-resources guarantee that a `finally` block does not?
A: It closes the resources for you, including when the body throws.
Q: Why wrap a reader in a `BufferedReader`?
A: Buffering cuts the number of reads from the underlying stream, which is much faster.
Q: What is the difference between `new FileWriter(f)` and `new FileWriter(f, true)`?
A: The second appends; the first truncates the file to empty first.
Q: When would `Files.readAllLines` be a worse choice than a `BufferedReader`?
A: For a file too large to fit in memory - it loads the whole thing at once.

## Exercise
Write a program that reads `numbers.txt` (one integer per line), doubles each number and writes the results to `doubled.txt`. Then change it to append rather than overwrite, and to skip any line that is not a number without ending the program.

```java starter
public class Main {
    public static void main(String[] args) {
        // Read numbers.txt, double each number, write doubled.txt
    }
}
```

## Common mistakes
- Forgetting to close the stream, so the last lines are never flushed.
- Relying on the platform default character set, so a file written on one machine is unreadable on another.
- Using `FileWriter` on a file with content you meant to keep.

## Recap
- Bytes for bytes, characters for text.
- try-with-resources closes what it opens.
- `java.nio.file` is the shorter path for new code.
