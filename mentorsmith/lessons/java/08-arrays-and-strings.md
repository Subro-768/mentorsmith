---
id: 08-arrays-and-strings
title: Arrays and Strings
order: 8
---

## Objectives
- Declare, allocate, and index fixed-size arrays.
- Inspect array `.length`.
- Utilize common String manipulation methods.

## Explanation
Arrays are fixed-length sequences of elements of the same type:
```java
int[] numbers = new int[5]; // default initialized to 0
int[] primes = {2, 3, 5, 7, 11};
System.out.println(primes[0]); // 2
System.out.println(primes.length); // 5
```

Accessing indices outside `0` to `length - 1` throws `ArrayIndexOutOfBoundsException`.

Strings provide rich inspection methods:
- `.length()`: number of characters
- `.charAt(index)`: character at index
- `.substring(start, end)`: sliced substring
- `.contains(seq)`, `.toUpperCase()`, `.toLowerCase()`

## Example
```java
public class Main {
    public static void main(String[] args) {
        int[] values = {10, 20, 30};
        for (int v : values) {
            System.out.println(v);
        }
        String text = "Java";
        System.out.println(text.toUpperCase());
    }
}
```

## Knowledge checks
Q: What property gives the number of elements in an array?
A: .length (notice: no parentheses, unlike String.length()).
Q: What exception is thrown when an invalid array index is accessed?
A: ArrayIndexOutOfBoundsException.
Q: Are Java Strings mutable?
A: No, Java Strings are immutable; methods like toUpperCase() return new Strings.

## Exercise
Given an array `int[] nums = {4, 7, 2, 9, 5};`, compute and print the largest number.

```java starter
public class Main {
    public static void main(String[] args) {
        int[] nums = {4, 7, 2, 9, 5};
        // Find and print maximum value
    }
}
```

## Common mistakes
- Writing `array.length()` with parentheses.
- Modifying a string and forgetting to reassign the result (`str.toUpperCase()` without `str = ...`).

## Recap
- Arrays are fixed-size and 0-indexed.
- Strings are immutable objects.
