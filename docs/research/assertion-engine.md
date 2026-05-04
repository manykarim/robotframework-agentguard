# AssertionEngine — Research Brief for AgentGuard Integration

**Audience:** ADR / DDD / proposal authors deciding whether and how to consume `robotframework-assertion-engine` in `robotframework-agentguard`. **Status:** Facts only, no design recommendations. **Sources:** `MarketSquare/AssertionEngine@main` and `MarketSquare/robotframework-browser@main`, fetched 2026-04-29.

> Naming: the **PyPI distribution** is `robotframework-assertion-engine` (current version **4.0.0**); the **import name** is `assertionengine`. "AssertionEngine" in Browser docs and the AgentGuard prompt refers to the same artifact.

---

## 1. AssertionEngine internals

### 1.1 Package layout (current `main`)

The shipping package contains four Python modules — there is no `assertion_operator.py` and no `formatter.py`:

```
src/assertionengine/
├── __init__.py              # public re-exports
├── assertion_engine.py      # AssertionOperator enum + verify_* functions
├── assertion_formatter.py   # FormatRules dict + Formatter ABC
├── type_converter.py        # is_truthy / type_converter helpers
└── py.typed
```

Source: `https://github.com/MarketSquare/AssertionEngine/tree/main/src/assertionengine`

### 1.2 Public surface — exact `__init__.py`

```python
# src/assertionengine/__init__.py
from .assertion_engine import (
    AssertionOperator, bool_verify_assertion, dict_verify_assertion,
    flag_verify_assertion, float_str_verify_assertion, int_dict_verify_assertion,
    int_str_verify_assertion, list_verify_assertion, verify_assertion,
)
from .assertion_formatter import Formatter

__all__ = ["AssertionOperator", "Formatter",
    "bool_verify_assertion", "dict_verify_assertion", "flag_verify_assertion",
    "float_str_verify_assertion", "int_dict_verify_assertion",
    "int_str_verify_assertion", "list_verify_assertion", "verify_assertion"]
```

Note that `FormatRules` (the value-transform dict) is **not** in `__all__`; Browser Library reaches into `assertionengine.assertion_formatter` to import it directly (see §2.3).
Source: `https://github.com/MarketSquare/AssertionEngine/blob/main/src/assertionengine/__init__.py`

### 1.3 `AssertionOperator` enum — verbatim definition

`AssertionOperator` is built **functionally** with `Enum(name, members_dict)` — not as a class with members. Every key in the dict becomes an enum **member name**; identical values mean those members are aliases of one another (Python `Enum` deduplicates by value, so `AssertionOperator["equal"] is AssertionOperator["=="]`).

```python
# src/assertionengine/assertion_engine.py:27-57
AssertionOperator = Enum(
    "AssertionOperator",
    {
        "equal": "==",                  "equals": "==",                "==": "==",
        "should be": "==",
        "inequal": "!=",                "!=": "!=",                    "should not be": "!=",
        "less than": "<",               "<": "<",
        "greater than": ">",            ">": ">",
        "<=": "<=",                     ">=": ">=",
        "contains": "*=",               "not contains": "not contains", "*=": "*=",
        "starts": "^=",                 "^=": "^=",                    "should start with": "^=",
        "ends": "$=",                   "should end with": "$=",       "$=": "$=",
        "matches": "$",
        "validate": "validate",
        "then": "then",                 "evaluate": "then",
    },
)
```

**Canonical operator count: 13 distinct values** (`==`, `!=`, `<`, `>`, `<=`, `>=`, `*=`, `not contains`, `^=`, `$=`, `$` (matches), `validate`, `then`) reached via **27 alias keys**.
Source: `https://github.com/MarketSquare/AssertionEngine/blob/main/src/assertionengine/assertion_engine.py#L27-L57`

> Pitfall: `matches` has **enum value `"$"`** (a single dollar sign), not `"matches"`. This is unique among the operators and is internal-only; users always reference it by name.

### 1.4 Three derived operator sets — verbatim

