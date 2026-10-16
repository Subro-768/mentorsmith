---
id: 03-functions
title: Functions
order: 3
---

## Objectives
- Define and call functions with `def`.
- Return values, including early returns.
- Use default arguments and keyword arguments.
- Understand Python's lack of a separate pass-by-reference keyword.

## Explanation
Functions are defined with `def` and always end with a colon; the body is
indented:

```python
def greet(name):
    return f"Hello, {name}"

print(greet("Ada"))
```

Indentation *is* the syntax. Four spaces is the convention. A wrong indent is a
syntax error, not a style complaint.

**Returning.** `return` sends a value back and ends the function. A function
without `return` returns `None`, which is Python's null.

```python
def classify(n):
    if n < 0:
        return "negative"
    elif n == 0:
        return "zero"
    return "positive"
```

**Default and keyword arguments.** Defaults are evaluated once, at definition
time — a trap when the default is a mutable value:

```python
def collect(item, bucket=[]):      # BUG: the list is created once
    bucket.append(item)
    return bucket

print(collect("a"))    # ['a']
print(collect("b"))    # ['a', 'b']  <- surprising!

def collect(item, bucket=None):    # correct
    if bucket is None:
        bucket = []
    bucket.append(item)
    return bucket
```

**No pass-by-reference keyword.** Python passes objects, and rebinding a
parameter never changes the caller's variable:

```python
def double(x):
    x = x * 2          # rebinds the local name only
    return x

n = 5
double(n)
print(n)               # still 5
```

To modify a caller's object, mutate it:

```python
def push(values, item):
    values.append(item)   # mutates the caller's list

items = [1, 2]
push(items, 3)
print(items)              # [1, 2, 3]
```

Compare that with C++: where C++ distinguishes `T&` from `const T&`, Python has
one model. A list is passed as one object, and calling a method on it changes
what the caller sees.

**Multiple return values** are just a tuple:

```python
def min_max(values):
    return min(values), max(values)

low, high = min_max([3, 1, 4])
```

## Example
```python
# functions.py
def add(a, b=0):
    """Return a + b. The second argument is optional."""
    return a + b


def safe_divide(a, b):
    """Raise rather than guess when the denominator is zero."""
    if b == 0:
        raise ValueError("division by zero")
    return a / b


def swap_pair(pair):
    a, b = pair
    return b, a


def apply_to_all(values, function):
    """A higher-order function: takes a function as an argument."""
    return [function(value) for value in values]


print(add(2, 3), add(2))                 # 5 2
print(safe_divide(7, 2))                 # 3.5

try:
    safe_divide(1, 0)
except ValueError as error:
    print("refused:", error)

print(swap_pair((1, 2)))                 # (2, 1)
print(apply_to_all([1, 2, 3], add))      # needs 2 args; use a lambda instead
print([x * 2 for x in [1, 2, 3]])        # 2, 4, 6

# keyword arguments make calls readable
print(add(a=1, b=4))                     # 5
```

## Knowledge checks
Q: Why is `def f(bucket=[])` dangerous?
A: The default list is created once when the function is defined and then shared between calls, so results accumulate unexpectedly. Use `None` as the default and build the list inside.
Q: Does modifying a parameter inside a function change the caller's variable?
A: Rebinding a name never does. Mutating a mutable object the caller also holds does.
Q: What does a function without `return` give back?
A: `None`.

## Exercise
Write three functions: `is_even(n)` returning a boolean, `average(values)`
returning the mean as a float and `0.0` for an empty list, and
`count_words(text)` returning how many space-separated words there are. Then
call each and print the result.

```python starter
def is_even(n):
    # Return True when n is divisible by 2.


def average(values):
    # Return the mean as a float, or 0.0 for an empty list.


def count_words(text):
    # Split on whitespace and return how many words there are.
```

## Common mistakes
- **Mutable default arguments.** Use `None` and construct inside.
- **Using `;` or braces instead of indentation.** Indentation is the syntax.
- **Forgetting `return`** and then using the result, which is `None`.
- **Expecting assignment inside a function to change the caller's variable.** It does not.
- **Comparing with `=` instead of `==`.**

## Recap
- `def name(params):` with an indented body.
- `return` ends the function; no `return` means `None`.
- Never use a mutable default; use `None`.
- Rebinding a parameter does not affect the caller; mutating does.
- Multiple returns are a tuple you can unpack.