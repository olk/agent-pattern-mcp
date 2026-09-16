#!/usr/bin/env python3
"""
Consistency checker for agent pattern JSON files.

Checks:
   1. suitable_domains / unsuitable_domains are disjoint
   2. All migration_from / migration_to targets exist in the catalog
   3. Migration graph reciprocity (warnings, not failures)
   4. No non-ASCII characters in name, category, topology, or domain fields
   5. Domain values are valid AgentDomain enum values
   6. Reference URLs are well-formed
   7. quality_attributes keys match the Pattern schema's seven attributes

Usage:
  python scripts/check_pattern_consistency.py          # report only
  python scripts/check_pattern_consistency.py --fix   # auto-fix whitespace issues
  python scripts/check_pattern_consistency.py --fix --dry-run  # show what would change
"""

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.schemas.enums import AgentDomain
from src.schemas.patterns import PatternQualityAttributes


class Issue(NamedTuple):
    severity: str
    pattern: str
    message: str


PATTERN_DIR = Path(__file__).parent.parent / "pattern"
VALID_DOMAINS = {d.value for d in AgentDomain}
VALID_QUALITY_ATTRIBUTE_KEYS = set(PatternQualityAttributes.model_fields.keys())


def load_patterns() -> dict[str, dict]:
    """Load all pattern JSON files, keyed by pattern name."""
    patterns = {}
    for path in sorted(PATTERN_DIR.glob("*-pattern.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        patterns[data["name"]] = data
    return patterns


def check_domains_disjoint(patterns: dict[str, dict]) -> list[Issue]:
    """Check suitable_domains and unsuitable_domains do not overlap."""
    issues = []
    for name, p in patterns.items():
        suitable = {d.lower().replace(" ", "-") for d in p.get("suitable_domains", [])}
        unsuitable = {d.lower().replace(" ", "-") for d in p.get("unsuitable_domains", [])}
        overlap = suitable & unsuitable
        if overlap:
            issues.append(Issue(
                "ERROR",
                name,
                f"suitable_domains and unsuitable_domains overlap: {sorted(overlap)}"
            ))
    return issues


def check_domain_validity(patterns: dict[str, dict]) -> list[Issue]:
    """Check domain values are valid AgentDomain enum values."""
    issues = []
    for name, p in patterns.items():
        for d in p.get("suitable_domains", []):
            normalized = d.lower().replace(" ", "-")
            if normalized not in VALID_DOMAINS:
                issues.append(Issue(
                    "ERROR",
                    name,
                    f"unknown domain in suitable_domains: {d!r} (normalized: {normalized})"
                ))
        for d in p.get("unsuitable_domains", []):
            normalized = d.lower().replace(" ", "-")
            if normalized not in VALID_DOMAINS:
                issues.append(Issue(
                    "ERROR",
                    name,
                    f"unknown domain in unsuitable_domains: {d!r} (normalized: {normalized})"
                ))
    return issues


def check_quality_attribute_keys(patterns: dict[str, dict]) -> list[Issue]:
    """Check quality_attributes contains only the schema-defined keys."""
    issues = []
    for name, p in patterns.items():
        unknown = set(p.get("quality_attributes", {})) - VALID_QUALITY_ATTRIBUTE_KEYS
        if unknown:
            issues.append(Issue(
                "ERROR",
                name,
                f"unknown quality_attributes keys: {sorted(unknown)} "
                f"(valid: {sorted(VALID_QUALITY_ATTRIBUTE_KEYS)})"
            ))
    return issues


def check_migration_edges(patterns: dict[str, dict]) -> tuple[list[Issue], list[Issue]]:
    """Check migration targets exist and graph is well-formed."""
    all_names = set(patterns.keys())
    errors = []
    warnings = []
    for name, p in patterns.items():
        for ref in p.get("migration_from", []):
            if ref not in all_names:
                errors.append(Issue(
                    "ERROR",
                    name,
                    f"migration_from references unknown pattern: {ref}"
                ))
        for ref in p.get("migration_to", []):
            if ref not in all_names:
                errors.append(Issue(
                    "ERROR",
                    name,
                    f"migration_to references unknown pattern: {ref}"
                ))
        if name in p.get("migration_from", []):
            warnings.append(Issue(
                "WARNING",
                name,
                "pattern lists itself in migration_from"
            ))
        if name in p.get("migration_to", []):
            warnings.append(Issue(
                "WARNING",
                name,
                "pattern lists itself in migration_to"
            ))
    return errors, warnings


def check_migration_reciprocity(patterns: dict[str, dict]) -> list[Issue]:
    """Warn about migration edges that lack reciprocal edges."""
    warnings = []
    for name, p in patterns.items():
        for ref in p.get("migration_to", []):
            if ref in patterns:
                rev = patterns[ref].get("migration_from", [])
                if name not in rev:
                    warnings.append(Issue(
                        "WARNING",
                        name,
                        f"migrates to '{ref}' but '{ref}' does not list '{name}' in migration_from"
                    ))
    return warnings


def check_non_ascii_in_key_fields(patterns: dict[str, dict]) -> list[Issue]:
    """Check name, category, topology, and domain fields contain only ASCII."""
    issues = []
    for name, p in patterns.items():
        fields: list[tuple[str, str]] = [
            ("name", name),
            ("topology", p.get("topology", "")),
            ("category", p.get("category", "")),
        ]
        fields.extend(("suitable_domains", d) for d in p.get("suitable_domains", []))
        fields.extend(("unsuitable_domains", d) for d in p.get("unsuitable_domains", []))
        for field, value in fields:
            for ch in value:
                if ord(ch) >= 128:
                    issues.append(Issue(
                        "ERROR",
                        name,
                        f"non-ASCII character in {field}: {ch!r}"
                    ))
    return issues


def check_reference_urls(patterns: dict[str, dict]) -> list[Issue]:
    """Check reference URLs are well-formed."""
    issues = []
    url_re = re.compile(r"https?://[^\s]+")
    for name, p in patterns.items():
        for ref in p.get("references", []):
            urls = url_re.findall(ref)
            for url in urls:
                parsed = urllib.parse.urlparse(url)
                if not parsed.scheme or not parsed.netloc:
                    issues.append(Issue(
                        "ERROR",
                        name,
                        f"malformed URL in references: {url}"
                    ))
                if len(url) > 500:
                    issues.append(Issue(
                        "WARNING",
                        name,
                        f"very long URL may cause issues: {url[:80]}..."
                    ))
    return issues


def fix_whitespace_in_domains(patterns: dict[str, dict], dry_run: bool = False) -> dict[str, list[str]]:
    """Fix whitespace issues in domain fields. Returns dict of pattern -> list of changes."""
    changes = {}
    for name, p in patterns.items():
        pattern_changes = []
        for field in ("suitable_domains", "unsuitable_domains"):
            original = list(p.get(field, []))
            fixed = [d.replace(" ", "-").lower() for d in original]
            if original != fixed:
                pattern_changes.append(f"  {field}:")
                for orig, f in zip(original, fixed, strict=False):
                    if orig != f:
                        pattern_changes.append(f"    {orig!r} -> {f!r}")
        if pattern_changes:
            changes[name] = pattern_changes
            if not dry_run:
                for field in ("suitable_domains", "unsuitable_domains"):
                    if field in p:
                        p[field] = [d.replace(" ", "-").lower() for d in p[field]]
    return changes


def write_pattern(name: str, data: dict) -> None:
    path = PATTERN_DIR / f"{name}-pattern.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def apply_domain_whitespace_fixes(args: argparse.Namespace, patterns: dict[str, dict]) -> None:
    """Apply (or preview) domain whitespace fixes per --fix/--dry-run flags."""
    if args.fix and not args.dry_run:
        changes = fix_whitespace_in_domains(patterns, dry_run=False)
        if changes:
            for name, change_list in changes.items():
                print(f"\nFixed whitespace in '{name}':")
                for c in change_list:
                    print(c)
                write_pattern(name, patterns[name])

    if args.dry_run and args.fix:
        changes = fix_whitespace_in_domains(patterns, dry_run=True)
        if changes:
            print("\nWould fix whitespace in domains:")
            for name, change_list in changes.items():
                print(f"\n  Pattern '{name}':")
                for c in change_list:
                    print(c)
        else:
            print("\nNo whitespace fixes needed.")


def print_issue_report(
    errors: list[Issue], warnings: list[Issue], all_warnings: list[Issue]
) -> None:
    """Print the ERROR/WARNING/INFO report sections."""
    if errors:
        print(f"\n{len(errors)} ERROR(S):")
        for issue in errors:
            print(f"  [{issue.pattern}] {issue.message}")

    if warnings:
        print(f"\n{len(warnings)} WARNING(S):")
        for issue in warnings:
            print(f"  [{issue.pattern}] {issue.message}")

    if all_warnings:
        print(f"\n{len(all_warnings)} INFO/WARNING(S):")
        for issue in all_warnings:
            print(f"  [{issue.pattern}] {issue.message}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check agent pattern consistency")
    parser.add_argument("--fix", action="store_true", help="Auto-fix whitespace issues in domains")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without modifying files")
    args = parser.parse_args()

    patterns = load_patterns()
    print(f"Loaded {len(patterns)} patterns from {PATTERN_DIR}")

    all_issues: list[Issue] = []
    all_warnings: list[Issue] = []

    all_issues.extend(check_domains_disjoint(patterns))
    all_issues.extend(check_domain_validity(patterns))
    all_issues.extend(check_quality_attribute_keys(patterns))

    errs, warns = check_migration_edges(patterns)
    all_issues.extend(errs)
    all_warnings.extend(warns)

    all_warnings.extend(check_migration_reciprocity(patterns))
    all_issues.extend(check_non_ascii_in_key_fields(patterns))
    all_issues.extend(check_reference_urls(patterns))

    apply_domain_whitespace_fixes(args, patterns)

    errors = [i for i in all_issues if i.severity == "ERROR"]
    warnings = [i for i in all_issues if i.severity == "WARNING"]
    all_warnings.extend([i for i in all_issues if i.severity == "WARNING"])

    print_issue_report(errors, warnings, all_warnings)

    if errors:
        print(f"\nFAILED: {len(errors)} error(s) found")
        return 1
    if warnings:
        print(f"\nPASSED with {len(warnings)} warning(s)")
        return 0
    print("\nPASSED: all checks clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
