---
id: 06-error-handling
title: Error Handling & Custom Error Hierarchies
order: 6
lesson_id: 06-error-handling
summary: Error constructor, call stack captures, try/catch/finally, and unhandled rejections.
tags: error-handling, exceptions, try-catch
---

# 6. Error Handling & Custom Error Hierarchies

### The Error Object
An `Error` instance captures the exact call stack at the moment it was instantiated:
```javascript
class NetworkError extends Error {
    constructor(message, statusCode) {
        super(message);
        this.name = "NetworkError";
        this.statusCode = statusCode;
    }
}
```