```python
# src/assertionengine/assertion_engine.py:89-109
NumericalOperators = [
    AssertionOperator["=="], AssertionOperator["!="],
    AssertionOperator[">="], AssertionOperator[">"],
    AssertionOperator["<="], AssertionOperator["<"],
]
SequenceOperators = [
    AssertionOperator["*="], AssertionOperator["validate"], AssertionOperator["then"],
    AssertionOperator["=="], AssertionOperator["!="],
]
EvaluationOperators = [
    AssertionOperator["validate"], AssertionOperator["then"],
]
```

These gate which operators are accepted by the typed `*_verify_assertion` helpers (`int_str_verify_assertion`, `list_verify_assertion`, etc.).

### 1.5 Operator handler table — what each operator actually does

```python
# src/assertionengine/assertion_engine.py:111-133
handlers = {
    AssertionOperator["=="]:           (lambda a, b: a == b,                            "should be"),
    AssertionOperator["!="]:           (lambda a, b: a != b,                            "should not be"),
    AssertionOperator["<"]:            (lambda a, b: a < b,                             "should be less than"),
    AssertionOperator[">"]:            (lambda a, b: a > b,                             "should be greater than"),
    AssertionOperator["<="]:           (lambda a, b: a <= b,                            "should be less than or equal"),
    AssertionOperator[">="]:           (lambda a, b: a >= b,                            "should be greater than or equal"),
    AssertionOperator["*="]:           (lambda a, b: b in a,                            "should contain"),
    AssertionOperator["not contains"]: (lambda a, b: b not in a,                        "should not contain"),
    AssertionOperator["matches"]:      (lambda a, b: re.search(b, a),                   "should match"),
    AssertionOperator["^="]:           (lambda a, b: re.search(f"^{re.escape(b)}", a),  "should start with"),
    AssertionOperator["$="]:           (lambda a, b: re.search(f"{re.escape(b)}$", a),  "should end with"),
    AssertionOperator["validate"]:     (lambda a, b: BuiltIn().evaluate(b, namespace={"value": a}),
                                                                                        "should validate to true with"),
}
# `then` (alias `evaluate`) is handled inline in verify_assertion — it returns the evaluation, not a bool.
```

Three observations from the table:
1. **`matches` uses `re.search`, not `re.fullmatch`.** A pattern like `"foo"` matches anywhere in the value.
2. **`^=` and `$=` are anchored regex with `re.escape` on the expected.** They are **literal** prefix/suffix tests, not regex, despite being implemented via `re.search`.
3. **`validate` and `then` (`evaluate`) call `BuiltIn().evaluate(...)` — Robot Framework's `Evaluate` keyword — which is a Python `eval()`** with `value` injected into the namespace. See §6.

Source: `https://github.com/MarketSquare/AssertionEngine/blob/main/src/assertionengine/assertion_engine.py#L111-L133`

### 1.6 `verify_assertion` — the actual signature

```python
# src/assertionengine/assertion_engine.py:166-193
def verify_assertion(
    value: T,
    operator: AssertionOperator | None,
    expected: Any,
    message: str = "",
    custom_message: str | None = None,
    formatters: list | None = None,        # NB: list, not single Formatter
) -> Any:
    if operator is None and expected:
        raise ValueError("Invalid validation parameters. Assertion operator is mandatory when specifying expected value.")
    if operator is None:
        return value
    expected = apply_to_expected(expected, formatters)
    value = apply_formatters(value, formatters)
    if operator is AssertionOperator["then"]:
        return cast(T, BuiltIn().evaluate(expected, namespace={"value": value}))
    handler = handlers.get(operator)
    filler = " " if message else ""
    if handler is None:
        raise RuntimeError(f"{message}{filler}`{operator}` is not a valid assertion operator")
    validator, text = handler
    if not validator(value, expected):
        raise_error(custom_message, expected, filler, message, text, value)
    return value
```

**Important deltas vs. the original AgentGuard prompt:** (1) the 4th positional is `message: str = ""`, **not** `prefix_message`; (2) the 6th positional is `formatters: list | None = None` — a **list of callables applied in order**, **not** a single `Formatter` instance.

### 1.7 Typed helpers — coercion behaviour

