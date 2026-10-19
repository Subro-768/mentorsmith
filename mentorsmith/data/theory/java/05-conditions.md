---
id: 05-conditions
title: Conditionals, Switch Expressions & String Equality
order: 5
lesson_id: 05-conditions
summary: Reference equality vs value equality, String pool, and modern Java 14+ switch expressions.
tags: conditions, switch, string-pool, equals
source_book: Programming with Java: A Primer
source_author: E. Balagurusamy
source_chapter: 6
source_page: 81
---

# 5. Conditionals, Switch Expressions & String Equality

### The String Constant Pool & Reference Equality
Never use `==` to compare Strings!
- `==` checks whether two variables point to the identical heap address.
- `.equals()` checks whether two strings contain the identical character sequence.

```java
String s1 = "hello";
String s2 = new String("hello");
System.out.println(s1 == s2);      // FALSE! Different objects.
System.out.println(s1.equals(s2)); // TRUE! Identical text.
```

---

### Java 14+ Switch Expressions
Modern Java allows switch statements to return values directly with arrow syntax:
```java
String dayType = switch (day) {
    case SATURDAY, SUNDAY -> "Weekend";
    default -> "Weekday";
};
```
