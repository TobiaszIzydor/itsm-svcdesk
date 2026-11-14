# ai-generated: 80% - Claude Code wrote the parsing, matching and counting from CI-SPEC.md section 3; I checked it against the practice set and the edge cases
"""bakeoff.py - scanner SARIF + a labels file -> a per-tool confusion matrix (CI-SPEC.md P-23).

    python3 bakeoff.py --labels labels.json a.sarif b.sarif > bakeoff.json

Standard library only - it runs as `python3 -S -E bakeoff.py`. Each function names the rule it implements.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import unquote

CLASS_CWES = {  # the course table of section 3.2
    "secret": {259, 260, 321, 798},
    "injection": {74, 77, 78, 79, 80, 88, 89, 90, 91, 94, 95, 96, 611, 776, 917, 943, 1336},
    "deserialization": {502},
    "weak-crypto": {261, 326, 327, 328, 330, 331, 338, 759, 760, 916},
    "insecure-transport": {295, 297, 319, 322, 757},
    "path-traversal": {22, 23, 35, 36, 73},
    "ssrf": {918},
    "vulnerable-dependency": {937, 1035, 1104, 1395},
    "misconfiguration": {16, 215, 250, 489, 668, 732, 1188},
    "access-control": {284, 285, 639, 862, 863},
}
SEMGREP_NAMES = {"semgrep", "semgrep oss", "semgrep ce", "semgrep community edition", "semgrep pro"}
KNOWN_TOOLS = {"trivy", "grype", "osv-scanner", "gitleaks"}
TRIVY_TAG_CLASSES = {"vulnerability": "vulnerable-dependency", "secret": "secret", "misconfiguration": "misconfiguration"}
CWE_RE = re.compile(r"(?<![A-Za-z0-9])[Cc][Ww][Ee]-([0-9]+)")
TOKEN_RE = re.compile(r"[A-Za-z0-9._-]+")
NO_RULE = object()  # a result without a ruleId string: differs from every string, "" included (P-21)


def _get(obj, key):
    """obj[key] when obj is an object; a member whose value is null counts as absent."""
    return obj.get(key) if isinstance(obj, dict) else None


def _array(value) -> list:
    """An array member that is not an array has no entries."""
    return value if isinstance(value, list) else []


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _strict_equal(a, b) -> bool:
    return type(a) is type(b) and a == b


def tool_id(run: dict) -> str:
    """P-15: the tool id of a run, from tool.driver.name."""
    name = _get(_get(_get(run, "tool"), "driver"), "name")
    if not isinstance(name, str):
        return "unknown"
    name = name.strip().lower()
    if name in KNOWN_TOOLS:
        return name
    if name in SEMGREP_NAMES:
        return "semgrep"
    slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return slug or "unknown"


def _suppressed(result: dict) -> bool:
    """P-16: any suppressions other than absent, null or empty ([], {}, false, 0, "") drop the result."""
    value = result.get("suppressions")
    if value is None or value is False or value == "" or value == [] or value == {}:
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0:
        return False
    return True


def kept_results(run: dict) -> list[dict]:
    """P-16: the results of a run that count: kind absent, null or exactly "fail", and not suppressed."""
    kept = []
    for result in _array(_get(run, "results")):
        if not isinstance(result, dict):
            continue
        kind = result.get("kind")
        if kind is not None and kind != "fail":
            continue
        if _suppressed(result):
            continue
        kept.append(result)
    return kept


def physical_location(result: dict):
    """P-16: the physicalLocation of the first entry of locations[], or None."""
    locations = _array(result.get("locations"))
    if not locations:
        return None
    return _get(locations[0], "physicalLocation")


def set_file(uri: str, root: str):
    """P-17: the result's file inside the set (from the last component equal to the root), or None."""
    path = unquote(uri)
    if path[:7].lower() == "file://":
        path = path[7:]
    if path.startswith("./"):
        path = path[2:]
    parts = path.split("/")
    last = None
    for index, part in enumerate(parts):
        if part == root:
            last = index
    if last is None:
        return None
    return "/".join(parts[last:])


def result_lines(location: dict):
    """P-18: (start, end) from region.startLine and region.endLine, or None when there is no startLine of at least 1."""
    region = _get(location, "region")
    start = _get(region, "startLine")
    if not _is_int(start) or start < 1:
        return None
    end = _get(region, "endLine")
    if not _is_int(end) or end < start:
        end = start
    return start, end


def _tags(obj) -> list[str]:
    return [tag for tag in _array(_get(_get(obj, "properties"), "tags")) if isinstance(tag, str)]


