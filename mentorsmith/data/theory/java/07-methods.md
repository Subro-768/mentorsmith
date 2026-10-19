---
id: 07-methods
title: Methods, Parameter Passing & Overloading
order: 7
lesson_id: 07-methods
summary: Strictly pass-by-value semantics in Java, stack activation, varargs, and overload resolution rules.
tags: methods, pass-by-value, overloading, varargs
source_book: Programming with Java: A Primer
source_author: E. Balagurusamy
source_chapter: 8
source_page: 126
---

# 7. Methods, Parameter Passing & Overloading

### Java Is Strictly Pass-by-Value
A common point of confusion: **Java is 100% pass-by-value**:
- When passing a primitive (`int`), a copy of the primitive value is passed.
- When passing an object, a **copy of the reference pointer** is passed by value.

```java
void modify(Dog d) {
    d.setName("Rover"); // Modifies the object in the heap!
    d = new Dog("Fido"); // Overwrites only the local pointer copy, caller unaffected!
}
```
