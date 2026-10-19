---
id: 09-testing
title: Testing Architecture, Fixtures & Property-Based Testing
order: 9
lesson_id: 09-testing
summary: Pytest architecture, dependency injection via fixtures, test parametrization, and mock isolation.
tags: testing, pytest, fixtures, assertions
---

# 9. Testing Architecture, Fixtures & Property-Based Testing

### Why Pytest Succeeds: Pure Expressions
Unlike `unittest` (derived from Java JUnit), pytest uses plain Python `assert` statements and rewrites AST tokens during test collection to provide rich diagnostic output.

---

### Pytest Fixture Lifecycle
Fixtures provide reusable, composable setup and teardown:
```python
import pytest

@pytest.fixture
def database_connection():
    conn = create_test_db()
    yield conn  # Test runs here
    conn.close() # Clean teardown guaranteed
```
