---
id: 10-encapsulation
title: Encapsulation
order: 10
tier: core
---

## Objectives
- Protect object integrity using `private` fields.
- Provide controlled access with getters and setters.
- Understand visibility modifiers.

## Explanation
Encapsulation bundles data with the methods that operate on it and hides internal state:
- `private`: Accessible only within the declaring class.
- `public`: Accessible from any class.
- (default/package-private): Accessible within the same package.
- `protected`: Accessible within the package and subclasses.

Setters can enforce data validation rules before updating fields:
```java
public void setAge(int age) {
    if (age >= 0) {
        this.age = age;
    }
}
```

## Example
```java
public class Main {
    static class BankAccount {
        private double balance;

        public void deposit(double amount) {
            if (amount > 0) balance += amount;
        }

        public double getBalance() {
            return balance;
        }
    }

    public static void main(String[] args) {
        BankAccount acc = new BankAccount();
        acc.deposit(100.0);
        System.out.println(acc.getBalance());
    }
}
```

## Knowledge checks
Q: Why are fields usually declared private?
A: To prevent outside code from directly altering internal state into an invalid condition.
Q: What naming convention is used for getter methods in Java?
A: getFieldName() or isFieldName() for booleans.
Q: What is encapsulation?
A: Bundling data and behavior while restricting direct access to internal implementation details.

## Exercise
Create a static class `Person` with private `name` and `age`, constructor, and getters `getName()` and `getAge()`. Instantiate and print the name and age.

```java starter
public class Main {
    // Define static class Person with private fields and public getters

    public static void main(String[] args) {
        // Instantiate Person and print name and age
    }
}
```

## Common mistakes
- Making all fields public for convenience, breaking encapsulation guarantees.
- Not validating inputs in setters.

## Recap
- Keep fields `private`.
- Provide read/write access via `getters` and `setters`.
