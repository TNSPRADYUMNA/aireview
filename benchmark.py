"""Evaluate exact rule/line matches on curated before/after pairs."""
import json
from pathlib import Path

from review import review

FIXTURES = [
    ("", "def f(data=[]):\n    return data\n", [("mutable-default", 1)]),
    ("", "def f(data=None):\n    return [] if data is None else data\n", []),
    ("", "try:\n    work()\nexcept:\n    recover()\n", [("bare-except", 3)]),
    ("", "try:\n    work()\nexcept OSError:\n    pass\n", [("silent-except", 4)]),
    ("", "try:\n    work()\nexcept OSError:\n    recover()\n", []),
    ("def f(data=[]):\n    return data\n", "def f(data=[]):\n    return len(data)\n", []),
    ("", "def f(x:\n    pass", [("syntax", 1)]),
    ("", "def f(x, *, y={}):\n    return x\n", [("mutable-default", 1)]),
    ("", "try:\n    work()\nexcept:\n    pass\n", [("bare-except", 3), ("silent-except", 4)]),
    ("", "def f(x):\n    return {}\n", []),
]


if __name__ == "__main__":
    rows = []
    for index, (before, after, expected) in enumerate(FIXTURES):
        actual = [(row["rule"], row["line"]) for row in review(before, after)["findings"]]
        rows.append({"case": index + 1, "expected": expected, "actual": actual,
                     "exact_match": set(actual) == set(expected)})
    result = {"correct": sum(row["exact_match"] for row in rows), "cases": rows}
    Path("results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{result['correct']}/{len(rows)} exact fixture matches")
