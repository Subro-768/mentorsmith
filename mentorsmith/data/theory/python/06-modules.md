---
id: 06-modules
title: Modules, Packages & Import Machinery
order: 6
lesson_id: 06-modules
summary: sys.path resolution, sys.modules cache, the __name__ guard, and circular imports.
tags: modules, imports, packages, sys.modules
---

# 6. Modules, Packages & Import Machinery

### Import Mechanics
When Python imports a module:
1. Checks `sys.modules` cache. If already imported, returns it immediately.
2. Locates module file along `sys.path`.
3. Compiles source code to bytecode (`.pyc`).
4. Executes the module body in its own namespace (`globals()`).
5. Caches the resulting module object in `sys.modules`.

---

### The `__name__ == '__main__'` Guard
When run directly from CLI, `__name__` is set to `"__main__"`. When imported by another module, `__name__` is the module's qualified import name.
