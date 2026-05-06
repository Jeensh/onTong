"""OD-11-B5-8 : Spring ReflectionAnalyzer — static reflection call marker.

감지 대상 (method/constructor body 내 호출):
  - `Class.forName("com.x.MyClass")` — static class lookup
  - `Proxy.newProxyInstance(loader, ifaces, handler)` — JDK dynamic proxy
  - `ctx.getBean("name")` — Spring ApplicationContext bean lookup by name
  - `clazz.getMethod("x")` / `clazz.getDeclaredMethod("x")` — method lookup
  - `clazz.getField("x")` / `clazz.getDeclaredField("x")` — field lookup

출력 포맷:
  - `method.attributes["reflection_calls"] = [{"api": "...", "arg": "..." or "<dynamic>", "line": N}, ...]`
  - `constructor.attributes["reflection_calls"] = [...]`
  - API 이름 규약:
      `Class.forName` / `Proxy.newProxyInstance` (static call on well-known class) 는 prefix 포함,
      나머지는 bare method name (getBean/getMethod/getDeclaredMethod/getField/getDeclaredField).

설계:
  - `analyze()` 는 Protocol 호환을 위해 `([], [])` 반환.
  - 대신 `enrich(entities, relations, tree, pkg_name)` 후처리로 METHOD/CONSTRUCTOR 속성에 merge.
  - PoC 범위: `invoke` / `newInstance` 은 noise 가 커서 제외 (B7 런타임 collector 에서 보강).
"""

from __future__ import annotations

from pathlib import Path

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.modeling.code_analysis.java_parser import JavaParser
from backend.modeling.code_analysis.parser_protocol import EntityKinds
from backend.modeling.code_analysis.spring import ReflectionAnalyzer

_LANG = Language(tsjava.language())


def _parse(src: str):
    p = Parser(_LANG)
    return p.parse(src.encode())


def _calls(entity) -> list[dict]:
    val = entity.attributes.get("reflection_calls")
    return val if isinstance(val, list) else []


# ---------------------------------------------------------------------------
# Standalone analyze() — no effect (Protocol compat)
# ---------------------------------------------------------------------------
def test_reflection_analyzer_analyze_returns_empty() -> None:
    src = """
package com.x;
public class J {
    public void run() {
        Class.forName("com.x.MyClass");
    }
}
"""
    tree = _parse(src)
    a = ReflectionAnalyzer()
    entities, relations = a.analyze(
        tree=tree, content=src.encode(), file_path="J.java", pkg_name="com.x",
    )
    assert entities == []
    assert relations == []


# ---------------------------------------------------------------------------
# Class.forName — static + dynamic
# ---------------------------------------------------------------------------
def test_class_forname_with_string_literal() -> None:
    src = """
package com.x;
public class Loader {
    public void load() {
        Class.forName("com.x.MyClass");
    }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("Loader.java"), src)
    method = next(
        e for e in result.entities
        if e.kind == EntityKinds.METHOD and e.qualified_name == "com.x.Loader.load"
    )
    calls = _calls(method)
    assert len(calls) == 1
    assert calls[0]["api"] == "Class.forName"
    assert calls[0]["arg"] == "com.x.MyClass"
    assert calls[0]["line"] >= 1


def test_class_forname_with_variable_arg() -> None:
    src = """
package com.x;
public class Loader {
    public void load(String className) {
        Class.forName(className);
    }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("Loader.java"), src)
    method = next(
        e for e in result.entities
        if e.kind == EntityKinds.METHOD and e.qualified_name == "com.x.Loader.load"
    )
    calls = _calls(method)
    assert len(calls) == 1
    assert calls[0]["api"] == "Class.forName"
    assert calls[0]["arg"] == "className"
    assert calls[0]["arg_kind"] == "variable"


# ---------------------------------------------------------------------------
# ApplicationContext.getBean(String)
# ---------------------------------------------------------------------------
def test_get_bean_by_name() -> None:
    src = """
package com.x;
import org.springframework.context.ApplicationContext;
public class BeanLookup {
    private final ApplicationContext ctx;
    public BeanLookup(ApplicationContext c) { this.ctx = c; }
    public Object svc() {
        return ctx.getBean("orderService");
    }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("BeanLookup.java"), src)
    method = next(
        e for e in result.entities
        if e.kind == EntityKinds.METHOD and e.qualified_name == "com.x.BeanLookup.svc"
    )
    calls = _calls(method)
    assert len(calls) == 1
    assert calls[0]["api"] == "getBean"
    assert calls[0]["arg"] == "orderService"


def test_get_bean_by_class_is_type_arg() -> None:
    src = """
