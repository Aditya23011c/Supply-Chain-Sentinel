"""Live signal clients for the Monitor Agent: Google News RSS + Open-Meteo weather (both free, no API key),
then classification by the LLM (if configured) or a rules fallback. Everything fails soft -> returns nothing.
Try it standalone:  python -m agents.monitor.feeds
"""
import re, urllib.parse, urllib.request, uuid
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from agents import config, llm  # noqa: F401
from agents.state import now

NODES = [  # must match the route_node values in data/orders_inventory.json
    {"name": "Mumbai", "lat": 19.076, "lon": 72.878, "keywords": ["Mumbai", "Nhava Sheva", "JNPT"]},
    {"name": "Chennai", "lat": 13.083, "lon": 80.271, "keywords": ["Chennai", "Ennore"]},
    {"name": "Kolkata", "lat": 22.572, "lon": 88.364, "keywords": ["Kolkata", "Haldia"]},
    {"name": "Delhi", "lat": 28.614, "lon": 77.209, "keywords": ["Delhi", "Gurugram", "Noida"]},
]
RISK_QUERY = ["port", "strike", "fire", "flood", "cyclone", "closure", "shutdown", "blockade"]
TYPES = ["port_closure", "supplier_factory_fire", "severe_weather", "strike", "flood", "other"]


def _http_get(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (SupplyChainSentinel hackathon bot)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ---------------------------------------------------------------- signals
def fetch_news(node, limit=8):
    terms = " OR ".join(f'"{k}"' if " " in k else k for k in node["keywords"])
    q = f"({terms}) ({' OR '.join(RISK_QUERY)}) when:2d"
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
    try:
        root = ET.fromstring(_http_get(url))
    except Exception:
        return []
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        if not title:
            continue
        items.append({"title": title, "link": (it.findtext("link") or "").strip(),
                      "source": (it.findtext("source") or "Google News").strip(), "published": it.findtext("pubDate") or ""})
        if len(items) >= limit:
            break
    return items


def fetch_weather(node):
    """Returns a weather 'signal' dict only when conditions look severe, else None."""
    import json
    url = ("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
        "latitude": node["lat"], "longitude": node["lon"], "timezone": "auto", "forecast_days": 2,
        "current": "weather_code,wind_gusts_10m", "daily": "precipitation_sum,wind_gusts_10m_max"}))
    try:
        d = json.loads(_http_get(url))
        gust = max([g for g in d["daily"]["wind_gusts_10m_max"] if g is not None] + [d["current"].get("wind_gusts_10m") or 0])
        rain = max([r for r in d["daily"]["precipitation_sum"] if r is not None] + [0])
        code = d["current"].get("weather_code") or 0
    except Exception:
        return None
    if not (gust >= 65 or rain >= 60 or code >= 95):
        return None
    return {"title": f"Severe weather forecast near {node['name']}: gusts up to {gust:.0f} km/h, up to {rain:.0f} mm rain in 48h",
            "link": "https://open-meteo.com/", "source": "Open-Meteo", "published": now(), "kind": "weather"}


# ---------------------------------------------------------------- classification
TYPE_RULES = {
    "port_closure": (["port", "terminal", "jnpt", "nhava sheva", "harbour", "harbor"], ["closed", "closure", "shut", "suspend", "halt", "blockade", "blocked", "congestion", "stranded"]),
    "supplier_factory_fire": (["fire", "blaze", "explosion", "blast"], ["factory", "plant", "warehouse", "industrial", "godown", "manufacturing"]),
    "strike": (["strike", "bandh", "lockout", "walkout"], ["truck", "transport", "workers", "union", "logistics", "customs", "dock"]),
    "flood": (["flood", "waterlogging", "inundat", "deluge"], ["road", "rail", "highway", "port", "factory", "city", "supply", "traffic"]),
    "severe_weather": (["cyclone", "storm", "landslide", "red alert", "orange alert"], ["warning", "alert", "port", "flights", "shipping", "rail", "landfall", "closed"]),
}


