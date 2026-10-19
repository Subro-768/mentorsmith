---
id: 15-packages
title: Packages and Imports
order: 15
tier: core
---

## Objectives
- Declare a package and match it to a folder layout.
- Import a class, a whole package, or a single static member.
- Name the standard library packages worth knowing.
- Resolve two imported types with the same simple name.

## Explanation
A package is a namespace. It keeps two classes with the same name apart and
gives the project a directory structure that matches its code.

```java
package com.example.billing;

public class Invoice { }
```

- The package name maps to folders: `com/example/billing/Invoice.class`.
- The convention is the reverse of a web address - `com.example.billing` - so it reads from general to specific.
- `import java.util.List;` imports one type, `import java.util.*;` imports a package, `import static java.lang.Math.max;` imports one static member.
- `java.lang` is imported automatically; `java.util` is not.

If two imported packages both contain a `List`, using the name unqualified is
a compile error - Java will not guess. Qualify it (`java.util.List`).

## Example
```java
package com.example.app;

import java.util.ArrayList;
import java.util.List;

public class Main {
    public static void main(String[] args) {
        List<String> names = new ArrayList<>();
        names.add("Ada");
        System.out.println(names);
    }
}
```

## Knowledge checks
Q: Which package is imported automatically?
A: `java.lang` - it holds `String`, `Object`, `Integer`, `System` and the rest of the core.
Q: Does `import java.util.*;` make the program slower at run time?
A: No. The class files are already fully qualified; an import only changes which name you may type.
Q: What happens if two imported packages both contain a type called `List`?
A: Using `List` unqualified is a compile error until you qualify it or import one specific type.
Q: Why is the package name written backwards compared to a domain name?
A: So it reads from the most general part to the most specific, and so it can be derived from a domain the organisation owns.
Q: Name three standard library packages.
A: Any three of `java.lang`, `java.util`, `java.io`, `java.net`, `java.time`, `java.util.function`, `java.util.stream`.

## Exercise
Create a package `com.example.geometry` containing a class `Rectangle` with a `width`, a `height` and an `area()` method. Create a second package `com.example.app` containing a `Main` that uses it. Compile with `javac -d out com/example/geometry/Rectangle.java com/example/app/Main.java` and run it from the `out` directory.

```java starter
package com.example.app;

public class Main {
    public static void main(String[] args) {
        // Use com.example.geometry.Rectangle
    }
}
```

## Common mistakes
- Declaring `package com.example.tools;` in a file that lives somewhere else - the compiler says the class should be in a file of a matching name.
- Forgetting the `package` line in a file inside a package folder.
- Importing `java.awt.*` and `java.util.*` together, which makes `List` ambiguous.

## Recap
- A package is a namespace and a folder.
- The folder layout must match the package name.
- `java.lang` is automatic; everything else is imported.
