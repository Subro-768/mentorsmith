---
id: 14-constructors-encapsulation
title: Constructors, Destructors & The Rule of 5
order: 14
lesson_id: 14-constructors-encapsulation
summary: Member initializer lists, explicit constructors, move semantics, and the Rule of Five.
tags: constructors, destructors, rule-of-5, move-semantics
source_book: Object Oriented Programming with C++
source_author: Dhamodharan G, Balasubramanian, Priya K
source_chapter: 6
source_page: 31
---

# 14. Constructors, Destructors & The Rule of 5

### Member Initializer Lists
Always initialize member fields in the constructor initializer list rather than in the constructor body:
```cpp
class Entity {
    std::string name;
public:
    // Efficient: initializes 'name' directly with s
    Entity(std::string s) : name(std::move(s)) {}
};
```

---

### The Rule of Five
If a class manually manages an owned raw resource, it must implement all 5 special member functions:
1. Destructor
2. Copy Constructor
3. Copy Assignment Operator
4. Move Constructor
5. Move Assignment Operator
