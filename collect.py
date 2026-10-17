#!/usr/bin/env python3
"""Collecte les sources ANGLOGRAPHES sur les Hokkaido Nippon-Ham Fighters (NPB).

Constat de sondage (17/10/2026) : la couverture anglophone d'un club de NPB est
rare. Sont ecartes car morts ou inaccessibles : Yakyu Cosmo (dernier article
nov. 2025), JapanBall (oct. 2025), NPB.jp/en (404), r/NPB (403). Les deux
sources retenues sont les seules reellement vivantes :

  1. Bing News  : agrege la presse anglophone (MLB Rumors, theScore, RotoWire,
                  MSN, note, newser...) et donne un vrai 302 vers l'editeur.
  2. Site officiel /en/news/ : version anglaise du club, via un proxy gratuit.

Aucune API payante, aucune cle, aucun compte.
"""
import os, re, json, html as ht, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
RAW = os.path.join(DATA, "raw")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
JINA = "https://r.jina.ai/"

BING = "https://www.bing.com/news/search?q=%s&format=RSS&count=60"
QUERIES = [
    ("Hokkaido Nippon-Ham Fighters", "Presse \u2014 club"),
    ("Nippon Ham Fighters", "Presse \u2014 Nippon Ham"),
    ("Fighters NPB Hokkaido", "Presse \u2014 NPB"),
    ("Fighters Es Con Field", "Presse \u2014 stade"),
    ("Hokkaido Fighters Pacific League", "Presse \u2014 Pacific League"),
    ("Nippon Ham Fighters Japan Series", "Presse \u2014 Japan Series"),
]
OFFICIAL = "https://www.fighters.co.jp/en/news/"

CJK_RE = re.compile(r"[\u3000-\u30ff\u4e00-\u9fff\uff00-\uffef]")


def is_english(text):
    """Le fil est anglophone : on ecarte les titres en japonais (DAZN, Yahoo...
    remontent via Bing News avec des titres en japonais)."""
    if not text:
        return False
    cjk = len(CJK_RE.findall(text))
    return cjk == 0 or (cjk / max(1, len(text))) < 0.12


NAV_TITLES = {
    "news", "all news", "team", "events", "tickets", "season ticket",
    "food & drinks", "food and drinks", "press release", "previous month",
    "next month", "match broadcast schedule", "gaora appearance information",
    "shop", "stadium", "access", "schedule", "standings", "roster", "farm team",
    "goods", "sponsor", "museum", "kids", "academy", "mascot", "cheer",
    "broadcast", "ticket", "player", "players",
}
KEYWORDS = ("fighter", "hokkaido", "nippon-ham", "nippon ham", "nipponham")
DAYS = 30
CAPS = {"bing": 26, "official": 10}
TOTAL_CAP = 36
JACCARD = 0.55
JUNK = ("auction", "ticket", "shop")

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
STOP = set("the a an and or of to in for on with at by from is are was were be been will "
           "would can could has have had its his her their this that these those as not "
           "but who what when why how new say says said into".split())


