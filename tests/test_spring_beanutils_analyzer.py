"""OD-11-B6-2 : Spring BeanUtilsAnalyzer — copyProperties / ModelMapper.map marker.

감지 대상:
  - Spring  `org.springframework.beans.BeanUtils.copyProperties(src, dst, ...ignore)`
  - Apache  `org.apache.commons.beanutils.BeanUtils.copyProperties(dst, src)` (인자 순서 반대!)
  - ModelMapper `org.modelmapper.ModelMapper.map(src, Dst.class)` 또는 `.map(src, dst)`
  - Static import (`import static ...BeanUtils.copyProperties` / `...BeanUtils.*`) 시 bare `copyProperties(...)` 호출도 감지

출력 포맷 (METHOD / CONSTRUCTOR entity 속성 marker):
  `beanutils_calls = [{library, src_type, dst_type, ignore, confidence, line}, ...]`

설계:
  - `analyze()` 는 Protocol 호환을 위해 `([], [])` 반환.
  - `enrich(entities, relations, tree, pkg_name)` post-pass 에서 AST 스캔 →
    method/constructor FQN 별 call 리스트 구축 → METHOD/CONSTRUCTOR entity 속성에 merge.
  - 실제 FIELD 교집합 → `PROPAGATES_TO` 승격은 B6-4 `CrossFileEnricher` 가 담당.
"""

from __future__ import annotations

from pathlib import Path

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.modeling.code_analysis.java_parser import JavaParser
from backend.modeling.code_analysis.parser_protocol import EntityKinds
from backend.modeling.code_analysis.spring import BeanUtilsAnalyzer

_LANG = Language(tsjava.language())


def _parse(src: str):
    p = Parser(_LANG)
    return p.parse(src.encode())


def _bean_calls(entity) -> list[dict]:
    val = entity.attributes.get("beanutils_calls")
    return val if isinstance(val, list) else []


def _method(result, fqn_suffix: str):
    for e in result.entities:
        if e.kind in (EntityKinds.METHOD, EntityKinds.CONSTRUCTOR) and e.qualified_name.endswith(fqn_suffix):
            return e
    return None


# ---------------------------------------------------------------------------
# analyze() is a no-op — no entities/relations
# ---------------------------------------------------------------------------
def test_beanutils_analyze_returns_empty() -> None:
    src = """
package com.x;
import org.springframework.beans.BeanUtils;
public class C {
    public void run(OrderReq src, OrderDto dst) {
        BeanUtils.copyProperties(src, dst);
    }
}
"""
    tree = _parse(src)
    a = BeanUtilsAnalyzer()
    entities, relations = a.analyze(tree=tree, content=src.encode(), file_path="C.java", pkg_name="com.x")
    assert entities == []
    assert relations == []


# ---------------------------------------------------------------------------
# Spring: (src, dst) with params
# ---------------------------------------------------------------------------
def test_spring_copyproperties_basic() -> None:
    src = """
package com.x;
import org.springframework.beans.BeanUtils;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;
public class Converter {
    public OrderDto convert(OrderReq src) {
        OrderDto dst = new OrderDto();
        BeanUtils.copyProperties(src, dst);
        return dst;
    }
}
"""
    parser = JavaParser(spring_analyzers=[BeanUtilsAnalyzer()])
    result = parser.parse_file(Path("Converter.java"), src)
    m = _method(result, ".Converter.convert")
    assert m is not None
    calls = _bean_calls(m)
    assert len(calls) == 1
    c = calls[0]
    assert c["library"] == "spring"
    assert c["src_type"] == "com.x.model.OrderReq"
    assert c["dst_type"] == "com.x.dto.OrderDto"
    assert c["confidence"] == 0.7
    assert c["ignore"] == []
    assert c["line"] >= 1


# ---------------------------------------------------------------------------
# Apache Commons: (dst, src) — reversed!
# ---------------------------------------------------------------------------
def test_apache_copyproperties_reverses_args() -> None:
    src = """
package com.x;
import org.apache.commons.beanutils.BeanUtils;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;
public class Converter {
    public void copy(OrderDto dst, OrderReq src) throws Exception {
        BeanUtils.copyProperties(dst, src);
    }
}
"""
    parser = JavaParser(spring_analyzers=[BeanUtilsAnalyzer()])
    result = parser.parse_file(Path("Converter.java"), src)
    m = _method(result, ".Converter.copy")
    assert m is not None
    calls = _bean_calls(m)
    assert len(calls) == 1
    c = calls[0]
    assert c["library"] == "apache"
    assert c["src_type"] == "com.x.model.OrderReq"
    assert c["dst_type"] == "com.x.dto.OrderDto"