package com.x;
public class BeanLookup {
    public Object svc() {
        return ctx.getBean(OrderService.class);
    }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("BeanLookup.java"), src)
    method = next(
        e for e in result.entities
        if e.kind == EntityKinds.METHOD and e.qualified_name == "com.x.BeanLookup.svc"
    )
    calls = _calls(method)
    assert len(calls) == 1
    assert calls[0]["api"] == "getBean"
    assert calls[0]["arg"] == "OrderService"
    assert calls[0]["arg_kind"] == "type"


# ---------------------------------------------------------------------------
# getMethod / getDeclaredMethod / getField / getDeclaredField
# ---------------------------------------------------------------------------
def test_get_method_captured() -> None:
    src = """
package com.x;
public class R {
    public void scan(Class<?> clazz) throws Exception {
        clazz.getMethod("doStuff");
    }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("R.java"), src)
    method = next(
        e for e in result.entities
        if e.kind == EntityKinds.METHOD and e.qualified_name == "com.x.R.scan"
    )
    calls = _calls(method)
    assert len(calls) == 1
    assert calls[0]["api"] == "getMethod"
    assert calls[0]["arg"] == "doStuff"


def test_get_declared_method_captured() -> None:
    src = """
package com.x;
public class R {
    public void scan(Class<?> clazz) throws Exception {
        clazz.getDeclaredMethod("secret");
    }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("R.java"), src)
    method = next(
        e for e in result.entities
        if e.kind == EntityKinds.METHOD and e.qualified_name == "com.x.R.scan"
    )
    calls = _calls(method)
    assert calls[0]["api"] == "getDeclaredMethod"
    assert calls[0]["arg"] == "secret"


def test_get_field_and_get_declared_field_captured() -> None:
    src = """
package com.x;
public class R {
    public void scan(Class<?> clazz) throws Exception {
        clazz.getField("id");
        clazz.getDeclaredField("secret");
    }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("R.java"), src)
    method = next(
        e for e in result.entities
        if e.kind == EntityKinds.METHOD and e.qualified_name == "com.x.R.scan"
    )
    calls = _calls(method)
    assert len(calls) == 2
    apis = [c["api"] for c in calls]
    args = [c["arg"] for c in calls]
    assert "getField" in apis
    assert "getDeclaredField" in apis
    assert "id" in args
    assert "secret" in args


# ---------------------------------------------------------------------------
# Proxy.newProxyInstance — always prefixed (static API)
# ---------------------------------------------------------------------------
def test_proxy_new_proxy_instance() -> None:
    src = """
package com.x;
import java.lang.reflect.Proxy;
public class Fac {
    public Object make(ClassLoader loader, Class<?>[] ifaces, Object handler) {
        return Proxy.newProxyInstance(loader, ifaces, handler);
    }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("Fac.java"), src)
    method = next(
        e for e in result.entities
        if e.kind == EntityKinds.METHOD and e.qualified_name == "com.x.Fac.make"
    )
    calls = _calls(method)
    assert len(calls) == 1
    assert calls[0]["api"] == "Proxy.newProxyInstance"
    # first arg is a variable identifier `loader`
    assert calls[0]["arg"] == "loader"
    assert calls[0]["arg_kind"] == "variable"


# ---------------------------------------------------------------------------
# Multiple reflection calls in a single method
# ---------------------------------------------------------------------------
def test_multiple_reflection_calls_in_one_method() -> None:
    src = """
package com.x;
public class R {
    public void bootstrap() throws Exception {
        Class<?> c = Class.forName("com.x.A");
        c.getMethod("run");
        c.getDeclaredField("state");
    }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("R.java"), src)
    method = next(
        e for e in result.entities
        if e.kind == EntityKinds.METHOD and e.qualified_name == "com.x.R.bootstrap"
    )
    calls = _calls(method)
    assert len(calls) == 3
    apis = [c["api"] for c in calls]
    assert "Class.forName" in apis
    assert "getMethod" in apis
    assert "getDeclaredField" in apis
    # ordered by line number (source order)
    lines = [c["line"] for c in calls]
    assert lines == sorted(lines)


# ---------------------------------------------------------------------------
# Methods without reflection — no attribute set
# ---------------------------------------------------------------------------
def test_method_without_reflection_has_no_attribute() -> None:
    src = """
