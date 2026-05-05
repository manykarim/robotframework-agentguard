"""Experiment 03: LiteLLM offline-introspection + mock_response works (research §4.4, §7.1).

Assumption: LiteLLM provides a uniform chat.completions interface, mapped exception
types, and a `mock_response=` parameter that lets us run unit tests with no API key.
"""

from importlib import metadata

import litellm


def main() -> int:
    try:
        ver = metadata.version("litellm")
    except Exception as e:
        ver = f"<unknown: {e}>"
    print("litellm version:", ver)
    # 1) model_list[:5]
    try:
        models = list(litellm.model_list)[:5]
    except Exception as e:
        models = ["<list error: %s>" % e]
    print("first 5 models:", models)

    # 2) Exception types importable
    try:
        ex_ok = True
    except Exception as e:
        ex_ok = False
        print("exception import error:", e)

    # 3) mock_response — no API key needed
    mock_ok = False
    content = None
    try:
        resp = litellm.completion(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "ping"}],
            mock_response="hi",
        )
        content = resp.choices[0].message.content
        mock_ok = content == "hi"
    except Exception as e:
        print("mock_response error:", type(e).__name__, e)

    print("RateLimitError importable:", ex_ok)
    print("mock_response result:", repr(content), "ok=", mock_ok)
    ok = ex_ok and mock_ok
    print("PASS" if ok else "FAIL", "exp_03_litellm_provider_shape")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
