---
id: 10-encapsulation
title: Encapsulation, Access Levels & Invariant Preservation
order: 10
lesson_id: 10-encapsulation
summary: Public, protected, package-private, and private access specifiers, defensive copying, and record classes.
tags: encapsulation, access-modifiers, records, immutability
---

# 10. Encapsulation, Access Levels & Invariant Preservation

### Access Modifier Matrix
Java provides four distinct visibility tiers:

| Modifier | Class | Package | Subclass | World |
|---|---|---|---|---|
| `public` | Yes | Yes | Yes | Yes |
| `protected` | Yes | Yes | Yes | No |
| *(default)* | Yes | Yes | No | No |
| `private` | Yes | No | No | No |

---

### Java 14+ Record Classes
For pure immutable data carrier objects, Java records eliminate boilerplate getters, constructors, `equals`, `hashCode`, and `toString`:

```java
public record User(String username, int age) {}
```