package com.x;
public class Plain {
    public int add(int a, int b) { return a + b; }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("Plain.java"), src)
    method = next(
        e for e in result.entities
        if e.kind == EntityKinds.METHOD and e.qualified_name == "com.x.Plain.add"
    )
    assert "reflection_calls" not in method.attributes


# ---------------------------------------------------------------------------
# Nested blocks — try/catch, lambdas, if branches
# ---------------------------------------------------------------------------
def test_nested_try_catch_reflection_detected() -> None:
    src = """
package com.x;
public class R {
    public void run() {
        try {
            Class.forName("com.x.MyClass");
        } catch (Exception ex) {
            // swallow
        }
    }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("R.java"), src)
    method = next(
        e for e in result.entities
        if e.kind == EntityKinds.METHOD and e.qualified_name == "com.x.R.run"
    )
    calls = _calls(method)
    assert len(calls) == 1
    assert calls[0]["api"] == "Class.forName"


def test_nested_lambda_reflection_detected() -> None:
    src = """
package com.x;
import java.util.List;
public class R {
    public void run(List<String> names) {
        names.forEach(n -> {
            try { Class.forName(n); } catch (Exception e) {}
        });
    }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("R.java"), src)
    method = next(
        e for e in result.entities
        if e.kind == EntityKinds.METHOD and e.qualified_name == "com.x.R.run"
    )
    calls = _calls(method)
    assert len(calls) == 1
    assert calls[0]["api"] == "Class.forName"
    assert calls[0]["arg"] == "n"
    assert calls[0]["arg_kind"] == "variable"


# ---------------------------------------------------------------------------
# Constructor body also gets enriched
# ---------------------------------------------------------------------------
def test_constructor_body_reflection_detected() -> None:
    src = """
package com.x;
public class Eager {
    public Eager() throws Exception {
        Class.forName("com.x.Bootstrap");
    }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("Eager.java"), src)
    ctor = next(
        e for e in result.entities
        if e.kind == EntityKinds.CONSTRUCTOR and e.qualified_name == "com.x.Eager.Eager"
    )
    calls = _calls(ctor)
    assert len(calls) == 1
    assert calls[0]["api"] == "Class.forName"
    assert calls[0]["arg"] == "com.x.Bootstrap"


# ---------------------------------------------------------------------------
# Non-reflection method invocations ignored
# ---------------------------------------------------------------------------
def test_non_reflection_calls_not_captured() -> None:
    src = """
package com.x;
public class Plain {
    public void run() {
        System.out.println("hi");
        this.helper();
        new Inner().doWork();
    }
    private void helper() {}
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("Plain.java"), src)
    method = next(
        e for e in result.entities
        if e.kind == EntityKinds.METHOD and e.qualified_name == "com.x.Plain.run"
    )
    assert "reflection_calls" not in method.attributes


def test_invoke_and_new_instance_not_captured_in_poc() -> None:
    """PoC scope: `Method.invoke` 와 `Constructor.newInstance` 는 noise 가 커서 감지 제외."""
    src = """
package com.x;
public class R {
    public void run(java.lang.reflect.Method m, Object target) throws Exception {
        m.invoke(target);
        java.lang.reflect.Constructor<?> c = null;
        c.newInstance();
    }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("R.java"), src)
    method = next(
        e for e in result.entities
        if e.kind == EntityKinds.METHOD and e.qualified_name == "com.x.R.run"
    )
    # PoC 는 invoke/newInstance 모두 skip — 속성 없음
    assert "reflection_calls" not in method.attributes


# ---------------------------------------------------------------------------
# Scope isolation — only the annotated method, not siblings
# ---------------------------------------------------------------------------
def test_reflection_scoped_to_single_method() -> None:
    src = """
package com.x;
public class R {
    public void reflective() {
        Class.forName("com.x.A");
    }
    public void boring() {
        System.out.println("hi");
    }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("R.java"), src)
    methods = {
        e.qualified_name: e for e in result.entities
        if e.kind == EntityKinds.METHOD
    }
    assert "reflection_calls" in methods["com.x.R.reflective"].attributes
    assert "reflection_calls" not in methods["com.x.R.boring"].attributes


# ---------------------------------------------------------------------------
# Enrich hook & standalone
# ---------------------------------------------------------------------------
def test_enrich_hook_exists() -> None:
    assert hasattr(ReflectionAnalyzer(), "enrich")


