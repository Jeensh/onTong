"""UC11 — Production translator demo (W38).

Bridge to W37: now that we know the framework can READ production data, this
demo TRANSLATES production methods. Picks N `code_methods.body_text` rows from
the real `data/ontology.db` and runs JavaToPythonTranslator on each.

Result classification per method:
  PASS              — translator emitted Python without locking
  SIGNATURE_LOCKED  — translator detected an unsupported construct (graceful)
  PARSE_ERROR       — tree-sitter couldn't parse the wrapped body
  EMPTY             — body_text was empty / whitespace-only

The aggregate rate is the framework's real-world coverage measurement against
production Java. Read-only against the production DB.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc11_production_translator.run
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tree_sitter_java as tsjava
from sqlalchemy import text
from sqlalchemy.orm import Session
from tree_sitter import Language, Parser

from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator
from backend.sim_v2.demos.uc10_production_inspector.run import open_readonly_session


JAVA_LANGUAGE = Language(tsjava.language())
SAMPLE_SIZE = 50  # how many production methods to translate
DEFAULT_REPO_ID = "synthetic-5k"  # has the most volume; switchable via main()


# ─────────────────────────────────────────────────────────────────────────────
# Method fetch + parse
# ─────────────────────────────────────────────────────────────────────────────


def fetch_methods(session: Session, repo_id: str, limit: int) -> list[dict[str, Any]]:
    """Fetch up to `limit` methods that have non-empty body_text."""
    rows = session.execute(
        text(
            "SELECT fqn, name, body_text, parent_type_fqn, return_type "
            "FROM code_methods "
            "WHERE repo_id = :r "
            "  AND body_text IS NOT NULL "
            "  AND length(trim(body_text)) > 0 "
            "ORDER BY fqn "
            "LIMIT :n"
        ),
        {"r": repo_id, "n": limit},
    ).fetchall()
    return [
        {
            "fqn":         r[0],
            "name":        r[1],
            "body_text":   r[2],
            "parent_type": r[3],
            "return_type": r[4],
        }
        for r in rows
    ]


def parse_method_declaration(body_text: str):
    """Wrap `body_text` in a synthetic class so tree-sitter can parse it as a
    method_declaration. Returns the method_declaration node, or None on parse
    failure / when no method_declaration is found."""
    wrapped = "class _T {\n" + body_text + "\n}"
    parser = Parser(JAVA_LANGUAGE)
    tree = parser.parse(wrapped.encode())
    root = tree.root_node
    # program > class_declaration > class_body > method_declaration
    for cls in root.children:
        if cls.type != "class_declaration":
            continue
        for child in cls.children:
            if child.type != "class_body":
                continue
            for member in child.named_children:
                if member.type == "method_declaration":
                    return member
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Classification
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class MethodResult:
    fqn:           str
    status:        str   # PASS / SIGNATURE_LOCKED / PARSE_ERROR / EMPTY
    python_lines:  int = 0
    notes:         tuple[str, ...] = ()
    error:         str = ""


@dataclass
class Report:
    repo_id:           str
    sample_size:       int
    pass_count:        int = 0
    locked_count:      int = 0
    parse_error_count: int = 0
    empty_count:       int = 0
    locked_notes:      list[str] = field(default_factory=list)
    sample_results:    list[MethodResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        nonempty = self.sample_size - self.empty_count
        return self.pass_count / nonempty if nonempty else 0.0


def translate_method(method: dict[str, Any]) -> MethodResult:
    """Try to translate one production method. Always returns a MethodResult."""
    body_text = method["body_text"].strip()
    if not body_text:
        return MethodResult(fqn=method["fqn"], status="EMPTY")

    try:
        node = parse_method_declaration(body_text)
    except Exception as e:
        return MethodResult(fqn=method["fqn"], status="PARSE_ERROR", error=str(e))

    if node is None:
        return MethodResult(fqn=method["fqn"], status="PARSE_ERROR",
                            error="no method_declaration found in wrapped source")

    try:
        translator = JavaToPythonTranslator()
        out = translator.translate(node, indent=0)
    except Exception as e:
        return MethodResult(fqn=method["fqn"], status="PARSE_ERROR", error=f"translator: {e}")

    if out.signature_locked:
        return MethodResult(
            fqn=method["fqn"],
            status="SIGNATURE_LOCKED",
            python_lines=len(out.python_source.splitlines()),
            notes=tuple(out.notes),
        )
    return MethodResult(
        fqn=method["fqn"],
        status="PASS",
        python_lines=len(out.python_source.splitlines()),
        notes=tuple(out.notes),
    )


def run_translation_survey(session: Session, repo_id: str, sample_size: int) -> Report:
    methods = fetch_methods(session, repo_id, sample_size)
    report = Report(repo_id=repo_id, sample_size=len(methods))
    for m in methods:
        result = translate_method(m)
        report.sample_results.append(result)
        if result.status == "PASS":
            report.pass_count += 1
        elif result.status == "SIGNATURE_LOCKED":
            report.locked_count += 1
            for n in result.notes:
                if n not in report.locked_notes:
                    report.locked_notes.append(n)
        elif result.status == "PARSE_ERROR":
            report.parse_error_count += 1
        else:
            report.empty_count += 1
    return report


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────


def _banner(text: str) -> None:
    print("─" * 78)
    print(text)
    print("─" * 78)


def main() -> int:
    print("=" * 78)
    print(f"UC11 — Production translator survey (W38, sample={SAMPLE_SIZE})")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print("  data/ontology.db not found — skipping (CI / fresh checkout)")
        return 0
    try:
        report = run_translation_survey(session, DEFAULT_REPO_ID, SAMPLE_SIZE)
        if report.sample_size == 0:
            print(f"  No methods with body_text in repo {DEFAULT_REPO_ID!r}")
            return 0

        _banner(f"Repo: {report.repo_id} (sample size: {report.sample_size})")
        print(f"  PASS              : {report.pass_count}")
        print(f"  SIGNATURE_LOCKED  : {report.locked_count}")
        print(f"  PARSE_ERROR       : {report.parse_error_count}")
        print(f"  EMPTY             : {report.empty_count}")
        nonempty = report.sample_size - report.empty_count
        print(f"  Pass rate         : {report.pass_count} / {nonempty} non-empty = {report.pass_rate * 100:.1f}%")
        print()

        if report.locked_notes:
            _banner("Distinct SIGNATURE_LOCKED reasons (top 8)")
            for note in report.locked_notes[:8]:
                print(f"  • {note}")
            if len(report.locked_notes) > 8:
                print(f"  … (+{len(report.locked_notes) - 8} more)")
            print()

        _banner("Per-method sample (first 10)")
        for r in report.sample_results[:10]:
            short_fqn = r.fqn[-72:] if len(r.fqn) > 72 else r.fqn
            print(f"  {r.status:<18} {short_fqn}")
        print()

        # Always succeed — the demo's value is the survey itself, not pass-rate ≥ N
        print(f"✓ Production translator survey complete — {report.pass_rate * 100:.1f}% PASS on real Java methods")
        print(f"  SIGNATURE_LOCKED reasons surface the highest-value translator coverage gaps")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
