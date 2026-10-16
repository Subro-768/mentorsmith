---
id: 02-conditions-and-loops
title: Conditions and Loops
order: 2
---

## Objectives
- Write `if` / `elif` / `else` chains.
- Use `while` and `for` loops and choose between them.
- Apply Python's `elif` (spelled differently from C++'s `else if`).
- Use `range()` correctly and avoid off-by-one errors.

## Explanation
Python's conditional is spelled `elif`, not `else if`:

```python
if score >= 90:
    grade = "A"
elif score >= 80:
    grade = "B"
elif score >= 70:
    grade = "C"
else:
    grade = "F"
```

This is one place a familiar C++ habit actively hurts. `else if` in Python is
valid but unusual, and writing it by habit signals you are not reading the code.

**`for` loops iterate over things**, unlike C++ where `for` is a counting
construct:

```python
for mark in marks:
    print(mark)

for letter in "tutor":
    print(letter)
```

To count, reach for `range()`:

```python
for i in range(5):        # 0, 1, 2, 3, 4  — five values
    print(i)

for i in range(1, 6):     # 1, 2, 3, 4, 5
    print(i)

for i in range(10, 0, -1):
    print(i)
```

`range(5)` excludes 5, exactly like `i < 5` in C++. The off-by-one instinct
transfers.

**`while` repeats while true**, and is the right choice when you do not know the
count:

```python
total = 0
while True:
    value = int(input("Number (0 to stop): "))
    if value == 0:
        break
    total += value
print(total)
```

`break` leaves the loop; `continue` skips to the next iteration.

The walrus operator `:=` assigns and returns a value in one step, which makes
loop conditions tidier:

```python
while (line := input("> ")) != "":
    print(line)
```

## Example
```python
# conditions_and_loops.py
marks = [70, 85, 92, 60, 78]

total = 0
for mark in marks:
    total += mark
print("total:", total)
print("average:", total / len(marks))     # true division, no cast needed

# Counting loop
for i in range(1, 4):
    print(i, "squared is", i * i)

# while with a break
count = 0
while True:
    if count >= 3:
        break
    print("count is", count)
    count += 1

# continue skips one value
for value in [1, 2, 3, 4, 5]:
    if value % 2 == 0:
        continue
    print("odd:", value)

# Grade chain, most specific first
def grade_for(mark):
    if mark >= 90:
        return "A"
    elif mark >= 80:
        return "B"
    elif mark >= 70:
        return "C"
    return "F"

for mark in marks:
    print(mark, grade_for(mark))
```

## Knowledge checks
Q: How does Python spell the middle of an if/else chain?
A: `elif`. `else if` is technically valid in Python but is not idiomatic.
Q: What does `range(5)` produce?
A: The values 0, 1, 2, 3 and 4 — five values, excluding the upper bound.
Q: When should you choose `while` over `for`?
A: When the number of iterations is not known in advance and depends on a condition evaluated each pass.
Q: What is the difference between `break` and `continue`?
A: `break` leaves the loop entirely; `continue` skips to the next iteration.

## Exercise
Print the multiplication table for 7 from `7 * 1` to `7 * 10` using a `for`
loop. Then use a `while` loop to read numbers until the user types `0`,
printing how many were read.

```python starter
# Part 1: for loop printing 7, 14, ... 70.
# Part 2: while loop reading ints until 0, then printing the count.
```

## Common mistakes
- **Writing `else if`** by habit from C++.
- **Using `range(1, 5)` expecting five values.** It gives four.
- **Modifying a list while iterating over it.** Python raises an error or behaves unexpectedly; iterate over a copy.
- **Forgetting `break`** in a `while True` loop, so it never exits.
- **Using `++` or `--`.** Python has no increment operator; use `+= 1`.

## Recap
- `elif`, not `else if`.
- `for` iterates over an iterable; use `range()` to count.
- `while` for unknown counts, and it must advance toward its exit.
- `range(n)` excludes `n`.
- Python has no `++`; use `+= 1`.