| Helper | Coerces `expected` to | Allowed operators |
|---|---|---|
| `int_str_verify_assertion` | `int(float(expected))` for numerics, `str(expected)` for `validate`/`then` | `NumericalOperators ∪ {validate, then}` (anything else → `ValueError`) |
| `float_str_verify_assertion` | `float(expected)` for numerics, `str(expected)` for `validate`/`then` | same |
| `bool_verify_assertion` | `is_truthy(expected)` against `{FALSE, NO, OFF, 0, UNCHECKED, NONE, ""}` | only `==` and `!=` |
| `list_verify_assertion` | sorts both sides for `==`/`!=`; for `contains` (`*=`) checks `all(item in value for item in expected)` via `BuiltIn().evaluate`; unwraps `expected[0]` for `validate`/`then` | `SequenceOperators` only |
| `dict_verify_assertion` | passes through | `SequenceOperators` only |
| `int_dict_verify_assertion` | `ast.literal_eval(expected)` for sequence ops, per-key `verify_assertion` for numerics | `NumericalOperators ∪ SequenceOperators` |
| `flag_verify_assertion` | converts `IntFlag`/`Flag` → set of member names; uses `set_handlers` (`==`, `!=`, `*=`, `not contains`) | `==`, `!=`, `*=`, `not contains`, `validate`, `then`; raises `TypeError` if value not a `Flag` |

Source: `https://github.com/MarketSquare/AssertionEngine/blob/main/src/assertionengine/assertion_engine.py#L275-L425`

### 1.8 `Formatter` ABC and `FormatRules` — exact contents

The `Formatter` ABC is **not** the value-transform mechanism. The value transforms live in a module-level `FormatRules` dict; the ABC is a **per-keyword formatter registry interface** that callers (e.g. Browser Library) implement to remember which rules apply to which keyword.

```python
# src/assertionengine/assertion_formatter.py
import re
from abc import ABC, abstractmethod

def _strip(value: str) -> str:             return value.strip()
def _normalize_spaces(value: str) -> str:  return re.sub(r"\s+", " ", value)
def _apply_to_expected(value: str) -> str: return value           # marker, not transform
def _case_insensitive(value: str) -> str:  return value.lower()

FormatRules = {
    "normalize spaces":  _normalize_spaces,    "strip":             _strip,
    "apply to expected": _apply_to_expected,   "case insensitive":  _case_insensitive,
}

class Formatter(ABC):
    @abstractmethod
    def get_formatter(self, keyword): ...
    @abstractmethod
    def set_formatter(self, keyword, formatter): ...
    def normalize_keyword(self, name: str):
        return name.lower().replace(" ", "_")
    def formatters_to_method(self, kw_formatter: list) -> list:
        return [FormatRules[formatter.lower()] for formatter in kw_formatter]
```

The `_apply_to_expected` function is a **sentinel** — `apply_to_expected()` in `assertion_engine.py` (lines 157-163) iterates the formatters list and only applies them to the expected value if a formatter named `_apply_to_expected` is present.
Source: `https://github.com/MarketSquare/AssertionEngine/blob/main/src/assertionengine/assertion_formatter.py`

### 1.9 What is **not** in AssertionEngine

- **No `with_assertion_polling` decorator.** That decorator lives in Browser Library, not AssertionEngine. AssertionEngine itself is purely synchronous and stateless beyond the optional `BuiltIn().evaluate` call.
- **No retry or timeout machinery.**
- **No formatter scope / suite / global lifecycle.** Browser Library implements all of that on top.

---

## 2. Browser Library integration pattern

### 2.1 Dependency pin

```toml
# robotframework-browser/pyproject.toml:16
"robotframework-assertion-engine >= 4.0.0, < 5.0.0",
```

Browser Library version pinning this dep: `robotframework-browser == 19.14.2` (also the `requires-python = ">= 3.10"` constraint matches AssertionEngine).
Source: `https://github.com/MarketSquare/robotframework-browser/blob/main/pyproject.toml`

### 2.2 Public re-exports — Browser does not re-export

Browser Library does **not** wrap or re-export `AssertionOperator`. Every keyword module imports directly from `assertionengine`:

