---
id: 11-memory-concepts
title: Memory Layout, Stack, Heap & RAII
order: 11
lesson_id: 11-memory-concepts
summary: Process memory segments, stack allocation, heap allocation, RAII, and smart pointers.
tags: memory, stack, heap, raii, smart-pointers
---

# 11. Memory Layout, Stack, Heap & RAII

### Process Memory Layout
A typical compiled process virtual memory layout consists of:
```
High Memory:   [ Stack (grows downward) ]
               [ ... free space ...     ]
               [ Heap  (grows upward)   ]
               [ BSS / Uninitialized    ]
               [ Data / Initialized     ]
Low Memory:    [ Text / Instructions    ]
```

---

### RAII: Resource Acquisition Is Initialization
RAII is C++'s greatest paradigm. Resources (memory, file handles, mutex locks, network sockets) are tied to object lifetimes:
- Constructor acquires the resource.
- Destructor automatically releases the resource when the object leaves scope.

```cpp
// Modern memory ownership with smart pointers:
{
    auto ptr = std::make_unique<Resource>();
    // Resource used here
} // Destructor runs automatically here: ZERO MEMORY LEAKS!
```
