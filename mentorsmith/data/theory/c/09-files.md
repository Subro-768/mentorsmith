---
id: 09-files
title: File I/O, Buffering & POSIX File Descriptors
order: 9
lesson_id: 09-files
summary: C stdio FILE* streams, POSIX open/read/write/close, and buffering strategies.
tags: files, stdio, posix, io
source_book: Programming in ANSI C
source_author: Ray Dawson
source_chapter: Section 12
source_page: 112
---

# 9. File I/O, Buffering & POSIX File Descriptors

### Standard C `FILE*` vs POSIX Descriptors
- **Standard C (`<stdio.h>`)**: Portable stream abstraction (`fopen`, `fread`, `fwrite`, `fclose`) with user-space buffer management.
- **POSIX System Calls (`<unistd.h>`)**: Raw low-level kernel transitions (`open`, `read`, `write`, `close`) using integer file descriptors (`0=stdin`, `1=stdout`, `2=stderr`).