# ---------------------------------------------------------------------------
# ModelMapper: .map(src, Dst.class) class literal form
# ---------------------------------------------------------------------------
def test_modelmapper_map_with_class_literal() -> None:
    src = """
package com.x;
import org.modelmapper.ModelMapper;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;
public class Converter {
    private final ModelMapper mm = new ModelMapper();
    public OrderDto convert(OrderReq src) {
        return mm.map(src, OrderDto.class);
    }
}
"""
    parser = JavaParser(spring_analyzers=[BeanUtilsAnalyzer()])
    result = parser.parse_file(Path("Converter.java"), src)
    m = _method(result, ".Converter.convert")
    assert m is not None
    calls = _bean_calls(m)
    assert len(calls) == 1
    c = calls[0]
    assert c["library"] == "modelmapper"
    assert c["src_type"] == "com.x.model.OrderReq"
    assert c["dst_type"] == "com.x.dto.OrderDto"


# ---------------------------------------------------------------------------
# ModelMapper: .map(src, dst) instance form (2nd arg is instance, not .class)
# ---------------------------------------------------------------------------
def test_modelmapper_map_with_instance_second_arg() -> None:
    src = """
package com.x;
import org.modelmapper.ModelMapper;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;
public class Converter {
    private final ModelMapper mm = new ModelMapper();
    public void fill(OrderReq src, OrderDto dst) {
        mm.map(src, dst);
    }
}
"""
    parser = JavaParser(spring_analyzers=[BeanUtilsAnalyzer()])
    result = parser.parse_file(Path("Converter.java"), src)
    m = _method(result, ".Converter.fill")
    assert m is not None
    calls = _bean_calls(m)
    assert len(calls) == 1
    c = calls[0]
    assert c["library"] == "modelmapper"
    assert c["src_type"] == "com.x.model.OrderReq"
    assert c["dst_type"] == "com.x.dto.OrderDto"


# ---------------------------------------------------------------------------
# Spring with ignore list (3rd+ args are string literal property names to skip)
# ---------------------------------------------------------------------------
def test_spring_copyproperties_with_ignore_list() -> None:
    src = """
package com.x;
import org.springframework.beans.BeanUtils;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;
public class Converter {
    public void fill(OrderReq src, OrderDto dst) {
        BeanUtils.copyProperties(src, dst, "password", "secret");
    }
}
"""
    parser = JavaParser(spring_analyzers=[BeanUtilsAnalyzer()])
    result = parser.parse_file(Path("Converter.java"), src)
    m = _method(result, ".Converter.fill")
    assert m is not None
    calls = _bean_calls(m)
    assert len(calls) == 1
    assert calls[0]["ignore"] == ["password", "secret"]


# ---------------------------------------------------------------------------
# No BeanUtils import → library=unknown, confidence=0.5
# ---------------------------------------------------------------------------
def test_unknown_library_without_import() -> None:
    src = """
package com.x;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;
public class Converter {
    public void fill(OrderReq src, OrderDto dst) {
        BeanUtils.copyProperties(src, dst);
    }
}
"""
    parser = JavaParser(spring_analyzers=[BeanUtilsAnalyzer()])
    result = parser.parse_file(Path("Converter.java"), src)
    m = _method(result, ".Converter.fill")
    assert m is not None
    calls = _bean_calls(m)
    assert len(calls) == 1
    c = calls[0]
    assert c["library"] == "unknown"
    assert c["confidence"] == 0.5


# ---------------------------------------------------------------------------
# Two calls in the same method — both captured in line order
# ---------------------------------------------------------------------------
def test_two_calls_in_same_method() -> None:
    src = """
package com.x;
import org.springframework.beans.BeanUtils;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;
import com.x.dto.SummaryDto;
public class Converter {
    public void fill(OrderReq src, OrderDto dst, SummaryDto sum) {
        BeanUtils.copyProperties(src, dst);
        BeanUtils.copyProperties(src, sum);
    }
}
"""
    parser = JavaParser(spring_analyzers=[BeanUtilsAnalyzer()])
    result = parser.parse_file(Path("Converter.java"), src)
    m = _method(result, ".Converter.fill")
    assert m is not None
    calls = _bean_calls(m)
    assert len(calls) == 2
    assert calls[0]["dst_type"] == "com.x.dto.OrderDto"
    assert calls[1]["dst_type"] == "com.x.dto.SummaryDto"
    assert calls[0]["line"] < calls[1]["line"]