```python
# Browser/keywords/getters.py:21-31
from assertionengine import (
    AssertionOperator,
    bool_verify_assertion, dict_verify_assertion, flag_verify_assertion,
    float_str_verify_assertion, int_dict_verify_assertion, int_str_verify_assertion,
    list_verify_assertion, verify_assertion,
)
```

The `@keyword` decorator picks up `AssertionOperator` directly from the type annotation; users pass plain strings (`"=="`, `"contains"`, etc.) which Robot Framework's argument converter coerces to enum members.
Source: `https://github.com/MarketSquare/robotframework-browser/blob/main/Browser/keywords/getters.py#L21-L31`

### 2.3 Polling decorator — verbatim

Browser owns the polling logic in `Browser/assertion_engine.py` (87 lines total). It is the only place AssertionEngine semantics are wrapped with retry behaviour:

```python
# Browser/assertion_engine.py:14-87
import time
from types import UnionType
from typing import get_args, get_origin

import wrapt
from assertionengine import AssertionOperator
from .utils import logger

def assertion_operator_is_set(wrapped, args, kwargs):
    assertion_operator = None
    assertion_op_name = None
    assertion_op_index = None
    for index, (_arg, typ) in enumerate(wrapped.__annotations__.items()):
        if get_origin(typ) is UnionType and AssertionOperator in get_args(typ):
            assertion_op_index = index
            break
        if typ is AssertionOperator:
            assertion_op_index = index
            break
    if assertion_op_index is not None:
        if len(args) > assertion_op_index:
            assertion_operator = args[assertion_op_index]
        elif assertion_op_name in kwargs:        # NB: assertion_op_name is always None — see §6
            assertion_operator = kwargs[assertion_op_name]
    return assertion_operator

@wrapt.decorator
def with_assertion_polling(wrapped, instance, args, kwargs):
    start = time.time()
    timeout = instance.timeout / 1000
    retry_assertions_until = instance.retry_assertions_for / 1000
    retries_start: float | None = None
    last_error: AssertionError | None = None
    tries = 1
    try:
        logger.stash_this_thread()
        while True:
            if retries_start is not None:
                elapsed = time.time() - start
                elapsed_retries = time.time() - retries_start
                if elapsed >= timeout or elapsed_retries >= retry_assertions_until:
                    raise last_error  # type: ignore[misc]
            try:
                return wrapped(*args, **kwargs)
            except AssertionError as e:
                last_error = e
                if retries_start is None:
                    retries_start = time.time()
                elapsed = time.time() - start
                elapsed_retries = time.time() - retries_start
                if elapsed >= timeout or elapsed_retries >= retry_assertions_until:
                    raise e
                tries += 1
                if timeout - elapsed > 0.01:
                    time.sleep(0.01)
                logger.clear_thread_stash()
    finally:
        logger.flush_and_delete_thread_stash()
        if retry_assertions_until and assertion_operator_is_set(wrapped, args, kwargs):
            now = time.time()
            logger.debug(
                f"Assertion polling statistics:\n"
                f"First element asserted in: {(retries_start or now) - start} seconds\n"
                f"Total tries: {tries}\n"
                f"Elapsed time in retries {now - (retries_start or now)} seconds"
            )

def assertion_formatter_used(func):
    func.assertion_formatter_used = True
    return func
```

Mechanism in plain words:
1. Reads two instance attributes: `instance.timeout` and `instance.retry_assertions_for` (both ms).
2. Calls the wrapped keyword. If it raises `AssertionError`, sleep ~10 ms and retry **the entire keyword**, including the underlying RPC/IO.
3. Stops when **either** wall-clock `timeout` or accumulated retry time `retry_assertions_for` is exceeded.
4. Re-raises the **last** `AssertionError`.
5. `logger.stash_this_thread()` swallows log lines from intermediate failures so only the final attempt's logs reach Robot Framework's report.

Source: `https://github.com/MarketSquare/robotframework-browser/blob/main/Browser/assertion_engine.py`

### 2.4 Per-keyword formatter registry — `Set Assertion Formatter`

Browser subclasses the `Formatter` ABC in `Browser/keywords/assertion_formatter.py` (123 lines). Key shape:

```python
# Browser/keywords/assertion_formatter.py (excerpt)
from assertionengine.assertion_formatter import FormatRules, Formatter as ASFormatter

class Formatter(ASFormatter, LibraryComponent):
    def set_assertion_formatter(self, keyword=None, *formatters,
                                scope: Scope = Scope.Global):
        if keyword is None: return self._clear_all_formatters()
        kw = keyword.name
        stack = self.assertion_formatter_stack.get()
        old = self._convert_scope_to_strings(stack.get(kw, []))
        stack[kw] = list(self.get_formatter_functions(formatters))
        self.assertion_formatter_stack.set(stack, scope)
        return {keyword.name: old}

    def get_formatter_functions(self, formatters):
        for f in formatters:
            if callable(f):                                           yield f                              # lambdas
            elif isinstance(f, FormatingRules):                       yield FormatRules[f.name]
            elif isinstance(f, str) and f.lower() in FormatRules:     yield FormatRules[f.lower()]
            else: raise ValueError(...)

    def get_formatter(self, keyword: str) -> list:
        return self.assertion_formatter_stack.get().get(keyword, [])

    def set_formatter(self, keyword, formatter): pass  # ABC requires; intentional no-op
```

Three load-bearing details:
1. The **per-keyword** registry is a `Scope`-stacked dict (`Global`/`Suite`/`Test`). Browser provides this; AssertionEngine does not.
2. Lambda formatters are accepted directly (the `FormatRules` keys are only one option).
3. Each getter calls `self.get_assertion_formatter("Get Text")` and passes the resulting **list of callables** as the 6th positional argument to `verify_assertion`.

Source: `https://github.com/MarketSquare/robotframework-browser/blob/main/Browser/keywords/assertion_formatter.py`

### 2.5 Canonical getter pattern

```python
# Browser/keywords/getters.py:222-266 (Get Text)
@keyword(tags=("Getter", "Assertion", "PageContent"))
@with_assertion_polling
@assertion_formatter_used
def get_text(self, selector: str,
             assertion_operator: AssertionOperator | None = None,
             assertion_expected: Any | None = None,
             message: str | None = None) -> str:
    ...
    response = self._get_text(selector)
    formatter = self.get_assertion_formatter("Get Text")
    return verify_assertion(
        response.body, assertion_operator, assertion_expected,
        "Text", message, formatter,
    )
```

Three decorators stack outside-in: `@keyword` (Robot exposure) → `@with_assertion_polling` (retry) → `@assertion_formatter_used` (sets `func.assertion_formatter_used = True`, used by stub generation / docs). The keyword body: fetch value, look up registered formatters, delegate to `verify_assertion`.
Source: `https://github.com/MarketSquare/robotframework-browser/blob/main/Browser/keywords/getters.py#L222-L266`

---

## 3. Operator surface — canonical reference table

| Operator string | Enum member name (one of) | Enum value | Aliases (alternate names of same member) | Coercion / behavior | Common use case |
|---|---|---|---|---|---|
| `==` | `==` | `==` | `equal`, `equals`, `should be` | `a == b` (Python equality) | Exact match |
| `!=` | `!=` | `!=` | `inequal`, `should not be` | `a != b` | Exact mismatch |
| `<` | `<` | `<` | `less than` | `a < b` (lexicographic for strings) | Numeric / ordering |
| `<=` | `<=` | `<=` | (none) | `a <= b` | Numeric / ordering |
| `>` | `>` | `>` | `greater than` | `a > b` | Numeric / ordering |
| `>=` | `>=` | `>=` | (none) | `a >= b` | Numeric / ordering |
| `*=` | `*=` | `*=` | `contains` | `b in a` (substring / membership) | Substring, list membership |
| `not contains` | `not contains` | `not contains` | (none) | `b not in a` | Substring absence |
| `^=` | `^=` | `^=` | `starts`, `should start with` | `re.search(f"^{re.escape(b)}", a)` — **literal** prefix | Prefix check |
| `$=` | `$=` | `$=` | `ends`, `should end with` | `re.search(f"{re.escape(b)}$", a)` — **literal** suffix | Suffix check |
| `matches` | `matches` | `$` | (none) | `re.search(b, a)` — **partial** regex match | Regex (anywhere in value) |
| `validate` | `validate` | `validate` | (none) | `BuiltIn().evaluate(b, namespace={"value": a})` returns truthy | Arbitrary Python predicate |
| `evaluate` | `then` | `then` | `evaluate` | `BuiltIn().evaluate(b, namespace={"value": a})` and **returns** the result | Transform/extract from the value |

