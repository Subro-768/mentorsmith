---
id: 02-variables-and-types
title: Primitive Types, Object Wrappers & Memory Layout
order: 2
lesson_id: 02-variables-and-types
summary: 8 primitives vs references, autoboxing overhead, object headers, and variable widening.
tags: primitives, autoboxing, wrappers, memory-layout
---

# 2. Primitive Types, Object Wrappers & Memory Layout

### The 8 Primitive Types
Java defines exactly eight primitive types with fixed bit-widths across all hardware architectures:

| Primitive | Width | Default Value | Wrapper Class |
|---|---|---|---|
| `byte` | 8 bits | `0` | `Byte` |
| `short` | 16 bits | `0` | `Short` |
| `int` | 32 bits | `0` | `Integer` |
| `long` | 64 bits | `0L` | `Long` |
| `float` | 32 bits | `0.0f` | `Float` |
| `double` | 64 bits | `0.0d` | `Double` |
| `boolean` | 1 bit (effective JVM byte) | `false` | `Boolean` |
| `char` | 16 bits (UTF-16) | `'\u0000'` | `Character` |

---

### The Autoboxing Hidden Cost
Autoboxing converts automatically between primitives and wrapper objects. However, every `Integer` allocates an object on the heap with a 12-to-16 byte object header! Using boxed types in tight numeric loops creates intense garbage collection pressure.
