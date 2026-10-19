---
id: 16-exceptions-and-error-handling
title: Exceptions, Stack Unwinding & Exception Safety
order: 16
lesson_id: 16-exceptions-and-error-handling
summary: Try/catch mechanics, stack unwinding, noexcept guarantees, and the three exception safety levels.
tags: exceptions, stack-unwinding, noexcept, error-handling
source_book: Object Oriented Programming with C++
source_author: Dhamodharan G, Balasubramanian, Priya K
source_chapter: 12.2
source_page: 61
---

# 16. Exceptions, Stack Unwinding & Exception Safety

### Stack Unwinding
When an exception is thrown, the runtime traverses upward through the call stack until it finds a matching `catch` block. During this traverse, all local objects in each popped stack frame have their **destructors executed in reverse order of creation**.

---

### The Three Guarantees of Exception Safety
1. **Basic Guarantee**: No resources leak; invariants are preserved.
2. **Strong Guarantee**: If an operation throws, state rolls back to what it was before the call (transactional).
3. **Nothrow Guarantee (`noexcept`)**: The function promises never to throw an exception.
