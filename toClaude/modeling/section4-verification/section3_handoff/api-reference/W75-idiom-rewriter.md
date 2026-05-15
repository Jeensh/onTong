# W75 · Java Idiom Rewriter — String / Collection / Optional / Math

> **What:** 50+ Java stdlib idiom 을 Python 대응 표현으로 변환.
>
> **Why for Section 3:** Section 3 transpiler 는 `length()` / `charAt()` 정도만 명시. `Optional.isPresent()`, `Math.abs(x)`, `Map.containsKey(k)`, `List.size()` 등 production 에서 자주 보이는 idiom 은 그대로 emit 되어 AttributeError. W75 가 모두 자동 변환.

## 1. Import

```python
from backend.sim_v2.core.synthesizer.idiom_rewriter import (
    rewrite_method_invocation,    # public API — 직접 호출 가능
)
```

이 함수는 `JavaToPythonTranslator._translate_method_invocation` 안에서 자동 호출되므로, **별도 호출 불필요**. translator 만 import 하면 idiom rewrite 자동 적용.

## 2. 3 tier 매칭 로직

```
1. STATIC idiom   — receiver_src 가 class name (Math, String, Integer, Objects, Optional)
2. TYPED idiom    — receiver_type 이 known (String, List, Map, Set, Optional)
3. UNKNOWN idiom  — 무엇이든 안전한 idiom (length, charAt, substring, trim, ...)
```

매칭 안 되면 None 반환 → caller 가 default `receiver.method(args)` fallback.

## 3. 전체 idiom 리스트

### String (typed)
| Java | Python |
| --- | --- |
| `s.isEmpty()` | `(not s)` |
| `s.equals(o)` | `(s == o)` |
| `s.equalsIgnoreCase(o)` | `(s.lower() == o.lower())` |
| `s.contains(sub)` | `(sub in s)` |
| `s.indexOf(c)` / `lastIndexOf(c)` | `s.find(c)` / `s.rfind(c)` |
| `s.replace(a, b)` | `s.replace(a, b)` |
| `s.concat(o)` | `(s + o)` |
| `s.split(sep)` | `s.split(sep)` |

### String (unknown — safe even without type)
| Java | Python |
| --- | --- |
| `s.length()` | `len(s)` |
| `s.charAt(i)` | `s[i]` |
| `s.substring(a)` / `(a, b)` | `s[a:]` / `s[a:b]` |
| `s.startsWith(p)` / `endsWith(p)` | `s.startswith(p)` / `s.endswith(p)` |
| `s.toLowerCase()` / `toUpperCase()` | `s.lower()` / `s.upper()` |
| `s.trim()` | `s.strip()` |
| `s.isBlank()` | `(not (s or '').strip())` |
| `o.toString()` | `str(o)` |

### List / ArrayList / LinkedList / Vector (typed)
| Java | Python |
| --- | --- |
| `list.size()` | `len(list)` |
| `list.isEmpty()` | `(not list)` |
| `list.contains(x)` | `(x in list)` |
| `list.get(i)` | `list[i]` |
| `list.set(i, v)` | `list.__setitem__(i, v)` |
| `list.add(x)` | `list.append(x)` |
| `list.remove(x)` | `list.remove(x)` |
| `list.clear()` | `list.clear()` |
| `list.indexOf(x)` | `list.index(x)` |

### Map / HashMap / LinkedHashMap / TreeMap (typed)
| Java | Python |
| --- | --- |
| `map.size()` | `len(map)` |
| `map.isEmpty()` | `(not map)` |
| `map.containsKey(k)` | `(k in map)` |
| `map.containsValue(v)` | `(v in map.values())` |
| `map.get(k)` | `map.get(k)` |
| `map.getOrDefault(k, d)` | `map.get(k, d)` |
| `map.put(k, v)` | `map.__setitem__(k, v)` |
| `map.remove(k)` | `map.pop(k, None)` |
| `map.keySet() / values() / entrySet()` | `set(map.keys()) / map.values() / map.items()` |

### Set / HashSet / TreeSet (typed)
| Java | Python |
| --- | --- |
| `set.size()` | `len(set)` |
| `set.isEmpty()` | `(not set)` |
| `set.contains(x)` | `(x in set)` |
| `set.add(x)` | `set.add(x)` |
| `set.remove(x)` | `set.discard(x)` |