def find_rule(run: dict, rule_id):
    """P-19: the first entry of tool.driver.rules[] whose id equals the result's ruleId."""
    if rule_id is None:
        return None
    for rule in _array(_get(_get(_get(run, "tool"), "driver"), "rules")):
        if isinstance(rule, dict) and _strict_equal(rule.get("id"), rule_id):
            return rule
    return None


def result_classes(tool: str, result: dict, rule) -> set[str]:
    """P-19: the classes of a result, from the first source that gives any; `other` matches no defect."""
    own = _get(_get(result, "properties"), "class")
    if isinstance(own, str) and own in CLASS_CWES:  # (a)
        return {own}
    if tool == "gitleaks":  # (b)
        return {"secret"}
    if tool in ("grype", "osv-scanner"):
        return {"vulnerable-dependency"}
    if tool == "trivy":
        classes = {TRIVY_TAG_CLASSES[t.lower()] for t in _tags(rule) if t.lower() in TRIVY_TAG_CLASSES}
        if classes:
            return classes
    cwes = set()  # (c)
    for tag in _tags(result) + _tags(rule):
        cwes.update(int(number) for number in CWE_RE.findall(tag))
    classes = {name for name, numbers in CLASS_CWES.items() if cwes & numbers}
    return classes or {"other"}  # (d)


def _pep503(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.lower())


def names_package(message, package: str) -> bool:
    """P-20: some token of message.text equals the package name under PEP 503 normalisation."""
    text = _get(message, "text")
    if not isinstance(text, str) or not isinstance(package, str):
        return False
    wanted = _pep503(package)
    for token in TOKEN_RE.findall(text):
        token = token.strip("._-")
        if token and _pep503(token) == wanted:
            return True
    return False


def matches(finding: dict, defect: dict) -> bool:
    """P-20: same file, the defect's class among the result's, and the package or overlapping lines."""
    if finding["file"] != defect.get("file") or defect.get("class") not in finding["classes"]:
        return False
    if defect["class"] == "vulnerable-dependency":
        return names_package(finding["message"], defect.get("package"))
    lines = finding["lines"]
    if lines is None:
        return False
    start, end = lines
    return start <= defect["end_line"] and defect["start_line"] <= end


def _score(numerator: int, denominator: int):
    return None if denominator == 0 else round(numerator / denominator, 4)


def confusion_matrix(labels: dict, sarif_documents: list) -> dict:
    """The matrix of P-21 and P-22 for the labels (P-14) and the parsed SARIF documents."""
    root = labels["set"]
    defects = labels["defects"]
    findings: dict[str, list[dict]] = {}
    for document in sarif_documents:
        for run in _array(_get(document, "runs")):
            if not isinstance(run, dict):
                continue
            tool = tool_id(run)
            tool_findings = findings.setdefault(tool, [])
            for result in kept_results(run):
                location = physical_location(result)
                uri = _get(_get(location, "artifactLocation"), "uri")
                if not isinstance(uri, str) or uri == "":
                    continue
                file = set_file(uri, root)
                if file is None:  # outside the set: triage material, not the matrix (P-17)
                    continue
                rule_id = result.get("ruleId")
                tool_findings.append({
                    "file": file,
                    "lines": result_lines(location),
                    "classes": result_classes(tool, result, find_rule(run, rule_id)),
                    "message": result.get("message"),
                    "rule": rule_id if isinstance(rule_id, str) else NO_RULE,
                })

    tools = {}
    for tool, tool_findings in findings.items():
        found = set()
        false_positives = set()
        for finding in tool_findings:
            hit = [index for index, defect in enumerate(defects) if matches(finding, defect)]
            if hit:
                found.update(hit)
            else:
                start, end = finding["lines"] if finding["lines"] else (None, None)
                false_positives.add((finding["rule"], finding["file"], start, end))
        tp, fp = len(found), len(false_positives)
        fn = len(defects) - tp
        tools[tool] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": _score(tp, tp + fp),
            "recall": _score(tp, tp + fn),
            "f1": _score(2 * tp, 2 * tp + fp + fn),
        }
    return {"set": root, "defects": len(defects), "tools": tools}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="per-tool confusion matrix of SARIF against labels (CI-SPEC.md P-23)")
    parser.add_argument("--labels", required=True, help="the labels file (P-14)")
    parser.add_argument("sarif", nargs="+", help="SARIF 2.1.0 files")
    args = parser.parse_args(argv)
    with open(args.labels, encoding="utf-8-sig") as fh:
        labels = json.load(fh)
    documents = []
    for path in args.sarif:
        with open(path, encoding="utf-8-sig") as fh:
            documents.append(json.load(fh))
    json.dump(confusion_matrix(labels, documents), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
