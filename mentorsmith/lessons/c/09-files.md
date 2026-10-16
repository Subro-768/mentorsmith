---
id: 09-files
title: File Handling
order: 9
---

## Objectives
- Open, read and write files with `<stdio.h>`.
- Choose between text and binary modes.
- Check every stream operation.
- Parse simple delimited text safely.

## Explanation
C uses `FILE *` streams from `<stdio.h>`:

```c
#include <stdio.h>

int main(void) {
    FILE *file = fopen("notes.txt", "r");
    if (file == NULL) {
        perror("notes.txt");       /* prints the reason, e.g. "No such file" */
        return 1;
    }

    char line[256];
    while (fgets(line, sizeof(line), file) != NULL) {
        printf("%s", line);
    }

    if (ferror(file)) {
        printf("error while reading\n");
    }

    fclose(file);
    return 0;
}
```

**Always check `fopen`.** It returns `NULL` when the file is missing or
permission is denied. `perror` prints the system's own reason, which is more
useful than inventing one.

**Modes:**

| Mode | Meaning |
|---|---|
| `"r"` | Read |
| `"w"` | Write, truncating |
| `"a"` | Append |
| `"r+"` | Read and write, no truncation |
| `"rb"` / `"wb"` | Binary, for portability |

Without `b` the file is opened in text mode, which on Windows translates
newlines. Always use `b` for binary data on any platform.

**`fgets` is the safe way to read a line.** Give it the buffer size and it can
never overflow:

```c
char line[256];
if (fgets(line, sizeof(line), file) == NULL) {
    /* end of file or error */
}
```

`fgets` keeps the newline, and returns `NULL` at end of file — which is the
loop condition above. Note that `scanf` stops at whitespace and is easy to
misuse; prefer `fgets` for text.

**Writing** is the same shape:

```c
FILE *out = fopen("data.txt", "w");
if (out == NULL) {
    perror("data.txt");
    return 1;
}
fprintf(out, "first\n");
fprintf(out, "value = %d\n", 42);
if (fclose(out) != 0) {
    printf("error flushing on close\n");
}
```

`fclose` can fail on a buffered write, so check it on files you care about.

**Parsing delimited text.** `sscanf` reads fields out of a string:

```c
char line[] = "Ada,93";
char name[32];
int mark;
if (sscanf(line, "%31[^,],%d", name, &mark) == 2) {
    printf("%s scored %d\n", name, mark);
}
```

`%31[^,]` reads at most 31 characters up to a comma, which respects the buffer
size — note the field width, which is what makes `sscanf` safe.

## Example
```c
/* files.c */
#include <stdio.h>
#include <string.h>

typedef struct {
    char name[32];
    int  mark;
} Record;

int write_records(const char *path, const Record *records, size_t count) {
    FILE *file = fopen(path, "w");
    if (file == NULL) {
        perror(path);
        return -1;
    }
    size_t i;
    for (i = 0; i < count; ++i) {
        fprintf(file, "%s,%d\n", records[i].name, records[i].mark);
    }
    if (fclose(file) != 0) {
        printf("error closing %s\n", path);
        return -1;
    }
    return 0;
}

int read_records(const char *path, Record *out, size_t capacity) {
    FILE *file = fopen(path, "r");
    if (file == NULL) {
        return -1;                 /* caller reports the reason */
    }

    char line[256];
    size_t found = 0;
    while (fgets(line, sizeof(line), file) != NULL) {
        if (found >= capacity) {
            printf("stopping at capacity\n");
            break;
        }
        char name[32];
        int mark;
        if (sscanf(line, "%31[^,],%d", name, &mark) != 2) {
            printf("skipping malformed line: %s", line);
            continue;
        }
        strncpy(out[found].name, name, sizeof(out[found].name) - 1);
        out[found].name[sizeof(out[found].name) - 1] = '\0';
        out[found].mark = mark;
        ++found;
    }

    if (ferror(file)) {
        printf("read error on %s\n", path);
        fclose(file);
        return -1;
    }
    fclose(file);
    return (int)found;
}

int main(void) {
    const char *path = "marks.txt";

    Record seed[3] = {
        {"Ada", 93},
        {"Alan", 81},
        {"Grace", 74}
    };

    if (write_records(path, seed, 3) != 0) {
        return 1;
    }
    printf("wrote 3 records to %s\n", path);

    Record loaded[10];
    int found = read_records(path, loaded, 10);
    if (found < 0) {
        perror(path);
        return 1;
    }

    int total = 0;
    int i;
    printf("loaded %d records:\n", found);
    for (i = 0; i < found; ++i) {
        printf("  %s %d\n", loaded[i].name, loaded[i].mark);
        total += loaded[i].mark;
    }
    printf("average = %.2f\n", (double)total / found);

    /* A missing file is reported, not crashed on */
    Record missing[1];
    if (read_records("no_such_file.txt", missing, 1) < 0) {
        printf("expected failure: cannot read no_such_file.txt\n");
    }

    return 0;
}
```

## Knowledge checks
Q: What does `fopen` return when it fails, and why must you check?
A: `NULL`. An unchecked stream produces no data, and the failure appears much later as a confusing symptom.
Q: Why prefer `fgets` over `scanf` for reading text lines?
A: `fgets` takes a buffer size and cannot overflow; `scanf` stops at whitespace and is easy to misuse.
Q: What does mode `"a"` do?
A: Opens for appending, creating the file if needed and never truncating.
Q: Why add `b` to the mode for binary data?
A: Text mode can translate newlines on some platforms, corrupting binary data.

## Exercise
Write `append_line(const char *path, const char *text)` that appends one line
using mode `"a"`. Then write `count_lines(const char *path)` that returns how
many lines the file has, returning −1 if it cannot be opened.

```c starter
#include <stdio.h>

int append_line(const char *path, const char *text) {
    /* fopen(path, "a"), fprintf, fclose. Return 0 or -1. */
}

int count_lines(const char *path) {
    /* fopen(path, "r"). If NULL return -1. Count fgets calls. */
}
```

## Common mistakes
- **Not checking `fopen`.** The program then silently does nothing.
- **Using mode `"w"` when you meant `"a"`,** destroying existing content.
- **Using `gets`,** which cannot be used safely. It was removed from the standard.
- **Passing an unbounded format string to `fprintf`.** Use `%s`, not the value itself.
- **Ignoring `fclose`,** which can hide a failed flush.

## Recap
- `FILE *` from `<stdio.h>`; always check `fopen` for `NULL`.
- `perror` explains the failure in the system's own words.
- `fgets(buffer, size, file)` is the safe way to read a line.
- `"r"`, `"w"` (truncates), `"a"`; add `b` for binary.
- `sscanf` with a field width, such as `%31[^,]`, respects the buffer size.