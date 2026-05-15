"""Recipe 4 — Stub-injected production behavioral verification end-to-end.

Section 3 의 sandbox 가 `cumulativeProductivity` 같은 *진짜 production 메서드* 를
in-process exec 할 수 있게 되는 full path:

    1. action 의 code_method_fqn 으로 Java body_text 로드
    2. JavaToPythonTranslator 로 변환 (W75 idiom rewrite 자동 적용)
    3. W71 으로 fixture 합성
    4. W74 build_stub_namespace 로 anchor + entity + bean stubs 자동 derive
    5. TwinInvariantRunner 에 stub_namespace 주입하여 실행
    6. PASS / FAIL_* 결과 표 surface

실행:
    .venv/bin/python toClaude/modeling/section4-verification/section3_handoff/usage-recipes/recipe-4-stub-injected-production.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

import tree_sitter_java as tsjava
from sqlalchemy import text
from tree_sitter import Language, Parser

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
)
from backend.sim_v2.core.synthesizer.java_translator import (
    JavaToPythonTranslator,
)
from backend.sim_v2.core.verification.fixture_synthesizer import (
    synthesize_fixtures_for_action,
)
from backend.sim_v2.core.verification.sandbox_stubs import (
    build_stub_namespace,
)
from backend.sim_v2.core.verification.twin_invariants import (
    TwinInvariantRunner,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


JAVA = Language(tsjava.language())


def _translate_body(body_text: str) -> tuple[str, str] | None:
    wrapped = f"public class C {{ {body_text} }}"
    tree = Parser(JAVA).parse(wrapped.encode())
    method = None
    for c in tree.root_node.children:
        if c.type == "class_declaration":
            body_n = next((x for x in c.children if x.type == "class_body"), None)
            if body_n is None:
                return None
            for m in body_n.named_children:
                if m.type == "method_declaration":
                    method = m
                    break
    if method is None:
        return None
    result = JavaToPythonTranslator().translate(method, indent=0)
    src = result.python_source
    first = src.splitlines()[0]
    if not first.startswith("def "):
        return None
    fn = first[4:].split("(", 1)[0].strip()
    return src, fn


def main() -> int:
    if not PRODUCTION_DB_PATH.exists():
        print(f"production DB not found at {PRODUCTION_DB_PATH}")
        return 1
    session = open_readonly_session()
    if session is None:
        return 1
    try:
        actions = load_actions(session, "slab-design-real-v2")
        # 데모용 — 가장 풍부한 메서드 1건 (anchor 상수 다수)
        target = next(
            a for a in actions
            if a.fqn == "action.scm.product.cumulative_productivity"
        )
        if not target.code_method_fqn:
            print("action.scm.product.cumulative_productivity has no code link")
            return 1

        # ─── 1) Java body load ────────────────────────────────────────────
        row = session.execute(
            text(
                "SELECT body_text FROM code_methods "
                "WHERE fqn = :f AND repo_id = :r"
            ),
            {"f": target.code_method_fqn, "r": target.repo_id},
        ).fetchone()
        if not row or not row[0]:
            print("no body_text found")
            return 1
        body_text = row[0]
        print(f"=== action: {target.fqn}")
        print(f"=== Java method: {target.code_method_fqn}")
        print(f"=== Java body (preview):")
        for line in body_text.splitlines()[:4]:
            print(f"    {line}")
        print("    ...")
        print()

        # ─── 2) Translate (W75 idiom rewrite 자동 적용) ──────────────────
        translated = _translate_body(body_text)
        if translated is None:
            print("translation failed"); return 1
        python_source, function_name = translated
        print(f"=== Python translation (preview):")
        for line in python_source.splitlines()[:6]:
            print(f"    {line}")
        print(f"    ... (function_name={function_name})")
        print()

        # ─── 3) W71 fixture 합성 ──────────────────────────────────────────
        rep = synthesize_fixtures_for_action(
            session, target,
            function_name=function_name,
            python_source=python_source,
        )
        print(f"=== W71 fixture synthesis")
        print(f"    primitive params : {rep.synthesizable_params}")
        print(f"    skipped params   : {rep.skipped_params}")
        print(f"    fixtures         : {len(rep.fixtures)}")
        print()

        # ─── 4) W74 stub namespace 자동 derive ───────────────────────────
        stub_ns = build_stub_namespace(
            session, target.code_method_fqn, target.repo_id, python_source,
        )
        print(f"=== W74 stub namespace ({len(stub_ns)} entries)")
        for name, val in list(stub_ns.items())[:6]:
            kind = type(val).__name__
            short = repr(val)[:60]
            print(f"    {name:30s}  ({kind}) {short}")
        if len(stub_ns) > 6:
            print(f"    ... and {len(stub_ns) - 6} more")
        print()

        # ─── 5) W72 invariant 검증 (with stub) ───────────────────────────
        # production method 가 합법적으로 throw 할 수 있는 exception 들 — UC40
        # 의 permissive 세트와 동일.
        runner = TwinInvariantRunner(
            declared_return="float",
            allowed_exceptions=(
                "AlgorithmException", "IllegalStateException",
                "ValueError", "TypeError", "RuntimeError",
                "ArithmeticError", "AttributeError",
            ),
            stub_namespace=stub_ns,
        )
        results = [runner.check(f) for f in rep.fixtures]
        passing = sum(1 for r in results if r.passed)

        print(f"=== W72 invariant check (in-process safe exec)")
        print(f"    fixtures PASS : {passing} / {len(results)}")
        print(f"    sample results:")
        for r in results[:4]:
            print(f"      {r.fixture_id:38s}  {r.status}")
        print()

        if passing == len(results):
            print("✓ END-TO-END SUCCESS — production method behavioral PASS")
            print("  W71 → W75 idiom rewrite → W74 stub injection → W72 invariant")
        else:
            print(f"  {len(results) - passing} fixtures need deeper stub or")
            print(f"  typed-return stub. UC40 의 FAIL_RETURN_TYPE 카테고리 참조.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
