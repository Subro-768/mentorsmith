---
id: 09-classes-and-objects
title: Classes and Objects
order: 9
tier: core
---

## Objectives
- Define classes with fields and constructors.
- Instantiate objects using `new`.
- Override the `toString()` method.

## Explanation
A class is a blueprint for objects:
```java
class Student {
    String name;
    int age;

    // Constructor
    Student(String name, int age) {
        this.name = name;
        this.age = age;
    }

    @Override
    public String toString() {
        return name + " (" + age + ")";
    }
}
```

- `this` refers to the current instance.
- Constructors initialize fields when `new Student(...)` is invoked.
- `toString()` formats the object when printed.

## Example
```java
public class Main {
    static class Book {
        String title;
        Book(String title) {
            this.title = title;
        }
    }

    public static void main(String[] args) {
        Book b = new Book("Clean Code");
        System.out.println(b.title);
    }
}
```

## Knowledge checks
Q: What keyword allocates memory for a new object in Java?
A: new.
Q: What is the purpose of this keyword?
A: It references the current instance of the class.
Q: What method should you override to provide a custom string representation of an object?
A: public String toString().

## Exercise
Create a static class `Rectangle` with integer fields `width` and `height`, a constructor, and a method `area()` returning `width * height`. Instantiate it with width 4 and height 6, and print the area.

```java starter
public class Main {
    // Define static class Rectangle

    public static void main(String[] args) {
        // Create Rectangle(4, 6) and print its area
    }
}
```

## Common mistakes
- Calling methods on an uninitialized reference, producing `NullPointerException`.
- Forgetting `this.` when constructor parameters shadow field names.

## Recap
- Classes encapsulate state (fields) and behavior (methods).
- `new` creates object instances.
