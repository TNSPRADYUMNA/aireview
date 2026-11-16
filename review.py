"""Evidence-linked review findings for changed Python lines."""
import ast
from difflib import SequenceMatcher
from hashlib import sha256


def review(before, after):
    previous, current = before.splitlines(), after.splitlines()
    changes = {i + 1 for tag, _, _, j0, j1 in SequenceMatcher(
        None, previous, current, autojunk=False).get_opcodes() if tag in ("replace", "insert")
               for i in range(j0, j1)}
    findings = []

    def emit(code, line, title, fix, confidence):
        if line not in changes or not 0 < line <= len(current):
            return
        identifier = sha256(f"{code}:{line}:{current[line-1]}".encode()).hexdigest()[:16]
        findings.append({"id": identifier, "rule": code, "line": line, "title": title,
                         "evidence": current[line-1].strip(), "suggestion": fix, "confidence": confidence})

    try:
        tree = ast.parse(after)
    except SyntaxError as error:
        emit("syntax", error.lineno, "Python syntax error", error.msg, "direct")
    else:
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                emit("bare-except", node.lineno, "Bare exception handler",
                     "Catch the expected exception types and report a failed operation.", "direct")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defaults = node.args.defaults + [x for x in node.args.kw_defaults if x is not None]
                for value in defaults:
                    if isinstance(value, (ast.List, ast.Dict, ast.Set)):
                        emit("mutable-default", value.lineno, "Mutable default argument",
                             "Initialize a fresh collection inside the function when no argument is supplied.", "direct")
            if isinstance(node, ast.ExceptHandler) and all(isinstance(item, ast.Pass) for item in node.body):
                line = node.body[0].lineno
                emit("silent-except", line, "Exception is silently discarded",
                     "Confirm that ignoring this failure is intentional, or report it to the caller.", "review")
    findings.sort(key=lambda item: (item["line"], item["rule"]))
    return {"changed_lines": len(changes), "findings": findings}
