---
id: 08-classes
title: Classes and Objects
order: 8
---

## Objectives
- Define a class with methods, `__init__` and attributes.
- Understand instance versus class attributes.
- Use `__repr__`, `__str__` and `__eq__`.
- Follow encapsulation with properties.

## Explanation
A class is a template; an object is an instance of it.

```python
class Rectangle:
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def area(self):
        return self.width * self.height
```

`__init__` runs when an object is created. `self` is the object the method was
called on; Python passes it automatically.

**Instance versus class attributes.** An attribute assigned inside `__init__` is
per-object. One assigned in the class body is shared by every instance:

```python
class Counter:
    limit = 100              # class attribute: one copy for all

    def __init__(self):
        self.count = 0       # instance attribute: one per object
```

Sharing mutable class attributes between instances is a classic bug: appending to
a list defined on the class appends to *everyone's* list.

**Dunder methods** give your type Python behaviour:

```python
class Point:
    def __init__(self, x, y):
        self.x, self.y = x, y

    def __repr__(self):
        return f"Point({self.x}, {self.y})"     # for developers

    def __str__(self):
        return f"({self.x}, {self.y})"          # for people

    def __eq__(self, other):
        return (self.x, self.y) == (other.x, other.y)
```

Without `__repr__`, printing an object shows something like
`<__main__.Point object at 0x7f...>`, which tells you nothing.

**Properties** let you validate while still using attribute syntax:

```python
class Temperature:
    def __init__(self, celsius):
        self.celsius = celsius          # goes through the setter

    @property
    def celsius(self):
        return self._celsius

    @celsius.setter
    def celsius(self, value):
        if value < -273.15:
            raise ValueError("below absolute zero")
        self._celsius = value

    @property
    def fahrenheit(self):
        return self._celsius * 9 / 5 + 32
```

`fahrenheit` is computed, so it cannot drift out of sync with `celsius`.

**Inheritance** is available but composition is often clearer:

```python
class Square(Rectangle):
    def __init__(self, side):
        super().__init__(side, side)
```

`super()` calls the parent's version. Prefer composition when the
"is-a" relationship is not genuine — inheritance locks in a coupling.

## Example
```python
# classes.py
class Rectangle:
    def __init__(self, width, height):
        if width <= 0 or height <= 0:
            raise ValueError("width and height must be positive")
        self.width = width
        self.height = height

    def area(self):
        return self.width * self.height

    def scaled(self, factor):
        """Return a new rectangle rather than mutating this one."""
        return Rectangle(self.width * factor, self.height * factor)

    def __repr__(self):
        return f"Rectangle({self.width}, {self.height})"

    def __eq__(self, other):
        return (
            isinstance(other, Rectangle)
            and self.width == other.width
            and self.height == other.height
        )


class Square(Rectangle):
    def __init__(self, side):
        super().__init__(side, side)

    def __repr__(self):
        return f"Square({self.width})"


class Counter:
    instances = 0                    # class attribute

    def __init__(self):
        self.count = 0               # instance attribute
        Counter.instances += 1


rect = Rectangle(3, 4)
print(rect)                          # uses __repr__ -> Rectangle(3, 4)
print("area:", rect.area())          # 12
print("scaled:", rect.scaled(2))     # a new object, rect unchanged
print("equal:", rect == Rectangle(3, 4))

square = Square(5)
print(square, "| area:", square.area())

print("instances:", Counter.instances)
a, b = Counter(), Counter()
print("instances after two:", Counter.instances, "| a.count:", a.count)

try:
    Rectangle(0, 5)
except ValueError as error:
    print("rejected:", error)
```

## Knowledge checks
Q: What is `self`?
A: The object the method was called on. Python passes it automatically; you never pass it when calling a method.
Q: What is the difference between a class attribute and an instance attribute?
A: A class attribute lives once on the class and is shared; an instance attribute is created per object in `__init__`.
Q: Why write `__repr__`?
A: Without it, printing an object shows an opaque address. `__repr__` gives a developer-facing form and `__str__` a human-facing one.
Q: Why is a mutable class attribute dangerous?
A: Every instance shares the same object, so mutating it in one place changes it for all of them.

## Exercise
Create a class `BankAccount` that validates a positive opening balance, offers
`deposit` and `withdraw` returning `True` or `False` rather than raising, keeps
a `history` list of transaction strings, and defines `__repr__`.

```python starter
class BankAccount:
    def __init__(self, opening):
        # Raise ValueError if opening <= 0
        # self.balance = opening; self.history = []

    def deposit(self, amount):
        # Reject non-positive amounts. Append to history. Return True/False.

    def withdraw(self, amount):
        # Reject non-positive amounts and overdrafts. Return True/False.

    def __repr__(self):
        # Something like BankAccount(balance=100.0, transactions=1)
```

## Common mistakes
- **Forgetting `self`** when assigning an attribute, which creates a local instead.
- **Mutable class attributes** shared across instances.
- **No `__repr__`,** so debugging output is an address.
- **Comparing objects with `==` without `__eq__`,** which falls back to identity.
- **Overriding `__init__` without calling `super().__init__()`** in a subclass.

## Recap
- `__init__` runs at construction; `self` is the instance.
- Class attributes are shared; instance attributes are per object.
- Implement `__repr__`, `__str__` and `__eq__` for useful behaviour.
- `@property` validates while keeping attribute syntax.
- Prefer composition unless the "is-a" relationship is genuine.