### Optional (typed)
| Java | Python |
| --- | --- |
| `opt.isPresent()` / `isEmpty()` | `(opt is not None)` / `(opt is None)` |
| `opt.get()` | `opt` |
| `opt.orElse(d)` | `(opt if opt is not None else d)` |
| `opt.orElseGet(supplier)` | `(opt if opt is not None else supplier())` |

### Math / Static
| Java | Python |
| --- | --- |
| `Math.abs(x)` | `abs(x)` |
| `Math.min(a, b)` / `max(a, b)` | `min(a, b)` / `max(a, b)` |
| `Math.pow(a, b)` | `(a ** b)` |
| `Math.round(x)` / `sqrt(x)` / `floor(x)` / `ceil(x)` | 각 대응 Python |
| `String.valueOf(o)` | `str(o)` |
| `Integer.parseInt(s)` / `Long.parseLong(s)` | `int(s)` |
| `Double.parseDouble(s)` / `Float.parseFloat(s)` | `float(s)` |
| `Boolean.parseBoolean(s)` | `(s.lower() == 'true')` |

### Objects (Java util)
| Java | Python |
| --- | --- |
| `Objects.isNull(x)` / `nonNull(x)` | `(x is None)` / `(x is not None)` |
| `Objects.equals(a, b)` | `(a == b)` |
| `Objects.requireNonNull(x)` | `x` |

### Optional factory
| Java | Python |
| --- | --- |
| `Optional.of(x)` / `ofNullable(x)` | `x` |
| `Optional.empty()` | `None` |

## 4. 통합 동작 — 직접 호출

```python
from backend.sim_v2.core.synthesizer.idiom_rewriter import rewrite_method_invocation

rewrite_method_invocation("name", "String", "isEmpty", [])
# → "(not name)"

rewrite_method_invocation("items", "List<String>", "size", [])
# → "len(items)"
# (generic 자동 strip — List<String> → List family)

rewrite_method_invocation("Math", None, "abs", ["-5"])
# → "abs(-5)"

rewrite_method_invocation("user", None, "getName", [])
# → None    (custom method — caller fallback)
```

## 5. JavaToPythonTranslator 와 자동 통합

`java_translator.py:578-647` 의 `_translate_method_invocation` 안에서 자동 호출:

```python
# (excerpt — line 645+)
idiom = rewrite_method_invocation(
    receiver_src, receiver_type, method_name, arg_strs,
)
if idiom is not None:
    return idiom

return f"{receiver_src}.{method_name}({', '.join(arg_strs)})"
```

Section 3 가 sim_v2 translator 를 호출하면 자동 적용. 별도 wiring 불필요.

## 6. 한계

- **Stream API 미구현** — `list.stream().filter(...).map(...).collect(...)` 등 Java 8 stream 은 W75 의 idiom 표에 없음. 다음 sprint 후보.
- **Builder pattern 미구현** — `new Foo.Builder().a(1).b(2).build()` 같은 fluent API.
- **`forEach` lambda** — Java 의 `list.forEach(x -> ...)` 는 java_translator 의 lambda 변환에 의존.

## 7. UC39 ATTRERROR 2건 vs UC40 결과

| 시점 | NAMERROR | SYNTAX | ATTRERROR |
| --- | --- | --- | --- |
| W75 적용 전 | 7 | 2 | 2 |
| W75 적용 후 | 9 (drilldown) | 2 | **0 ✓** |
| W74 stub 추가 후 (UC40) | 0 ✓ | 2 | 0 |

UC39 의 ATTRERROR 2건 (`'str' object has no attribute 'length'`) 이 W75 으로 정확히 close 됨.

## 8. 관련 파일

| 파일 | 역할 |
| --- | --- |
| `backend/sim_v2/core/synthesizer/idiom_rewriter.py` | 50+ idiom table + 3 tier matching |
| `backend/sim_v2/tests/core/synthesizer/test_w75_idiom_rewriter.py` | 69 unit test |
| `backend/sim_v2/core/synthesizer/java_translator.py:645` | 통합 후크 |
