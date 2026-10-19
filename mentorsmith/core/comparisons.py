"""Cross-language comparisons that are actually meaningful.

Phase 4 asks for exercises that compare the same idea across languages, and
warns that "similar names do not imply identical semantics". That warning is
the whole point of this module: `7 / 2` is `3` in C and `3.5` in Python, and
reading one track after another quietly teaches the wrong thing.

Each comparison states what is genuinely the same and, more importantly, where
the semantics diverge. Nothing here is generated; it is curated, because a
wrong comparison would teach a misconception.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Comparison:
    """One concept seen through two languages."""

    id: str
    concept: str
    languages: tuple[str, str]
    #: What both languages genuinely share.
    same: str
    #: Where they differ. This is the part worth reading.
    different: tuple[str, ...] = ()
    #: Runnable snippets, one per language, in ``languages`` order.
    snippets: tuple[str, str] = ("", "")
    #: A question to answer after reading, so it is not passive.
    question: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "concept": self.concept,
            "languages": list(self.languages),
            "same": self.same,
            "different": list(self.different),
            "snippets": list(self.snippets),
            "question": self.question,
        }


COMPARISONS: tuple[Comparison, ...] = (
    Comparison(
        id="division",
        concept="Integer versus true division",
        languages=("c", "python"),
        same="The `/` operator divides two values.",
        different=(
            "In C, `7 / 2` with two ints is `3`: the fractional part is discarded.",
            "In Python, `7 / 2` is always `3.5`, because `/` is true division.",
            "Python's `//` is the integer answer, so `7 // 2` is `3`.",
            "This is the single most common bug when moving between them: a C "
            "program that works becomes silently wrong in Python.",
        ),
        snippets=(
            "int a = 7, b = 2;\nprintf(\"%d\\n\", a / b);      /* 3 */\n"
            "printf(\"%.1f\\n\", (double)a / b); /* 3.5 - cast first */",
            "a, b = 7, 2\nprint(a / b)        # 3.5 - always true division\n"
            "print(a // b)       # 3    - floor division",
        ),
        question=(
            "You port a C function that averaged two integers to Python. What "
            "changes, and what test would catch the mistake?"
        ),
    ),
    Comparison(
        id="pointers-vs-references",
        concept="What a pointer really is",
        languages=("c", "cpp"),
        same="Both store an address, and `&` takes one while `*` dereferences one.",
        different=(
            "C has no references at all: modifying through a pointer is the only "
            "way to change a caller's variable.",
            "C++ has both. A reference is an alias that can never be reseated and "
            "can never be null; a pointer can do both.",
            "A C++ reference is closer in spirit to a Python reference or a "
            "JavaScript object binding than to a C pointer.",
        ),
        snippets=(
            "void bump(int *x) { *x += 1; }   /* may be NULL */\n"
            "int n = 1; bump(&n);",
            "void bump(int &x) { x += 1; }    /* always refers to something */\n"
            "int n = 1; bump(n);",
        ),
        question=(
            "Why can a C++ reference never be compared against null, and what "
            "would you lose if you tried to allow it?"
        ),
    ),
    Comparison(
        id="loops",
        concept="Counting versus iterating",
        languages=("cpp", "python"),
        same="Both run a body repeatedly and both must advance toward their exit.",
        different=(
            "A C++ `for` counts: it manages an index, a bound and an update.",
            "A Python `for` iterates over an object, so the index is not yours to "
            "manage and cannot go out of step.",
            "`range(5)` excludes 5, like `i < 5` — but a Python `for` over a "
            "container has no bound at all.",
            "C++ `continue` in a `for` still runs the update expression. Python's "
            "`continue` has no update to run, which is why C-style loops written "
            "in Python can spin forever.",
        ),
        snippets=(
            "for (int i = 0; i < 5; ++i) { /* 0..4 */ }",
            "for i in range(5):\n    pass                  # 0..4\n"
            "for item in items:           # no index at all\n    pass",
        ),
        question=(
            "A C++ loop body uses `continue` and your Python port freezes. Why, "
            "and how do you write the intent directly in Python?"
        ),
    ),
    Comparison(
        id="functions",
        concept="Parameter passing",
        languages=("cpp", "python"),
        same="Both pass arguments into a function.",
        different=(
            "C++ makes the choice explicit: by value copies, by reference or "
            "pointer aliases.",
            "Python has one rule. Primitives arrive as copies, so rebinding does "
            "not affect the caller; objects arrive as the same object, so "
            "mutating one is visible outside.",
            "Python therefore has no syntax to choose a mode, and no way to pass a "
            "large object by value cheaply.",
        ),
        snippets=(
            "void set(int &x)  { x = 99; }   /* caller sees 99 */\n"
            "void copy(int x)  { x = 99; }   /* caller unchanged */",
            "def set(n):  n = 99          # caller unchanged\n"
            "def mutate(lst): lst.append(99)  # caller sees it",
        ),
        question=(
            "Why does appending to a list inside a Python function change the "
            "caller's list, while assigning to a number does not?"
        ),
    ),
    Comparison(
        id="equality",
        concept="Equality and truthiness",
        languages=("cpp", "javascript"),
        same="Both compare values and both have a loose comparison people regret.",
        different=(
            "C++ compares only the type you ask for, and `==` on a pointer is an "
            "address comparison, not a contents comparison.",
            "JavaScript `==` coerces: `\"5\" == 5` is true, and `[] == false` is "
            "also true.",
            "JavaScript has `===`, which compares type and value. C++ has no "
            "equivalent because the types are already usually fixed.",
            "C++ treats any non-zero value as true; JavaScript treats an empty "
            "array as true, which surprises people coming from C.",
        ),
        snippets=(
            "if (x) { }              /* any non-zero */\nif (x == 5) { }",
            "if (x) { }              /* 0, \"\" and null are false, [] is TRUE */\n"
            "if (x === 5) { }        /* prefer this */",
        ),
        question=(
            "Write the JavaScript equivalent of C's `if (count)`, then explain "
            "what a JavaScript learner would wrongly assume about an empty array?"
        ),
    ),
    Comparison(
        id="errors",
        concept="Handling failure",
        languages=("cpp", "javascript"),
        same="Both have exceptions and both can propagate them up the stack.",
        different=(
            "C++ requires either an exception type or a value convention, and "
            "`catch` order matters because the first match wins.",
            "JavaScript has one `Error` class plus built-in subtypes, and the same "
            "first-match-wins rule applies.",
            "C++ destructors run during unwinding, which is why RAII cleanup "
            "works without any catch block.",
            "JavaScript has no destructors, so cleanup must be explicit in a "
            "`finally` block.",
        ),
        snippets=(
            "try { risky(); }\ncatch (const std::runtime_error& e) { /* RAII still cleans up */ }",
            "try { risky(); }\ncatch (error) { /* no automatic cleanup */ }\n"
            "finally { cleanup(); }",
        ),
        question=(
            "Why does C++ not usually need a `finally`-style block to release a "
            "file, and what is the JavaScript equivalent obligation?"
        ),
    ),
    Comparison(
        id="java-cpp-memory",
        concept="Memory management and garbage collection",
        languages=("java", "cpp"),
        same="Both languages run compiled object-oriented code with classes and methods.",
        different=(
            "Java runs in the JVM with an automatic Garbage Collector (GC); objects created with `new` are freed when unreachable.",
            "C++ uses deterministic lifetime (RAII, destructors, smart pointers) and direct memory management without a GC pause.",
            "Java has no pointers or manual `delete`, preventing memory leaks from forgotten frees, but gives up deterministic destruction order.",
        ),
        snippets=(
            "// Java: JVM garbage collector manages memory\nPoint p = new Point(1, 2);\n// Automatically freed when no longer referenced",
            "// C++: RAII deterministic lifetime\nauto p = std::make_unique<Point>(1, 2);\n// Freed deterministically as soon as p leaves scope",
        ),
        question="What is the main trade-off between Java's garbage collection and C++'s RAII?",
    ),
)


def by_concept(concept_id: str) -> list[Comparison]:
    """Comparisons whose ``id`` matches, plus any naming the concept."""
    return [c for c in COMPARISONS if c.id == concept_id or c.id.startswith(concept_id)]


def for_language_pair(first: str, second: str) -> list[Comparison]:
    """Comparisons involving both languages, in either order."""
    return [
        c for c in COMPARISONS
        if {c.languages[0], c.languages[1]} == {first, second}
    ]


def for_language(language: str) -> list[Comparison]:
    """Every comparison involving a language."""
    return [c for c in COMPARISONS if language in c.languages]


def searchable() -> list[Comparison]:
    return list(COMPARISONS)