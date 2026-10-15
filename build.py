"""世界のニュースの見出しを集めて site/index.html を作る。標準ライブラリのみ。"""
import datetime as dt
import email.utils
import html
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "site", "index.html")
JST = dt.timezone(dt.timedelta(hours=9), "JST")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

# 取得元。source が None のものは、見出しの末尾「 - 媒体名」か <source> から媒体名を取る（Googleニュース）。
FEEDS = [
    {"tab": "world", "name": "Googleニュース 国際", "source": None,
     "url": "https://news.google.com/rss/headlines/section/topic/WORLD?hl=ja&gl=JP&ceid=JP:ja"},
    {"tab": "world", "name": "BBC日本語", "source": "BBC",
     "url": "https://feeds.bbci.co.uk/japanese/rss.xml"},
    {"tab": "world", "name": "朝日新聞 国際", "source": "朝日新聞",
     "url": "https://www.asahi.com/rss/asahi/international.rdf"},
    {"tab": "economy", "name": "Googleニュース ビジネス", "source": None,
     "url": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ja&gl=JP&ceid=JP:ja"},
]
TABS = [("world", "世界"), ("economy", "経済")]
MAX_AGE_HOURS = 36  # これより古い見出しは載せない
MAX_ITEMS = 40      # タブごとの上限
MAX_PER_SOURCE = 8  # 1つの媒体が並びすぎないようにする


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def local(tag):
    return tag.rsplit("}", 1)[-1]


def child_text(el, name):
    for c in el:
        if local(c.tag) == name and c.text:
            return c.text.strip()
    return ""


def parse_time(s):
    if not s:
        return None
    try:
        t = email.utils.parsedate_to_datetime(s)  # RSS 2.0 の pubDate
    except (TypeError, ValueError):
        try:
            t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))  # RDF の dc:date
        except ValueError:
            return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def parse_feed(feed, raw):
    items = []
    for el in ET.fromstring(raw).iter():
        if local(el.tag) != "item":
            continue
        title = child_text(el, "title")
        link = child_text(el, "link")
        when = parse_time(child_text(el, "pubDate") or child_text(el, "date"))
        if not title or not link or not when:
            continue
        source = feed["source"]
        if source is None:
            source = child_text(el, "source")
            m = re.match(r"^(.*)\s+-\s+([^-]+)$", title)
            if m:
                title = m.group(1).strip()
                source = source or m.group(2).strip()
        items.append({"tab": feed["tab"], "title": title, "link": link,
                      "source": source or feed["name"], "ts": when.timestamp()})
    return items


def key(title):
    """重複判定用。記号・空白を除いた先頭20字。"""
    return re.sub(r"[\s\W_]+", "", title)[:20]


def collect(now):
    items, failed = [], []
    for feed in FEEDS:
        try:
            got = parse_feed(feed, fetch(feed["url"]))
            if not got:
                raise ValueError("見出しが0件")
            items += got
        except Exception as e:  # 1つ失敗しても残りで作る
            print(f"取得失敗: {feed['name']}: {e}", file=sys.stderr)
            failed.append(feed["name"])
    cutoff = now.timestamp() - MAX_AGE_HOURS * 3600
    by_tab = {t: [] for t, _ in TABS}
    seen, per_source = set(), {}
    for it in sorted(items, key=lambda x: -x["ts"]):
        k = (it["tab"], key(it["title"]))
        s = (it["tab"], it["source"])
        if (it["ts"] < cutoff or k in seen or per_source.get(s, 0) >= MAX_PER_SOURCE
                or len(by_tab[it["tab"]]) >= MAX_ITEMS):
            continue
        seen.add(k)
        per_source[s] = per_source.get(s, 0) + 1
        by_tab[it["tab"]].append(it)
    return by_tab, failed


def fmt_jst(ts):
    t = dt.datetime.fromtimestamp(ts, JST)
    return f"{t.month}/{t.day} {t.hour}:{t.minute:02d}"


def render(by_tab, failed, now):
    tabs_html, panels_html = [], []
    for i, (tab, label) in enumerate(TABS):
        sel = "true" if i == 0 else "false"
        tabs_html.append(f'<button role="tab" id="t-{tab}" aria-controls="p-{tab}" aria-selected="{sel}">{label}</button>')
        rows = []
        for it in by_tab[tab]:
            rows.append(
                f'<li><a href="{html.escape(it["link"])}" target="_blank" rel="noopener">'
                f'<span class="title">{html.escape(it["title"])}</span>'
                f'<span class="meta">{html.escape(it["source"])} · '
                f'<time data-ts="{int(it["ts"])}">{fmt_jst(it["ts"])}</time></span></a></li>'
            )
        body = "\n".join(rows) or '<li class="empty">見出しを取得できませんでした</li>'
        hidden = "" if i == 0 else " hidden"
        panels_html.append(f'<ul role="tabpanel" id="p-{tab}" aria-labelledby="t-{tab}"{hidden}>\n{body}\n</ul>')
    note = f'<p class="warn">取得できなかった取得元：{html.escape("、".join(failed))}</p>' if failed else ""
    with open(os.path.join(ROOT, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    return (tpl.replace("{{UPDATED_TS}}", str(int(now.timestamp())))
               .replace("{{UPDATED}}", fmt_jst(now.timestamp()))
               .replace("{{TABS}}", "\n".join(tabs_html))
               .replace("{{PANELS}}", "\n".join(panels_html))
               .replace("{{NOTE}}", note)
               .replace("{{SOURCES}}", html.escape("、".join(f["name"] for f in FEEDS))))


def main():
    now = dt.datetime.now(JST)
    by_tab, failed = collect(now)
    if len(failed) == len(FEEDS):
        sys.exit("すべての取得元で失敗したので、前回のページを残す")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(render(by_tab, failed, now))
    print(json.dumps({t: len(v) for t, v in by_tab.items()}, ensure_ascii=False), "失敗:", failed or "なし")


if __name__ == "__main__":
    main()
