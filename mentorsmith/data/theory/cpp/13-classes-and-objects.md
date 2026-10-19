---
id: 13-classes-and-objects
title: Classes, Objects & The Object Model
order: 13
lesson_id: 13-classes-and-objects
summary: Encapsulation, access specifiers, the this pointer, const member functions, and memory overhead.
tags: oop, classes, this-pointer, const-methods
source_book: Object Oriented Programming with C++
source_author: Dhamodharan G, Balasubramanian, Priya K
source_chapter: 5
source_page: 23
---

# 13. Classes, Objects & The Object Model

### Anatomy of an Object
In C++, a class without virtual methods has **zero runtime memory overhead** compared to a raw C struct:

```cpp
class Timer {
private:
    uint64_t start_tick;

public:
    void reset();
    uint64_t elapsed() const; // Cannot modify any member variables!
};
```

### The Implicit `this` Pointer
Inside non-static member functions, `this` is a pointer to the invoking instance (`Timer* const this`). When marking a method `const`, `this` becomes `const Timer* const this`.
