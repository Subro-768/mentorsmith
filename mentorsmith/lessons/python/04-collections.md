---
id: 04-collections
title: Collections
order: 4
---

## Objectives
- Use `list`, `tuple`, `dict` and `set` for the right job.
- Slice sequences.
- Use comprehensions to build collections concisely.
- Avoid mutating a collection while iterating over it.

## Explanation

| Type | Ordered | Mutable | Duplicates | Use for |
|---|---|---|---|---|
| `list` | yes | yes | yes | A sequence you will change |
| `tuple` | yes | **no** | yes | A fixed record, a constant |
| `dict` | insertion | yes | keys unique | Key/value lookup |
| `set` | no | yes | **no** | Membership tests, uniqueness |

```python
marks = [70, 85, 92]              # list
point = (3, 4)                    # tuple
ages = {"Ada": 36, "Alan": 41}    # dict
unique = {1, 2, 2, 3}             # set -> {1, 2, 3}
```

**Lists** support append, insert and removal:

```python
marks.append(60)
marks.insert(0, 99)
marks.remove(70)          # raises ValueError if absent
last = marks.pop()        # removes and returns
```

**Slicing** takes a sub-sequence, start inclusive, end exclusive:

```python
values = [10, 20, 30, 40, 50]
values[1:3]     # [20, 30]
values[:2]      # [10, 20]
values[-1]      # 50
values[::-1]    # reversed copy
```

Slicing never modifies the original. Use `values[1:3] = [x]` to change it.

**Dict** lookups are by key:

```python
ages["Ada"]                 # KeyError if missing
ages.get("Grace", 0)        # 0 if missing — safer
for name, age in ages.items():
    print(name, age)
```

**Comprehensions** build a collection in one expression and are the idiomatic
way to transform:

```python
doubled = [x * 2 for x in marks]
evens = [x for x in range(10) if x % 2 == 0]
squares = {x: x * x for x in range(4)}
```

**Do not mutate while iterating.** Python raises `RuntimeError` for some cases
and silently misbehaves for others:

```python
# BAD
for value in marks:
    marks.remove(value)

# GOOD - iterate over a copy
for value in marks[:]:
    marks.remove(value)
```

## Example
```python
# collections.py
marks = [70, 85, 92, 60, 78]

print("list      :", marks)
print("reversed  :", marks[::-1])
print("slice     :", marks[1:3])
print("comprehen. :", [m for m in marks if m >= 78])

marks.append(88)
marks.sort()
print("sorted    :", marks)

low, high = min(marks), max(marks)
print("min/max   :", low, high, "| mean:", sum(marks) / len(marks))

grades = {"A": 0, "B": 0, "C": 0}
for mark in marks:
    if mark >= 80:
        grades["A"] += 1
    elif mark >= 70:
        grades["B"] += 1
    else:
        grades["C"] += 1
print("grades    :", grades)

ages = {"Ada": 36, "Alan": 41}
ages["Grace"] = 45
print("by key    :", ages["Grace"], "| missing:", ages.get("Nobody", 0))
print("keys      :", sorted(ages))
print("items     :", list(ages.items())[:2])

# a set removes duplicates
print("set       :", sorted({1, 2, 2, 3, 3, 3}))

# a tuple is fixed
point = (3, 4)
print("tuple     :", point, "| unpacked:", point[0], point[1])
```

## Knowledge checks
Q: When should you choose a tuple instead of a list?
A: When the value is a fixed record or should not change — tuples are immutable and can be used as dict keys.
Q: What does `values[1:3]` return for `[10, 20, 30, 40, 50]`?
A: `[20, 30]`. The start is inclusive and the end is exclusive.
Q: Why is mutating a list inside a `for` loop over it a problem?
A: The loop's position is based on the original sequence, so removing elements makes it skip or overrun. Iterate over a copy such as `values[:]`.
Q: What does a dict comprehension look like?
A: `{key: value for item in items}` — it builds a dict in one expression.

## Exercise
Build a list of five marks entered by the user, rejecting non-numeric input.
Print the marks in order and reversed, the highest and lowest, and a dict
counting how many marks fall into each of three bands.

```python starter
marks = []

# Read 5 marks with int(input(...)); on ValueError print a message and stop.
# Print the marks, marks[::-1], max and min.
# Build a dict of band -> count for >=80, >=70 and below.
```

## Common mistakes
- **Using `.pop(i)` where you meant `remove(value)`.** `pop` takes an index.
- **Expecting slicing to modify the list.** It returns a new list.
- **`KeyError` from a missing dict key.** Use `.get(key, default)`.
- **Mutating a list while iterating over it.**
- **Assuming `dict` ordering is alphabetical.** It preserves insertion order; use `sorted()` for sorted output.

## Recap
- `list` is mutable, `tuple` is not, `dict` is keyed, `set` is unique.
- Slicing is `start:end` with end excluded, and it copies.
- `dict[key]` raises if absent; `dict.get(key, default)` does not.
- Comprehensions are the idiomatic way to transform.
- Never mutate a collection while iterating over it.