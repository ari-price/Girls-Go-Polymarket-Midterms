"""Girls Go Midterm Poly Markets: rank the biggest 2026 midterm markets on Kalshi + Polymarket."""
import csv, json, urllib.request, datetime, html, collections

TOP_N = 20  # change to show more markets

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "midterm-dashboard"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)

KEYS = ("senate", "house", "governor", "midterm", "congress")

def num(x):
    try: return float(x)
    except Exception: return 0.0

def scan_polymarket():
    out = []
    for off in (0, 100, 200):
        evs = get("https://gamma-api.polymarket.com/events?active=true&closed=false"
                  f"&order=volume&ascending=false&limit=100&offset={off}")
        for e in evs:
            for m in e.get("markets", []):
                q = m.get("question", "")
                if "2026" in q + e.get("title", "") and any(k in q.lower() for k in KEYS):
                    p = m.get("outcomePrices")
                    p = json.loads(p) if isinstance(p, str) else p
                    if p: out.append(dict(venue="Polymarket", market=q, yes=float(p[0]), volume=num(m.get("volume"))))
    return out

def scan_kalshi():
    out, cursor = [], ""
    for _ in range(6):
        d = get("https://api.elections.kalshi.com/trade-api/v2/events?status=open&with_nested_markets=true&limit=200"
                + (f"&cursor={cursor}" if cursor else ""))
        for e in d.get("events", []):
            t = e.get("title", "")
            if any(k in t.lower() for k in KEYS) and "2026" in (t + e.get("event_ticker", "") + e.get("sub_title", "")):
                for m in e.get("markets", []):
                    def c(k):
                        v = m.get(k + "_dollars", m.get(k)); v = num(v)
                        return v if k + "_dollars" in m else v / 100
                    bid, ask = c("yes_bid"), c("yes_ask")
                    yes = (bid + ask) / 2 if bid and ask else c("last_price")
                    name = m.get("title") or t
                    sub = m.get("yes_sub_title") or ""
                    out.append(dict(venue="Kalshi", market=f"{name} ({sub})" if sub and sub not in name else name,
                                    yes=yes, volume=num(m.get("volume_fp") or m.get("volume"))))
        cursor = d.get("cursor") or ""
        if not cursor: break
    return out

def top_markets(n=TOP_N):
    """Biggest midterm markets on Kalshi + Polymarket by volume, independent of your holdings."""
    found, ok = [], []
    for name, fn in (("Kalshi", scan_kalshi), ("Polymarket", scan_polymarket)):
        try: found += fn(); ok.append(name)
        except Exception as ex: print(f"{name} scan failed: {ex}")
    if not found:  # keep last good snapshot
        try: return json.load(open("docs/markets.json"))
        except Exception: return dict(rows=[], note="Live market scan unavailable.")
    found = [f for f in found if f["yes"] and f["volume"] > 0]
    found.sort(key=lambda r: -r["volume"])
    note = "Sources: " + " and ".join(ok) + ("." if len(ok) == 2 else f". {({'Kalshi','Polymarket'}-set(ok)).pop()} unavailable.")
    return dict(rows=found[:n], note=note)


def main():
    import datetime
    mk = top_markets()
    mk["updated"] = datetime.datetime.now(datetime.timezone.utc).strftime("%b %d, %Y %H:%M UTC")
    json.dump(mk, open("docs/markets.json", "w"), indent=1)
    open("docs/index.html", "w").write(render(mk))
    print(f"{len(mk['rows'])} markets, updated {mk['updated']}")