def rules_classify(node, signals):
    best = None
    for i, s in enumerate(signals):
        if s.get("kind") == "weather":
            cand = (0.7, i, "severe_weather")
            best = cand if not best or cand[0] > best[0] else best
            continue
        t = s["title"].lower()
        for dtype, (a, b) in TYPE_RULES.items():
            # match at the START of a word, so "port" matches "port"/"ports" but NOT "airport" or "support"
            ha, hb = [w for w in a if re.search(r"\b" + re.escape(w), t)], [w for w in b if re.search(r"\b" + re.escape(w), t)]
            if ha and hb:
                cand = (min(0.9, 0.5 + 0.1 * (len(ha) + len(hb))), i, dtype)
                if not best or cand[0] > best[0]:
                    best = cand
    if not best:
        return None
    sev, i, dtype = best
    return _event(node, signals, i, dtype, sev, signals[i]["title"], "keyword rules", "matched disruption keywords in headline")


def llm_classify(node, signals):
    listing = "\n".join(f"{i + 1}. [{s['source']}] {s['title']} ({s['published'][:25]})" for i, s in enumerate(signals))
    raw = llm.chat_json(
        "You are a supply-chain risk analyst for an Indian manufacturer. From the signals about one location, decide whether "
        "there is a REAL, CURRENT disruption to ports, logistics, roads/rail, or manufacturing there. Ignore opinion pieces, "
        "past events, drills, sports, entertainment and unrelated crime. Reply with JSON only: "
        '{"disruption": true|false, "disruption_type": "port_closure|supplier_factory_fire|severe_weather|strike|flood|other", '
        '"headline": "<=140 chars plain English", "severity": 0.0-1.0, "evidence_index": <1-based number of the most relevant signal>, '
        '"reasoning": "<=160 chars"}',
        f"Location: {node['name']}\nSignals:\n{listing}")
    if not isinstance(raw, dict) or not raw.get("disruption"):
        return None
    try:
        idx = int(raw.get("evidence_index", 1)) - 1
    except (TypeError, ValueError):
        idx = 0
    idx = idx if 0 <= idx < len(signals) else 0
    dtype = raw.get("disruption_type") if raw.get("disruption_type") in TYPES else "other"
    try:
        sev = max(0.0, min(1.0, float(raw.get("severity", 0.6))))
    except (TypeError, ValueError):
        sev = 0.6
    return _event(node, signals, idx, dtype, sev, str(raw.get("headline") or signals[idx]["title"]), f"llm:{llm.settings()['provider']}/{llm.settings()['model']}", str(raw.get("reasoning") or ""))


def _event(node, signals, idx, dtype, sev, headline, classifier, reasoning):
    ordered = [signals[idx]]   # only the evidence the classifier actually relied on
    return {"event_id": "evt_" + uuid.uuid4().hex[:6], "disruption_type": dtype, "location": node["name"],
            "headline": headline.strip()[:160], "source": ", ".join(sorted({s["source"] for s in ordered})),
            "severity_estimate": round(sev, 2), "detected_at": now(),
            "evidence": [{k: s[k] for k in ("title", "link", "source")} for s in ordered],
            "classifier": classifier, "reasoning": reasoning[:200]}


def classify(node, signals):
    if llm.settings()["configured"]:
        try:
            return llm_classify(node, signals)
        except llm.LLMError as e:
            ev = rules_classify(node, signals)
            if ev:
                ev["classifier"] = f"keyword rules (LLM unavailable: {str(e)[:60]})"
            return ev
    return rules_classify(node, signals)


# ---------------------------------------------------------------- the scan
def scan_live(nodes=NODES, min_severity=0.5):
    with ThreadPoolExecutor(8) as ex:
        news = list(ex.map(fetch_news, nodes))
        weather = list(ex.map(fetch_weather, nodes))
    work = []
    for node, n, w in zip(nodes, news, weather):
        signals = ([w] if w else []) + n
        if signals:
            work.append((node, signals))
    if not work:
        return None
    with ThreadPoolExecutor(4) as ex:
        events = [e for e in ex.map(lambda nw: classify(*nw), work) if e and e["severity_estimate"] >= min_severity]
    return max(events, key=lambda e: e["severity_estimate"]) if events else None


if __name__ == "__main__":
    print("LLM:", llm.label())
    for node in NODES:
        n, w = fetch_news(node), fetch_weather(node)
        print(f"\n== {node['name']}: {len(n)} headlines, weather {'SEVERE' if w else 'ok'}")
        for s in n[:3]:
            print("  -", s["title"][:110])
    print("\nRunning full scan...")
    ev = scan_live()
    print(ev if ev else "No live disruption found (the scripted fallback would be used).")
