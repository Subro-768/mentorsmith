---
id: 04-operators
title: Operators
order: 4
---

## Objectives
- Use arithmetic, comparison and logical operators correctly.
- Predict the result of mixed-type expressions.
- Explain integer division, modulo and truncation.
- Use parentheses to control evaluation order explicitly.

## Explanation
**Arithmetic:** `+  -  *  /  %`

`%` is modulo — the remainder after integer division. It only works on integer
operands; `7.5 % 2` is a compile error.

**The division trap.** When both operands are integers, `/` does integer
division and throws away the fractional part. This is the single most common
wrong answer in beginner C++:

```cpp
5 / 2      // 2    (two ints)
5.0 / 2    // 2.5  (one is a double)
5 / 2.0    // 2.5
(int)5 / 2 // 2    (cast applied first, still two ints)
```

**Comparison:** `==  !=  <  >  <=  >=`

`=` assigns. `==` compares. Writing `=` where you meant `==` is a mistake the
compiler usually catches for you.

**Logical:** `&&  ||  !`

These short-circuit, which is the safe way to guard a second condition:

```cpp
if (count != 0 && total / count > 10)   // safe: / count never runs when count == 0
```

Without `&&` short-circuiting, `count != 0 & total / count > 10` would divide by
zero regardless of the first test.

**Compound assignment:** `+=  -=  *=  /=  %=`

```cpp
score += 10;      // same as: score = score + 10;
```

**Increment:** `++` and `--`. In C++ `i++` returns the value *before*
incrementing while `++i` returns the value *after*. For a standalone statement
`i++;` and `++i;` are identical — the distinction only matters when the result
is used in an expression, which is a good reason to avoid it there.

**Precedence:** `*  /  %` bind tighter than `+  -`, which bind tighter than
comparisons, which bind tighter than `&&`, which binds tighter than `||`.

Do not memorise the whole table. Use parentheses when the intent is not
obvious. They cost nothing and remove all doubt.

## Example
```cpp
#include <iomanip>
#include <iostream>

int main() {
    const int    apples  = 7;
    const int    baskets = 2;
    const double price   = 1.25;

    std::cout << "7 / 2            = " << apples / baskets << '\n';
    std::cout << "7.0 / 2          = " << 7.0 / 2 << '\n';
    std::cout << "7 % 2            = " << apples % baskets << '\n';

    const double cost = apples * price;
    std::cout << std::fixed << std::setprecision(2)
              << "Total            = " << cost << '\n';

    const bool   affordable = cost < 10.0;
    const bool   rich       = cost > 5.0 && affordable;
    std::cout << "affordable?      = " << std::boolalpha << affordable << '\n';
    std::cout << "rich?            = " << rich << '\n';

    int score = 50;
    score += 10;
    std::cout << "score after +=10 = " << score << '\n';
    return 0;
}
```

## Knowledge checks
Q: What is the value of `7 / 2` and of `7.0 / 2`?
A: `7 / 2` is `2` because both operands are integers, so the fraction is truncated. `7.0 / 2` is `2.5` because one operand is a `double`.
Q: Why does `7.5 % 2` fail to compile?
A: The modulo operator is only defined for integer operands.
Q: Why write `count != 0 && total / count > 10` rather than using two `&` symbols?
A: `&&` short-circuits, so the division is skipped entirely when `count` is zero. A non-short-circuit `&` would evaluate both sides and divide by zero.

## Exercise
Given `int a = 17;` and `int b = 5;`, print `a + b`, `a - b`, `a * b`, `a / b`,
`a % b`, and whether `a` is greater than `b`. Then convert `a` to `double` and
print the division again to show the difference.

```cpp starter
#include <iostream>

int main() {
    const int a = 17;
    const int b = 5;

    // Print each operation on its own labelled line.
    // Then: const double da = static_cast<double>(a); print da / b
    return 0;
}
```

## Common mistakes
- **Integer division when a fraction was expected.** Promote one operand to `double` first.
- **`=` instead of `==`.** Assigns instead of comparing.
- **Using `&` or `|` instead of `&&` or `||`.** Loses short-circuiting and can crash.
- **Relying on precedence.** It is correct but hard to read. Parenthesise.

## Recap
- `/` on two integers truncates toward zero.
- `%` requires integers and yields the remainder.
- `=` assigns, `==` compares.
- `&&` and `||` short-circuit, which makes them the safe choice in guards.
- Use parentheses to make intent explicit.