def render(mk):
    rows = mk["rows"]
    total = sum(r["volume"] for r in rows) or 1
    by = collections.Counter(r["venue"] for r in rows)
    body = ""
    for i, m in enumerate(rows, 1):
        share = m["volume"] / total * 100
        body += (f"<tr><td>{i}</td><td class=bet>{html.escape(m['market'])}</td><td>{m['venue']}</td>"
                 f"<td>{m['yes']*100:.0f}%</td>"
                 f"<td class=bar><i style='width:{min(share*2.5,100):.0f}%'></i><b>{m['volume']:,.0f}</b></td>"
                 f"<td>{share:.1f}%</td></tr>")
    if not body:
        body = "<tr><td></td><td class=bet>No data yet. The next scheduled run will fill this in.</td><td></td><td></td><td></td><td></td></tr>"
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Girls Go Midterm Poly Markets</title>
<link rel=preconnect href=https://fonts.googleapis.com><link rel=stylesheet href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=Bricolage+Grotesque:wght@700&display=swap">
<style>
:root{{--bg:#ffeef6;--ink:#3a0f2b;--mute:#8a5a78;--line:#f6cfe3;--card:#fffafc;--acc:#e0338a}}
@media(prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#1d0a16;--ink:#ffe6f2;--mute:#c493ae;--line:#43182f;--card:#2a0f20;--acc:#ff6fb5}}}}
*{{box-sizing:border-box}}html,body{{margin:0}}body{{background:var(--bg);color:var(--ink);font:15px/1.5 'IBM Plex Sans',system-ui,sans-serif;padding:max(24px,env(safe-area-inset-top)) 20px 40px}}
main{{max-width:1000px;margin:auto}}h1{{font:700 34px 'Bricolage Grotesque','IBM Plex Sans',sans-serif;margin:0 0 4px;color:var(--acc)}}
.sub{{color:var(--mute);margin:0 0 24px;max-width:70ch}}.stats{{display:flex;gap:32px;flex-wrap:wrap;margin-bottom:24px}}
.stats div{{font-size:13px;color:var(--mute)}}.stats b{{display:block;font-size:24px;color:var(--ink);font-variant-numeric:tabular-nums}}
.wrap{{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:8px}}
table{{border-collapse:collapse;width:100%;min-width:640px;font-variant-numeric:tabular-nums}}
th,td{{padding:10px 12px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}}
th{{font-weight:600;color:var(--mute);font-size:13px;cursor:pointer;position:sticky;top:0;background:var(--card)}}
th:focus-visible{{outline:2px solid var(--acc)}}td:nth-child(2),th:nth-child(2),td:nth-child(3),th:nth-child(3){{text-align:left}}
td:first-child,th:first-child{{text-align:center;color:var(--mute)}}td.bet{{white-space:normal;min-width:260px}}
.bar{{position:relative;min-width:130px}}.bar i{{position:absolute;left:0;top:6px;bottom:6px;background:var(--acc);opacity:.22;border-radius:0 3px 3px 0}}
.bar b{{position:relative;font-weight:600}}tr:last-child td{{border-bottom:0}}
p.note{{color:var(--mute);font-size:13px;max-width:70ch;margin-top:16px}}
</style></head><body><main>
<h1>Girls Go Midterm Poly Markets</h1>
<p class=sub>The {len(rows)} most traded 2026 midterm markets on Kalshi and Polymarket, ranked by volume. Updated {mk.get('updated','')}. {html.escape(mk['note'])}</p>
<div class=stats><div>Markets listed<b>{len(rows)}</b></div><div>Total volume<b>{total:,.0f}</b></div><div>Kalshi / Polymarket<b>{by.get('Kalshi',0)} / {by.get('Polymarket',0)}</b></div></div>
<div class=wrap><table id=t><thead><tr><th>#</th><th>Market</th><th>Venue</th><th>Yes odds</th><th>Volume</th><th>Share</th></tr></thead><tbody>{body}</tbody></table></div>
<p class=note>Yes odds are the market's current price for Yes. Kalshi volume counts contracts and Polymarket volume counts dollars, so the ranking is approximate. Click a column to sort. Not financial advice.</p>
</main><script>
document.querySelectorAll('#t th').forEach((h,i)=>{{h.tabIndex=0;const s=()=>{{const b=document.querySelector('#t tbody'),d=h.dataset.d=h.dataset.d=='1'?'-1':'1';
[...b.rows].sort((x,y)=>{{const a=x.cells[i].innerText,c=y.cells[i].innerText,n=v=>parseFloat(v.replace(/[^0-9.+-]/g,''));
return (isNaN(n(a))||isNaN(n(c))?a.localeCompare(c):n(a)-n(c))*d}}).forEach(r=>b.append(r))}};h.onclick=s;h.onkeydown=e=>e.key=='Enter'&&s()}});
</script></body></html>"""

if __name__ == "__main__":
    main()
