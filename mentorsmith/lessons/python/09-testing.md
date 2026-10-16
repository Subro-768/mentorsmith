---
id: 09-testing
title: Testing
order: 9
---

## Objectives
- Write tests with `pytest`.
- Cover normal cases, boundaries and invalid input.
- Test what should happen *and* what should be rejected.
- Keep tests independent of each other.

## Explanation
A test states an expected outcome and fails loudly when reality disagrees.
`pytest` runs plain functions whose names start with `test_`:

```python
# test_calc.py
import pytest
from calc import add, divide

def test_add_returns_the_sum():
    assert add(2, 3) == 5

def test_divide_rejects_zero():
    with pytest.raises(ValueError):
        divide(1, 0)
```

`assert` is the whole assertion language you need. `pytest.raises` asserts that
something is *supposed* to fail — an important half of testing.

**What to cover.** Three kinds of case, and the second is the one people skip:

1. **Normal** — the ordinary successful path.
2. **Boundary** — zero, one, empty, very large, exactly on a threshold.
3. **Invalid** — the wrong type, a negative where positive is required.

```python
@pytest.mark.parametrize("a,b,expected", [
    (0, 0, 0),          # boundary
    (-3, 4, 1),         # negative
    (2.5, 0.5, 3.0),    # floats
])
def test_divide(a, b, expected):
    assert divide(a, b) == expected
```

`parametrize` runs one test body over many inputs, so each case shows up
separately in the report.

**Keep tests independent.** A test must pass on its own, regardless of the order
tests run in. Use fixtures for setup instead of relying on earlier tests.

**Testing the code under test.** Import the real function rather than copying its
logic into the test. A test that reimplements the logic only proves the two
copies agree.

Run them:

```bash
python3 -m pytest -q
python3 -m pytest test_calc.py::test_add_returns_the_sum -v
```

## Example
```python
# test_stats_tool.py
import pytest

from stats_tool import summarise, best_index


def test_mean_of_known_values():
    report = summarise([2, 4, 6])
    assert report["count"] == 3
    assert report["mean"] == pytest.approx(4.0)


def test_single_value_has_zero_stdev():
    # Boundary: stdev is undefined for one sample, so we report 0.0.
    assert summarise([5])["stdev"] == 0.0


def test_empty_list_is_rejected():
    with pytest.raises(ValueError):
        summarise([])


def test_best_index_finds_the_maximum():
    assert best_index([3, 9, 4]) == 1


def test_best_index_returns_first_of_a_tie():
    assert best_index([5, 5, 1]) == 0


def test_best_index_rejects_empty():
    with pytest.raises(ValueError):
        best_index([])


@pytest.mark.parametrize("values,expected", [
    ([1], 1),               # single element
    ([0, 0, 0], 0),         # all equal
    ([-5, -1, -9], 1),      # all negative
])
def test_best_index_edge_cases(values, expected):
    assert best_index(values) == expected
```

Expected output:

```text
........                                                          [100%]
8 passed
```

## Knowledge checks
Q: Why test that something *fails* as well as that it succeeds?
A: Because rejecting invalid input is part of the behaviour. Without those tests, a validator could be silently removed and the suite would stay green.
Q: What is the boundary between normal and boundary cases?
A: Boundary inputs sit on an edge of the valid range: zero, one, empty, the largest accepted value, or exactly on a threshold.
Q: Why must tests be independent?
A: Order dependence means a failure in one test causes unrelated failures, which wastes debugging time and hides real problems.
Q: Why is `pytest.approx` used for the mean?
A: Floating point arithmetic is approximate, so `==` on computed values is unreliable.

## Exercise
Write tests for `divide(a, b)`: a normal division, division by a decimal, zero
numerator, division by a negative number, and the two invalid cases (zero
divisor, and a string argument) using `pytest.raises`.

```python starter
import pytest


# test_divide.py
def test_normal_division():
    # assert divide(7, 2) == 3.5


def test_zero_dividend():
    # assert divide(0, 5) == 0.0


def test_zero_divisor_is_rejected():
    # with pytest.raises(...): divide(1, 0)


def test_non_numeric_argument_is_rejected():
    # with pytest.raises(TypeError): divide("a", 1)
```

## Common mistakes
- **Only testing the happy path.** Invalid input is where bugs hide.
- **Copying the implementation into the test.** Test the real code.
- **Comparing floats with `==`.** Use `pytest.approx`.
- **Tests depending on order or on shared mutable state.**
- **Asserting on a whole object,** which breaks on any unrelated field change. Assert on the field you care about.

## Recap
- Plain functions named `test_*`, with `assert`.
- `pytest.raises` for behaviour that must be rejected.
- Cover normal, boundary and invalid cases.
- `@pytest.mark.parametrize` runs one body over many inputs.
- Tests must be independent and must test the real code.