---
id: 11-collections
title: Collections
order: 11
---

## Objectives
- Use dynamic lists with `java.util.ArrayList`.
- Store key-value mappings with `java.util.HashMap`.
- Iterate through collections.

## Explanation
Java provides collections that resize dynamically:

**ArrayList<E>**:
```java
import java.util.ArrayList;

ArrayList<String> fruits = new ArrayList<>();
fruits.add("Apple");
fruits.add("Banana");
System.out.println(fruits.get(0)); // Apple
System.out.println(fruits.size()); // 2
```

**HashMap<K, V>**:
```java
import java.util.HashMap;

HashMap<String, Integer> ages = new HashMap<>();
ages.put("Alice", 25);
int age = ages.get("Alice"); // 25
boolean hasBob = ages.containsKey("Bob");
```

## Example
```java
import java.util.ArrayList;

public class Main {
    public static void main(String[] args) {
        ArrayList<Integer> nums = new ArrayList<>();
        nums.add(10);
        nums.add(20);
        int sum = 0;
        for (int n : nums) sum += n;
        System.out.println("Sum: " + sum);
    }
}
```

## Knowledge checks
Q: How does ArrayList differ from a regular array?
A: ArrayList can dynamically grow and shrink; regular arrays have fixed capacity.
Q: Can primitive types like int be directly stored in an ArrayList?
A: No, collections store objects; Java automatically boxes primitives into wrapper types like Integer.
Q: Which method checks if a key exists in a HashMap?
A: containsKey(key).

## Exercise
Create a `HashMap<String, Integer>` storing items and prices: "Pen": 2, "Notebook": 5. Print the price of "Notebook".

```java starter
import java.util.HashMap;

public class Main {
    public static void main(String[] args) {
        // Create HashMap and print price of Notebook
    }
}
```

## Common mistakes
- Writing `ArrayList<int>` instead of `ArrayList<Integer>`.
- Using `.length` instead of `.size()` on collections.

## Recap
- `ArrayList` provides dynamic array functionality.
- `HashMap` provides fast O(1) average lookup by key.
