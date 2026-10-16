---
id: 15-file-handling
title: File Handling
order: 15
---

## Objectives
- Read from and write to files using `<fstream>`.
- Distinguish input, output and bidirectional streams.
- Check for errors instead of assuming success.
- Parse simple structured text safely.

## Explanation
`<fstream>` provides three stream classes:

| Class | Purpose |
|---|---|
| `std::ifstream` | Read from a file |
| `std::ofstream` | Write to a file (truncates any existing content) |
| `std::fstream` | Read and write |

The usual pattern is: open, check, use, close.

```cpp
#include <fstream>
#include <iostream>
#include <string>

int main() {
    std::ifstream input("notes.txt");
    if (!input) {                                  // ALWAYS check
        std::cout << "Could not open notes.txt\n";
        return 1;
    }

    std::string line;
    while (std::getline(input, line)) {
        std::cout << line << '\n';
    }
    if (!input.eof()) {                            // read failed part-way
        std::cout << "Error while reading\n";
    }
    input.close();
    return 0;
}
```

**Check the stream immediately after opening.** This is the single most
important habit here — an unchecked `ifstream` on a missing file silently
produces no data, and the bug surfaces much later in a confusing place.

**Writing** works the same way:

```cpp
std::ofstream output("notes.txt");           // creates, or truncates
if (!output) {
    std::cout << "Could not write notes.txt\n";
    return 1;
}
output << "first line\n";
output << "value = " << 42 << '\n';
output.close();
```

To append rather than overwrite, use the `std::ios::app` mode:

```cpp
std::ofstream output("notes.txt", std::ios::app);
```

**Open modes** combine with `|` when you need more than one:

```cpp
std::fstream file("data.txt", std::ios::in | std::ios::out);
```

**Reading numbers.** `>>` on a stream that has run out of data leaves the
stream in a failed state. Check `while (input >> value)` rather than trusting
the input:

```cpp
int value;
while (input >> value) {
    std::cout << value << '\n';        // stops cleanly at end of file
}
```

This is the idiomatic way to read a list of numbers of unknown length.

**File paths.** Use `std::filesystem` for anything non-trivial:

```cpp
#include <filesystem>

const std::filesystem::path path = "data/notes.txt";
if (!path.parent_path().empty()) {
    std::filesystem::create_directories(path.parent_path());
}
```

**A note on parsing.** Splitting a line with `std::stringstream` is a safe,
readable way to parse a simple delimited format:

```cpp
std::istringstream parser(line);
std::string name;
int mark;
if (parser >> name >> mark) { /* use them */ }
```

Reach for `std::regex` only when regular expressions genuinely help; prefer
simple parsing for simple formats.

## Example
```cpp
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

struct Record {
    std::string name;
    int         mark = 0;
};

std::string read_record_file(const std::string& path, std::vector<Record>& out) {
    std::ifstream input(path);
    if (!input) return "cannot open '" + path + "' for reading";

    std::string line;
    int number = 0;
    while (std::getline(input, line)) {
        ++number;
        if (line.empty()) continue;                 // skip blank lines

        std::istringstream parser(line);
        Record record;
        if (!(parser >> record.name >> record.mark)) {
            return "malformed record on line " + std::to_string(number);
        }
        out.push_back(record);
    }
    if (!input.eof()) return "error while reading '" + path + "'";
    return "";                                       // empty string = success
}

std::string write_record_file(const std::string& path, const std::vector<Record>& records) {
    std::ofstream output(path);                      // truncates
    if (!output) return "cannot open '" + path + "' for writing";

    for (const Record& record : records) {
        output << record.name << ' ' << record.mark << '\n';
    }
    if (!output) return "error while writing '" + path + "'";
    return "";
}

void append_record(const std::string& path, const Record& record) {
    std::ofstream output(path, std::ios::app);       // append, do not truncate
    if (!output) {
        std::cout << "append failed\n";
        return;
    }
    output << record.name << ' ' << record.mark << '\n';
}

int main() {
    const std::string path = "marks.txt";

    const std::vector<Record> seed{
        { "Ada",   93 },
        { "Alan",  81 },
        { "Grace", 74 },
    };

    std::string error = write_record_file(path, seed);
    if (!error.empty()) {
        std::cout << "write error: " << error << '\n';
        return 1;
    }
    std::cout << "wrote " << seed.size() << " records to " << path << '\n';

    append_record(path, { "Linus", 67 });
    std::cout << "appended 1 record\n";

    std::vector<Record> loaded;
    error = read_record_file(path, loaded);
    if (!error.empty()) {
        std::cout << "read error: " << error << '\n';
        return 1;
    }

    int total = 0;
    std::cout << "\nloaded " << loaded.size() << " records:\n";
    for (const Record& record : loaded) {
        std::cout << "  " << record.name << " " << record.mark << '\n';
        total += record.mark;
    }

    if (!loaded.empty()) {
        std::cout << "average = "
                  << static_cast<double>(total) / loaded.size() << '\n';
    } else {
        std::cout << "average = undefined (no records)\n";
    }

    // Reading a file that does not exist is reported, not crashed on.
    std::vector<Record> missing;
    const std::string missing_error = read_record_file("no_such_file.txt", missing);
    std::cout << "\nexpected failure: " << missing_error << '\n';
    return 0;
}
```

## Knowledge checks
Q: Why must you check the stream right after opening a file?
A: Opening can fail for many reasons — the file may not exist, or permissions may be denied. An unchecked stream simply produces no data, and the failure appears much later as a confusing symptom.
Q: What does `std::ofstream output("f.txt")` do if `f.txt` already exists?
A: It truncates the file, discarding its contents. Use `std::ios::app` to append instead.
Q: Why is `while (input >> value)` the idiomatic loop for reading numbers?
A: When extraction fails at end of file it sets the stream's fail state, making the condition false and ending the loop cleanly, with no separate EOF handling needed.
Q: What is `std::istringstream` useful for?
A: Treating an in-memory string as a stream, which gives you `>>` parsing and safe token extraction without touching disk.

## Exercise
Write a program that appends one line of user input to a file named
`journal.txt` for each run, using append mode so earlier entries survive. Then
write a second part that reads the file back and prints how many entries it
contains and the last one entered.

```cpp starter
#include <fstream>
#include <iostream>
#include <string>

int main() {
    std::string entry;

    std::cout << "New journal entry: ";
    if (!std::getline(std::cin >> std::ws, entry) || entry.empty()) {
        std::cout << "Nothing to save.\n";
        return 1;
    }

    // 1. Append `entry` to journal.txt, checking the stream.
    //    Use std::ios::app so previous entries are kept.

    // 2. Open journal.txt for reading and count the lines.

    // 3. Print the count and the last line entered.
    return 0;
}
```

## Common mistakes
- **Not checking whether the file opened.** Produces silent, confusing failures.
- **Using `ofstream` when you meant to append.** Truncates existing content.
- **Reading with `>>` and expecting a clean end.** Check the stream each iteration.
- **Forgetting `close()` before reopening for read.** Data may not be flushed yet.
- **Hardcoding paths.** Use `std::filesystem` for anything beyond a single filename.
- **Leaving the file open on an error path.** Prefer RAII with `std::fstream`.

## Recap
- `ifstream` reads, `ofstream` writes, `fstream` does both.
- Check the stream immediately after opening, before reading anything.
- `ofstream` truncates by default; `std::ios::app` appends.
- `while (input >> value)` handles EOF and errors cleanly.
- `std::istringstream` parses strings with the same operators as files.