def fetch(url, timeout=30, tries=2, headers=None):
    last = None
    for i in range(tries):
        try:
            h = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9",
                 "Accept-Encoding": "identity"}
            if headers:
                h.update(headers)
            with urllib.request.urlopen(urllib.request.Request(url, headers=h),
                                        timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def clean(s):
    return WS_RE.sub(" ", ht.unescape(TAG_RE.sub(" ", s or ""))).strip()


def clip(s, n=230):
    if len(s) <= n:
        return s
    cut, sp = s[:n], s[:n].rfind(" ")
    return (cut[:sp] if sp > 100 else cut).rstrip(" ,;:.") + "\u2026"


def tokens(t):
    return {w for w in re.findall(r"[a-z0-9']+", (t or "").lower())
            if len(w) > 2 and w not in STOP}


def jac(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def parse_when(raw):
    if not raw:
        return None
    try:
        w = parsedate_to_datetime(raw)
    except Exception:
        try:
            w = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None
    return w.replace(tzinfo=timezone.utc) if w.tzinfo is None else w


def rss_items(blob):
    try:
        root = ET.fromstring(blob)
    except Exception as e:
        return [], "parse: %s" % e
    loc = lambda t: t.split("}")[-1]
    if loc(root.tag) == "rss":
        ch = [c for c in root if loc(c.tag) == "channel"]
        nodes = [i for i in (ch[0] if ch else []) if loc(i.tag) == "item"]
    elif loc(root.tag) == "feed":
        nodes = [c for c in root if loc(c.tag) == "entry"]
    else:
        return [], "racine " + loc(root.tag)
    out = []
    for n in nodes:
        def tx(*names):
            for nm in names:
                for c in n:
                    if loc(c.tag) == nm and c.text and c.text.strip():
                        return c.text.strip()
            return ""
        link = ""
        for c in n:
            if loc(c.tag) == "link":
                href = c.get("href")
                if href and (c.get("rel") or "alternate").lower() == "alternate":
                    link = href.strip(); break
                if c.text and c.text.strip().startswith("http"):
                    link = c.text.strip(); break
        out.append({"title": tx("title"), "url": link,
                    "when": parse_when(tx("pubDate", "published", "updated")),
                    "publisher": clean(tx("source", "Source")), "summary": ""})
    return out, None


def resolve_bing(url, timeout=20):
    """Suit la redirection apiclick de Bing jusqu'a l'article d'origine."""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        with urllib.request.build_opener(NoRedirect).open(
                urllib.request.Request(url, method="HEAD",
                                       headers={"User-Agent": UA}), timeout=timeout) as r:
            return r.headers.get("Location")
    except urllib.error.HTTPError as e:
        return e.headers.get("Location")
    except Exception:
        return None


def official_items():
    """Articles de la version anglaise du site du club, via un proxy gratuit.

    Le site est en Drupal : pas de flux RSS exploitable. On lit la page de news
    rendue en markdown et on y prend les liens d'articles.
    """
    try:
        blob = fetch(JINA + OFFICIAL, 60, headers={"x-return-format": "markdown"})
    except Exception:
        return []
    md = blob.decode("utf-8", "replace")
    out, seen = [], set()
    for m in re.finditer(r"\[([^\]\n]{12,140})\]\((https://www\.fighters\.co\.jp/en/news/[^\)\s]+)\)", md):
        title, url = clean(m.group(1)), m.group(2)
        if url in seen:
            continue
        # La page de news melange les articles et les rubriques du menu
        # ("Season Ticket", "Food & Drinks"...). Un vrai titre d'article est
        # descriptif : on exige au moins 5 mots et on ecarte le menu.
        low = title.lower()
        if len(title.split()) < 5 or low in NAV_TITLES:
            continue
        seen.add(url)
        out.append({"title": title, "url": url, "when": None,
                    "publisher": "Hokkaido Nippon-Ham Fighters", "summary": ""})
    return out


def collect():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=DAYS)
    os.makedirs(RAW, exist_ok=True)
    report, staged, proxied = [], [], set()

    # 1. Bing News
    for query, label in QUERIES:
        url = BING % urllib.parse.quote(query)
        slug = re.sub(r"\W+", "-", label).lower()
        path = os.path.join(RAW, "bing-%s.xml" % slug)
        err = None
        try:
            open(path, "wb").write(fetch(url))
        except Exception as e:
            err = "%s: %s" % (type(e).__name__, getattr(e, "code", e))
        items, perr = rss_items(open(path, "rb").read()) if os.path.exists(path) else ([], "absent")
        err = err or perr
        n = 0
        for it in items:
            t = it["title"] or ""
            if not t or not it["url"]:
                continue
            if it["when"] and it["when"] < cutoff:
                continue
            if not any(k in (t + " " + it["url"]).lower() for k in KEYWORDS):
                continue
            if not is_english(t):
                continue
            pub = it["publisher"] or urllib.parse.urlparse(it["url"]).netloc
            if any(j in pub.lower() for j in JUNK):
                continue
            it.update(chip=pub, kind="bing", priority=0,
                      resolve="bing.com" in it["url"])
            it["_dt"] = it["when"] or now
            staged.append(it)
            n += 1
        report.append({"source": label, "site": "https://www.bing.com/news", "n": n,
                       "ok": n > 0, "note": (err or "Bing News RSS")[:64]})

    # 2. site officiel
    off = official_items()
    n = 0
    for it in off:
        it.update(chip="Site officiel", kind="official", priority=1)
        it["_dt"] = now
        staged.append(it)
        n += 1
    if n:
        proxied.add("site officiel via jina")
    report.append({"source": "Site officiel (EN)", "site": OFFICIAL, "n": n,
                   "ok": n > 0, "note": "fighters.co.jp/en/news via proxy"})

    # 3. dedup
    staged.sort(key=lambda x: (x["priority"], -x["_dt"].timestamp()))
    kept, sigs = [], []
    for it in staged:
        s = tokens(it["title"])
        if any(jac(s, k) >= JACCARD for k in sigs):
            continue
        sigs.append(s)
        kept.append(it)

    per, final = {}, []
    for it in kept:
        c = it["chip"]
        if per.get(c, 0) >= CAPS.get(it["kind"], 12):
            continue
        per[c] = per.get(c, 0) + 1
        final.append(it)
    final.sort(key=lambda x: x["_dt"], reverse=True)
    final = final[:TOTAL_CAP]

    resolved = 0
    for it in final:
        if it.pop("resolve", False):
            real = resolve_bing(it["url"])
            if real:
                it["url"] = real
                resolved += 1
        it["summary"] = clip(it["summary"])

    items = [{"title": i["title"], "url": i["url"], "when": i["_dt"].isoformat(),
              "summary": i["summary"], "publisher": i["publisher"], "chip": i["chip"],
              "site": "https://www.fighters.co.jp/en/" if i["kind"] == "official"
                      else "https://www.bing.com/news"} for i in final]

    payload = {"generated": now.isoformat(), "count": len(items),
               "sources": report, "items": items}
    prev = 0
    if os.path.exists(os.path.join(DATA, "items.json")):
        try:
            prev = json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))["count"]
        except Exception:
            prev = 0
    if not items and prev:
        print("collecte vide -> items.json precedent conserve (%d)" % prev)
        return
    json.dump(payload, open(os.path.join(DATA, "items.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("articles retenus: %d" % len(items))
    for r in report:
        print("  %-26s %s n=%-3s %s" % (r["source"], "OK " if r["ok"] else "KO ", r["n"], r["note"][:50]))
    print("  liens Bing resolus vers l'editeur: %d" % resolved)
    if proxied:
        print("  via proxy: %s" % ", ".join(sorted(proxied)))


if __name__ == "__main__":
    collect()
