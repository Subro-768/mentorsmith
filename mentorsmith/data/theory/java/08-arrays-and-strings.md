---
id: 08-arrays-and-strings
title: Array Memory Layout & String Immutability
order: 8
lesson_id: 08-arrays-and-strings
summary: Covariant arrays, cache locality, compact strings (byte[] Latin1/UTF-16), and StringBuilder.
tags: arrays, strings, stringbuilder, immutability
---

# 8. Array Memory Layout & String Immutability

### String Immutability & Compact Strings
`java.lang.String` is immutable. Once created, its character buffer cannot change.
In modern Java (Java 9+), `String` uses **Compact Strings**: storing either `byte[]` with Latin-1 encoding (1 byte per char) if possible, or UTF-16 (2 bytes per char) if non-Latin characters are present, cutting heap consumption by up to 50%.