def test_reflection_analyzer_alone_emits_no_extras() -> None:
    """ReflectionAnalyzer 단독으로도 Spring 전용 entity 를 새로 만들지 않아야 한다."""
    src = """
package com.x;
public class R {
    public void run() { Class.forName("com.x.A"); }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("R.java"), src)
    kinds = {e.kind for e in result.entities}
    assert EntityKinds.SPRING_BEAN not in kinds
    assert EntityKinds.SCHEDULED_TASK not in kinds
    assert EntityKinds.HTTP_ENDPOINT not in kinds
    assert EntityKinds.ASPECT not in kinds


# ---------------------------------------------------------------------------
# OD-11-B7-0 : arg_kind taxonomy
#   - literal  : "com.x.Foo"
#   - variable : identifier reference (param / field / local)
#   - concat   : "prefix." + suffix  (binary_expression)
#   - type     : Foo.class           (class_literal)
#   - other    : everything else (method call, ternary, cast, null ...)
# ---------------------------------------------------------------------------
def test_arg_kind_literal_class_forname() -> None:
    src = """
package com.x;
public class L {
    public void go() throws Exception {
        Class.forName("com.x.A");
    }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("L.java"), src)
    method = next(
        e for e in result.entities
        if e.kind == EntityKinds.METHOD and e.qualified_name == "com.x.L.go"
    )
    calls = _calls(method)
    assert len(calls) == 1
    assert calls[0]["arg"] == "com.x.A"
    assert calls[0]["arg_kind"] == "literal"


def test_arg_kind_variable_get_bean() -> None:
    src = """
package com.x;
public class B {
    public Object svc(String shipperName) {
        return ctx.getBean(shipperName);
    }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("B.java"), src)
    method = next(
        e for e in result.entities
        if e.kind == EntityKinds.METHOD and e.qualified_name == "com.x.B.svc"
    )
    calls = _calls(method)
    assert len(calls) == 1
    assert calls[0]["api"] == "getBean"
    assert calls[0]["arg"] == "shipperName"
    assert calls[0]["arg_kind"] == "variable"


def test_arg_kind_concat_class_forname() -> None:
    src = """
package com.x;
public class L {
    public void load(String suffix) throws Exception {
        Class.forName("com.acme." + suffix);
    }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("L.java"), src)
    method = next(
        e for e in result.entities
        if e.kind == EntityKinds.METHOD and e.qualified_name == "com.x.L.load"
    )
    calls = _calls(method)
    assert len(calls) == 1
    assert calls[0]["api"] == "Class.forName"
    assert calls[0]["arg_kind"] == "concat"
    # source text must include the concat operator and the prefix literal
    assert "com.acme." in calls[0]["arg"]
    assert "+" in calls[0]["arg"]
    assert "suffix" in calls[0]["arg"]


def test_arg_kind_other_method_call_arg() -> None:
    src = """
package com.x;
public class B {
    public Object svc() {
        return ctx.getBean(resolveName());
    }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("B.java"), src)
    method = next(
        e for e in result.entities
        if e.kind == EntityKinds.METHOD and e.qualified_name == "com.x.B.svc"
    )
    calls = _calls(method)
    assert len(calls) == 1
    assert calls[0]["api"] == "getBean"
    assert calls[0]["arg_kind"] == "other"


# ---------------------------------------------------------------------------
# Regression : literal-arg tests must also carry arg_kind == "literal"
# ---------------------------------------------------------------------------
def test_literal_arg_tests_carry_arg_kind_literal() -> None:
    src = """
package com.x;
public class R {
    public void run() throws Exception {
        Class.forName("com.x.A");
        ctx.getBean("orderService");
    }
}
"""
    parser = JavaParser(spring_analyzers=[ReflectionAnalyzer()])
    result = parser.parse_file(Path("R.java"), src)
    method = next(
        e for e in result.entities
        if e.kind == EntityKinds.METHOD and e.qualified_name == "com.x.R.run"
    )
    calls = _calls(method)
    assert len(calls) == 2
    for c in calls:
        assert c["arg_kind"] == "literal"


# ---------------------------------------------------------------------------
# Empty / tree=None edge cases
# ---------------------------------------------------------------------------
def test_enrich_with_none_tree_is_safe() -> None:
    a = ReflectionAnalyzer()
    entities, relations = a.enrich([], [], None, None)
    assert entities == []
    assert relations == []