Per-helper restrictions are listed in §1.7. AgentGuard-relevant gaps and quirks:

- **`>=` / `<=` lack a string alias** ("greater than or equal" is not in the enum). Documented in the enum docstring as having no alternative.
- **String-vs-int sensitivity:** `verify_assertion` does **no** coercion in the generic path. `verify_assertion("9", AssertionOperator[">="], "10")` returns `True` because `"9" >= "10"` is `True` lexicographically. Use `int_str_verify_assertion` / `float_str_verify_assertion` to force numeric coercion.
- **`contains` for sets is a different lambda.** `flag_verify_assertion` uses `set_handlers` where `*=` becomes `b.issubset(a)` — different semantics from substring `*=`.
- **`matches` is `re.search`, not `re.fullmatch`.** Pattern `"\d+"` matches `"abc 42 def"`. To force full-string match, callers must anchor: `^\d+$`.
- AssertionEngine and Browser docs are consistent — there are **no operators in one but not the other**. Every operator above is reachable from a Browser keyword call site.

---

## 4. Polling + formatting integration

### 4.1 How polling actually works

`with_assertion_polling` (§2.3) wraps the **whole keyword**, not just the assertion comparison. On each retry the keyword:
1. Re-issues the underlying gRPC / Playwright call (Browser pays a network round-trip per retry).
2. Re-runs the formatter pipeline.
3. Re-invokes `verify_assertion`.

It catches **only** `AssertionError`. Any other exception (network failure, `RuntimeError` for unsupported operator, `ValueError` from numeric coercion) escapes immediately. The retry loop sleeps a **fixed 10 ms** between attempts; there is no backoff. Two timers gate exit:

- `instance.timeout` — Browser's library-wide default action timeout.
- `instance.retry_assertions_for` — the maximum *cumulative* retry budget once the first failure occurs (defaults to 0 in Browser, meaning "no polling" unless the user opts in via `Set Retry Assertions For`).

The decorator's `finally` block emits a `logger.debug` summary with `tries` and elapsed time only if `retry_assertions_for` was non-zero **and** an assertion operator was actually set on the call (via `assertion_operator_is_set`).

### 4.2 Implications for AgentGuard

AgentGuard keywords mostly evaluate **one-shot statistics over a captured trajectory** (Tool Hit Rate, Step Count, Plan Adherence, Loop Detection, etc.). Polling is a poor fit for several of them:

| AgentGuard keyword class | Pollable in AssertionEngine sense? | Reasoning |
|---|---|---|
| LLM-touching judges (e.g. `Verify Response Quality`) | **No** | Each retry re-invokes the LLM at full cost; non-deterministic; latency is seconds. Polling for an `AssertionError` would multiply spend. |
| Trajectory statistics over closed runs (Tool Hit Rate, Loop Detection) | **No** | Input is immutable after the agent finishes. Retrying yields identical results. |
| Live-stream observers during a long agent run (e.g. periodic Tool Hit Rate sampled from a buffered log) | **Possibly yes** | If the value source is monotonic and incremental, polling can wait for a threshold to be reached. But this requires the keyword to *re-read* the source each call — not just re-evaluate a cached value. |
| Statistical baseline checks (e.g. confidence intervals from N samples) | **No, but for a different reason** | Each retry would need to **redraw** N samples. With N≥10, retries multiply already-high cost; flaky baselines should fail loudly, not retry. |

The honest framing for the proposal authors: **Browser-style polling is opt-in and only meaningful when the underlying observable can change between calls.** Many AgentGuard assertions cannot.

### 4.3 Formatter portability

