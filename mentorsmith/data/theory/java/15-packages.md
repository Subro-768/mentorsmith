---
id: 15-packages
title: Packages, Imports & Class Organisation
order: 15
lesson_id: 15-packages
summary: Declaring a package, the standard library's main packages, import rules, and why package names must match the folder layout.
tags: packages, imports, namespace, classpath
source_book: Programming with Java: A Primer
source_author: E. Balagurusamy
source_chapter: 11
source_page: 192
---

# 15. Packages, Imports & Class Organisation

A package is a namespace. It stops two classes with the same simple name
from colliding, and it groups related classes into a directory tree that
matches how they are built.

```java
package com.example.billing;

public class Invoice { }
```

The package name maps to folders: `com/example/billing/Invoice.class`.

### Naming
The convention is the reverse of a web address - `com.example.billing`, not
`billing.example.com` - so that the parts read from most general to most
specific. The first part usually names the organisation, and the last part
the project or package inside it.

### Importing
```java
import java.util.List;              // one type
import java.util.*;                 // everything in a package
import static java.lang.Math.max;   // one static member
```

The classes in `java.lang` - `String`, `Integer`, `System` - are imported
automatically. `java.util` is not, which is why `List` needs an import
while `String` does not.

`import` is not a copy. It lets you refer to a type by its short name; the
class still lives in its own package, and the fully qualified name always
works:

```java
java.util.List<String> names = new java.util.ArrayList<>();
```

### Two types of clash
If two imported packages both contain a simple name, using it is a compile
error - Java will not guess. Resolve it by qualifying the name
(`java.util.List` vs `java.awt.List`), or by importing one specific type.

### The standard library's main packages
| Package | Holds |
|---|---|
| `java.lang` | the core: `String`, `Object`, `Integer`, `System` |
| `java.util` | collections, `Date`, `Random`, `Optional` |
| `java.io` | streams and files |
| `java.net` | sockets, URLs |
| `java.time` | dates and times (`LocalDate`, `Duration`) |
| `java.util.function` | functional interfaces: `Function`, `Predicate` |
| `java.util.stream` | stream processing |

### Common mistakes
- Putting the file in the wrong folder for its package: the compiler
  reports "class ... is public, should be declared in a file named ...".
- Forgetting `package` on a file that is in a package directory.
- Assuming `import java.util.*` makes the program slower - it changes
  nothing at run time, since the class file names are fully qualified.
- Reaching for `java.awt.*` and `java.util.*` together, which makes
  `List` ambiguous.

### Review questions
1. What does a package actually provide, beyond a folder to put files in?
2. Why is the package name written in the reverse of a domain name?
3. Which package is imported automatically, and what is in it?
4. What happens if two imported packages both contain a type called `List`
   and you use `List` unqualified?
5. Does `import` affect the compiled class file's contents? Why or why not?
6. A class is declared `package com.example.tools;` but the file sits in
   `com/example/`. What does the compiler say?
7. Name three standard library packages and one type from each.
8. What does a static import bring into scope, and when is it a good idea?

### Practice
Create a package `com.example.geometry` with a class `Rectangle` and
another package `com.example.app` with a class `Main` that uses it. Compile
with the directory layout `javac -d out com/example/geometry/Rectangle.java
com/example/app/Main.java` and run it from the `out` directory so the
classpath resolves.
