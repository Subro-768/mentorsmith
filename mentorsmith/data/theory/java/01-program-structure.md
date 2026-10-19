---
id: 01-program-structure
title: JVM Architecture, Bytecode & Class Loading
order: 1
lesson_id: 01-program-structure
summary: The JVM execution model, JIT compilation, classloaders, and the main entry point.
tags: jvm, bytecode, jit, classloader
---

# 1. JVM Architecture, Bytecode & Class Loading

### The "Write Once, Run Anywhere" Reality
Java compiles source (`.java`) into intermediate platform-neutral **bytecode** (`.class`). The **Java Virtual Machine (JVM)** interprets this bytecode or compiles hot execution paths into native machine instructions via the **Just-In-Time (JIT) Compiler** (HotSpot C1/C2 compilers).

```
Main.java ──(javac)──> Main.class (Bytecode) ──(JVM/JIT)──> Native Machine Code
```

---

### ClassLoader Hierarchy
Classes are dynamically loaded into memory by three hierarchical loaders:
1. **Bootstrap ClassLoader**: Loads core JDK classes (`java.lang.*`).
2. **Platform/Extension ClassLoader**: Loads platform modular extensions.
3. **Application ClassLoader**: Loads classes found on the user's `-classpath` or `--class-path`.

---

### The Strict File-Class Naming Constraint
In Java, a `public class Foo` **must** reside in a file named exactly `Foo.java`. This enables the compiler and JVM to immediately locate type definitions on disk without scanning all files.
