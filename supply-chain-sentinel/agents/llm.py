"""Tiny provider-agnostic LLM client (stdlib only). Providers: Groq (OpenAI-compatible) and Google Gemini.
Everything in the project treats the LLM as OPTIONAL: callers check settings()["configured"] and fall back.

.env keys:  LLM_PROVIDER=groq|gemini|auto   GROQ_API_KEY / GROQ_MODEL   GEMINI_API_KEY / GEMINI_MODEL
Self-test:  python -m agents.llm
"""
import json, os, re, time, urllib.error, urllib.request
from agents import config  # noqa: F401  (loads .env)

DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"       # llama-3.3-70b-versatile was retired by Groq on 2026-08-16
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"        # gemini-2.5-* models shut down on 2026-10-16


class LLMError(Exception):
    pass


def settings():
    provider = os.getenv("LLM_PROVIDER", "auto").strip().lower()
    groq, gem = os.getenv("GROQ_API_KEY"), (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    if provider in ("", "auto"):
        provider = "groq" if groq else "gemini" if gem else "none"
    if (provider == "groq" and not groq) or (provider == "gemini" and not gem):
        provider = "none"
    model = {"groq": os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL), "gemini": os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)}.get(provider)
    return {"provider": provider, "model": model, "configured": provider != "none"}


def label():
    s = settings()
    return f"{s['provider']}:{s['model']}" if s["configured"] else "rules/template (no LLM key)"


def _post(url, payload, headers, timeout):
    data = json.dumps(payload).encode()
    # a custom User-Agent matters: some APIs sit behind Cloudflare, which blocks the default Python one
    hdrs = {"Content-Type": "application/json", "User-Agent": "SupplyChainSentinel/1.0", **headers}
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:300]
            if e.code in (429, 500, 502, 503) and attempt == 0:
                time.sleep(1.5)
                continue
            raise LLMError(f"HTTP {e.code}: {body}")
        except Exception as e:
            if attempt == 0:
                time.sleep(0.8)
                continue
            raise LLMError(str(e))


def _clean(text):
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)   # some reasoning models leak this
    return text.strip()


def chat(system, user, json_mode=False, max_tokens=1200, temperature=0.2, timeout=25):
    s = settings()
    if not s["configured"]:
        raise LLMError("no LLM configured")
    if s["provider"] == "groq":
        payload = {"model": s["model"], "temperature": temperature, "max_tokens": max_tokens,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if "gpt-oss" in s["model"]:
            payload["reasoning_effort"] = "low"        # keep it fast; we only need short outputs
        out = _post("https://api.groq.com/openai/v1/chat/completions", payload,
                    {"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"}, timeout)
        try:
            return _clean(out["choices"][0]["message"]["content"])
        except Exception:
            raise LLMError(f"unexpected Groq response: {str(out)[:200]}")
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    cfg = {"temperature": temperature, "maxOutputTokens": max_tokens}
    if json_mode:
        cfg["responseMimeType"] = "application/json"
    payload = {"systemInstruction": {"parts": [{"text": system}]},
               "contents": [{"role": "user", "parts": [{"text": user}]}], "generationConfig": cfg}
    out = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{s['model']}:generateContent",
                payload, {"x-goog-api-key": key}, timeout)
    try:
        return _clean("".join(p.get("text", "") for p in out["candidates"][0]["content"]["parts"]))
    except Exception:
        raise LLMError(f"unexpected Gemini response: {str(out)[:200]}")


def extract_json(text):
    text = _clean(text)
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    raise LLMError(f"model did not return valid JSON: {text[:160]}")


def chat_json(system, user, **kw):
    return extract_json(chat(system, user, json_mode=True, **kw))


if __name__ == "__main__":
    s = settings()
    print("LLM settings:", s)
    if not s["configured"]:
        print("No key found. Add GROQ_API_KEY=... (or GEMINI_API_KEY=...) to the .env file in the project root.")
    else:
        try:
            print("reply:", chat_json('Reply with JSON only: {"ok": true, "word": "<one word>"}', "Say hi."))
            print("LLM OK")
        except LLMError as e:
            print("LLM ERROR:", e)
            print("Hint: 'model not found' -> set GROQ_MODEL / GEMINI_MODEL in .env to a current model name.")