# ---------------------------------------------------------------------------
# Different methods — scope isolation
# ---------------------------------------------------------------------------
def test_different_methods_scope_isolation() -> None:
    src = """
package com.x;
import org.springframework.beans.BeanUtils;
import com.x.model.OrderReq;
import com.x.model.PayReq;
import com.x.dto.OrderDto;
import com.x.dto.PayDto;
public class Converter {
    public void order(OrderReq src, OrderDto dst) {
        BeanUtils.copyProperties(src, dst);
    }
    public void pay(PayReq src, PayDto dst) {
        BeanUtils.copyProperties(src, dst);
    }
    public void untouched() {
        int x = 1;
    }
}
"""
    parser = JavaParser(spring_analyzers=[BeanUtilsAnalyzer()])
    result = parser.parse_file(Path("Converter.java"), src)
    order = _method(result, ".Converter.order")
    pay = _method(result, ".Converter.pay")
    untouched = _method(result, ".Converter.untouched")
    assert order is not None and pay is not None and untouched is not None
    oc = _bean_calls(order)
    pc = _bean_calls(pay)
    assert len(oc) == 1 and oc[0]["src_type"] == "com.x.model.OrderReq"
    assert len(pc) == 1 and pc[0]["src_type"] == "com.x.model.PayReq"
    assert "beanutils_calls" not in untouched.attributes


# ---------------------------------------------------------------------------
# Non-BeanUtils call → ignored
# ---------------------------------------------------------------------------
def test_non_beanutils_call_ignored() -> None:
    src = """
package com.x;
import com.x.service.Helper;
import com.x.model.OrderReq;
public class Converter {
    private final Helper helper = new Helper();
    public void run(OrderReq src) {
        helper.process(src);
        System.out.println("hi");
    }
}
"""
    parser = JavaParser(spring_analyzers=[BeanUtilsAnalyzer()])
    result = parser.parse_file(Path("Converter.java"), src)
    m = _method(result, ".Converter.run")
    assert m is not None
    assert "beanutils_calls" not in m.attributes


# ---------------------------------------------------------------------------
# Static import: bare `copyProperties(...)` should be detected (Spring variant)
# ---------------------------------------------------------------------------
def test_static_import_bare_copyproperties() -> None:
    src = """
package com.x;
import static org.springframework.beans.BeanUtils.copyProperties;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;
public class Converter {
    public void fill(OrderReq src, OrderDto dst) {
        copyProperties(src, dst);
    }
}
"""
    parser = JavaParser(spring_analyzers=[BeanUtilsAnalyzer()])
    result = parser.parse_file(Path("Converter.java"), src)
    m = _method(result, ".Converter.fill")
    assert m is not None
    calls = _bean_calls(m)
    assert len(calls) == 1
    assert calls[0]["library"] == "spring"


# ---------------------------------------------------------------------------
# Constructor body call — CONSTRUCTOR entity gets the marker
# ---------------------------------------------------------------------------
def test_constructor_body_call() -> None:
    src = """
package com.x;
import org.springframework.beans.BeanUtils;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;
public class Converter {
    private OrderDto dst;
    public Converter(OrderReq src) {
        this.dst = new OrderDto();
        BeanUtils.copyProperties(src, this.dst);
    }
}
"""
    parser = JavaParser(spring_analyzers=[BeanUtilsAnalyzer()])
    result = parser.parse_file(Path("Converter.java"), src)
    ctor = _method(result, ".Converter.Converter")
    assert ctor is not None
    calls = _bean_calls(ctor)
    assert len(calls) == 1
    assert calls[0]["src_type"] == "com.x.model.OrderReq"
    assert calls[0]["dst_type"] == "com.x.dto.OrderDto"


# ---------------------------------------------------------------------------
# Unresolved type keeps simple name (B6-4 will resolve via repo-level index)
# ---------------------------------------------------------------------------
def test_unresolved_type_keeps_simple_name() -> None:
    src = """
package com.x;
import org.springframework.beans.BeanUtils;
import com.x.dto.OrderDto;
public class Converter {
    public void fill(Unknown raw, OrderDto dst) {
        BeanUtils.copyProperties(raw, dst);
    }
}
"""
    parser = JavaParser(spring_analyzers=[BeanUtilsAnalyzer()])
    result = parser.parse_file(Path("Converter.java"), src)
    m = _method(result, ".Converter.fill")
    assert m is not None
    calls = _bean_calls(m)
    assert len(calls) == 1
    # Unknown import falls back to simple name — B6-4 resolves later
    assert calls[0]["src_type"] == "Unknown"
    assert calls[0]["dst_type"] == "com.x.dto.OrderDto"