Of the four `FormatRules` shipped:
- `strip`, `normalize spaces`, `case insensitive` — directly applicable to AgentGuard's text-comparing assertions (e.g. final-answer matching).
- `apply to expected` — useful when an expected value is supplied as a heredoc / fixture string; mirrors transforms onto the expected side.

Custom lambda formatters (Browser supports them, §2.4) would let AgentGuard plug in domain-specific transforms (e.g. "strip ANSI", "drop tool-call IDs") without subclassing.

---

## 5. PyPI + dependency footprint

```bash
$ curl -s https://pypi.org/pypi/robotframework-assertion-engine/json
```

| Field | Value |
|---|---|
| PyPI distribution | `robotframework-assertion-engine` |
| Latest version | **4.0.0** (current `main`, released for RF 6.1.1+) |
| Recent versions | 3.1.2, 3.1.3, 3.2.0, 3.5.0, 4.0.0 |
| `requires_python` | `>=3.10` |
| `requires_dist` | `robotframework>=6.1.1`, `robotframework-pythonlibcore>=3.0.0` |
| License | Apache-2.0 |

**Transitive dependency closure (declared):**
- `robotframework` (already a peer dep for any RF library — zero added cost for AgentGuard).
- `robotframework-pythonlibcore` (~50 KB, pure Python; pulled in by most modern RF libraries already).

**Import-time impact (worst case for AgentGuard):**
- `assertion_engine.py` imports `robot.libraries.BuiltIn` lazily-acceptable: the module-level imports are only `ast`, `re`, `enum`, `typing`, `collections.abc`, and `robot.libraries.BuiltIn`. The latter triggers Robot Framework's BuiltIn library load (~10-30 ms cold) but Robot is already loaded in any AgentGuard runtime path.
- `assertion_formatter.py` imports only `re` and `abc`.
- Net new code: **~500 lines of Python**, no C extensions, no I/O at import.

Browser pin: `robotframework-assertion-engine >= 4.0.0, < 5.0.0`. AgentGuard adopting the same range yields zero version conflict for suites that load both Browser and AgentGuard.

Sources: `https://pypi.org/pypi/robotframework-assertion-engine/json`, `https://github.com/MarketSquare/robotframework-browser/blob/main/pyproject.toml#L16`

---

## 6. Three load-bearing observations for the proposal authors

1. **`validate` and `then`/`evaluate` are `BuiltIn().evaluate(...)` — Python `eval()` in disguise.** The expected value is a string of Python source executed with `value` injected into the namespace. Robot Framework's `Evaluate` allows arbitrary expressions and supports `modules=` for imports. If AgentGuard surfaces these operators directly to `.robot` files written by less-trusted authors (or generated by an LLM), it inherits an arbitrary-code-execution surface. A whitelist or operator-disable mechanism may be required at the AgentGuard boundary. Source: `assertion_engine.py:129-130, 182-183`.

2. **`with_assertion_polling` is a Browser-Library invention, not part of AssertionEngine, and re-runs the entire wrapped keyword on every retry.** Adopting the same polling pattern for AgentGuard's LLM-judge or N-sample statistical keywords would multiply both latency and API spend by `tries`. Polling only makes sense for keywords whose value source is (a) cheap to re-read, (b) monotonic or eventually consistent, and (c) failure-mode is "not yet" rather than "wrong". The proposal must explicitly opt **in or out** of polling on a per-keyword basis. Source: `Browser/assertion_engine.py:43-82`.

3. **The `verify_assertion` signature in the original AgentGuard prompt is wrong in two material places: the 4th positional is `message` (not `prefix_message`) and the 6th positional is `formatters: list` (not a single `formatter`).** Additionally, `matches` uses `re.search` (substring regex, not full-match), `^=`/`$=` apply `re.escape` to the expected (literal prefix/suffix, not regex), and the `contains` semantics differ between scalar values (`b in a`), sets (`b.issubset(a)`), and lists (per-element `all(item in value for item in expected)`). Any AgentGuard wrapper must fix these signatures and document the `re.search` behavior, otherwise Robot suites authored against the prompt will fail in confusing ways. Sources: `assertion_engine.py:120-128, 166-173, 342-382`.
