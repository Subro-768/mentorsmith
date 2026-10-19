---
id: 12-exceptions
title: Exception Hierarchy, Checked vs. Unchecked & Try-With-Resources
order: 12
lesson_id: 12-exceptions
summary: Throwable tree, Error vs Exception vs RuntimeException, checked exceptions, and AutoCloseable.
tags: exceptions, checked-exceptions, try-with-resources, autocloseable
source_book: Programming with Java: A Primer
source_author: E. Balagurusamy
source_chapter: 13
source_page: 230
---

# 12. Exception Hierarchy, Checked vs. Unchecked & Try-With-Resources

### The `Throwable` Hierarchy
```
                Throwable
               /                   Exception       Error (Out Of Memory, StackOverflow)
          /         Checked Exceptions   RuntimeException (NullPointer, IndexOutOfBounds)
```
- **Checked Exceptions**: Compiler forces caller to catch or declare with `throws`.
- **Unchecked Exceptions** (`RuntimeException`): Programming errors that can happen anywhere.

---

### Try-With-Resources (`AutoCloseable`)
Any resource implementing `java.lang.AutoCloseable` is guaranteed to be closed upon exiting the block, even if an exception occurs:

```java
try (var in = new FileInputStream("data.bin")) {
    in.read();
} // Automatically and safely closed!
```
