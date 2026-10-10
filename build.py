"""Girls Go Midterm Poly Markets: free Polymarket midterm dashboard with price moves, trends and movers."""
import json, html, datetime, urllib.request

TOP_N = 20      # markets in the table
POOL_N = 60     # markets considered for the Movers tab
KEYS = ("senate", "house", "governor", "midterm", "congress")

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "midterm-dashboard"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def num(x):
    try: return float(x)
    except Exception: return 0.0

def opt(x):
    try: return float(x)
    except Exception: return None

def cat(q):
    q = q.lower()
    return "Control" if "control" in q else "Senate" if "senate" in q else "House" if "house" in q else "Governor" if "governor" in q else "Other"

def scan():
    pool = []
    for off in (0, 100, 200):
        for e in get("https://gamma-api.polymarket.com/events?active=true&closed=false"
                     f"&order=volume&ascending=false&limit=100&offset={off}"):
            for m in e.get("markets", []):
                q = m.get("question", "")
                if "2026" in q + e.get("title", "") and any(k in q.lower() for k in KEYS):
                    p, t = m.get("outcomePrices"), m.get("clobTokenIds")
                    p = json.loads(p) if isinstance(p, str) else p
                    t = json.loads(t) if isinstance(t, str) else t
                    if p:
                        pool.append(dict(market=q, cat=cat(q), yes=float(p[0]), volume=num(m.get("volume")),
                            vol24=num(m.get("volume24hr")), d1=opt(m.get("oneDayPriceChange")),
                            d7=opt(m.get("oneWeekPriceChange")), d30=opt(m.get("oneMonthPriceChange")),
                            token=(t or [None])[0], url="https://polymarket.com/event/" + str(e.get("slug", ""))))
    pool = [x for x in pool if x["yes"] and x["volume"] > 0]
    pool.sort(key=lambda r: -r["volume"])
    return pool[:POOL_N]

def history(token):
    d = get(f"https://clob.polymarket.com/prices-history?market={token}&interval=1w&fidelity=180")
    h = [float(x["p"]) for x in d["history"]]
    step = max(1, len(h) // 40)
    return h[::step] + ([h[-1]] if h and (len(h) - 1) % step else [])

def main():
    try:
        pool = scan()
        for r in pool[:TOP_N]:
            try: r["hist"] = history(r["token"])
            except Exception as ex: print(f"history failed: {ex}")
        mk = dict(pool=pool)
    except Exception as ex:
        print(f"Polymarket scan failed: {ex}")  # keep last good snapshot
        try: mk = json.load(open("docs/markets.json"))
        except Exception: mk = dict(pool=[])
    now = datetime.datetime.now(datetime.timezone.utc)
    mk["updated"] = now.strftime("%b %d, %Y %H:%M UTC")
    mk["iso"] = now.isoformat()
    json.dump(mk, open("docs/markets.json", "w"))
    open("docs/index.html", "w").write(render(mk))
    print(f"{len(mk['pool'])} markets, updated {mk['updated']}")

# ---------- rendering ----------
def chg(x):
    if x is None: return "<td data-v=-999>–</td>"
    c = "pos" if x > 0 else "neg" if x < 0 else ""
    a = "▲" if x > 0 else "▼" if x < 0 else ""
    return f"<td class={c} data-v={x:.4f} style='--i:{min(abs(x)*10,1):.2f}'>{a} {abs(x)*100:.1f}</td>"

def spark(h):
    if not h or len(h) < 2: return ""
    lo, hi = min(h), max(h); rng = (hi - lo) or 1
    pts = " ".join(f"{i/(len(h)-1)*88+1:.1f},{24-(v-lo)/rng*22:.1f}" for i, v in enumerate(h))
    c = "pos" if h[-1] >= h[0] else "neg"
    return f"<svg class='spark {c}' viewBox='0 0 90 26' width=90 height=26 aria-hidden=true><polyline pathLength=1 points='{pts}'/></svg>"

def short(q, n=44):
    q = q.replace("Will ", "").replace("?", "")
    return html.escape(q if len(q) <= n else q[:n - 1] + "…")

def render(mk):
    pool = mk["pool"]; rows = pool[:TOP_N]
    total = sum(r["volume"] for r in rows) or 1
    v24 = sum(r["vol24"] for r in rows)
    movers = [p for p in pool if p["d1"] is not None]
    best = max(movers, key=lambda p: abs(p["d1"]), default=None)
    body = ""
    for i, m in enumerate(rows, 1):
        share = m["volume"] / total * 100
        body += (f"<tr data-cat='{m['cat']}'><td>{i}</td><td class=bet><a href='{html.escape(m['url'])}' target=_blank rel=noopener>{html.escape(m['market'])}</a><small>{m['cat']}</small></td>"
                 f"<td data-v={m['yes']:.4f}>{m['yes']*100:.0f}%</td>{chg(m['d1'])}{chg(m['d7'])}{chg(m['d30'])}"
                 f"<td class=sp>{spark(m.get('hist'))}</td>"
                 f"<td class=bar data-v={m['volume']:.0f}><i style='width:{min(share*2.5,100):.0f}%'></i><b>{m['volume']:,.0f}</b></td>"
                 f"<td data-v={m['vol24']:.0f}>{m['vol24']:,.0f}</td></tr>")
    body = body or "<tr><td></td><td class=bet>No data yet. The next scheduled run will fill this in.</td>" + "<td></td>" * 7 + "</tr>"
    tape = "".join(f"<span class=tk><b>{short(r['market'], 32)}</b> {r['yes']*100:.0f}% "
                   + (f"<em class={'pos' if r['d1']>0 else 'neg' if r['d1']<0 else ''}>{'▲' if r['d1']>0 else '▼' if r['d1']<0 else ''} {abs(r['d1'])*100:.1f}</em>" if r["d1"] is not None else "")
                   + "</span>" for r in rows)
    hist = {r["market"]: r.get("hist") for r in rows}
    def card(p):
        return (f"<li><a href='{html.escape(p['url'])}' target=_blank rel=noopener>{short(p['market'], 60)}</a>"
                f"<span class={'pos' if p['d1']>0 else 'neg'}>{'▲' if p['d1']>0 else '▼'} {abs(p['d1'])*100:.1f} pts</span>"
                f"<span class=px>{p['yes']*100:.0f}%</span>{spark(hist.get(p['market']))}</li>")
    up = sorted((p for p in movers if p["d1"] > 0), key=lambda p: -p["d1"])[:6]
    dn = sorted((p for p in movers if p["d1"] < 0), key=lambda p: p["d1"])[:6]
    mv = (f"<div class=cols><div><h2>Gaining today</h2><ul class=mv>{''.join(card(p) for p in up) or '<li>No gainers yet.</li>'}</ul></div>"
          f"<div><h2>Falling today</h2><ul class=mv>{''.join(card(p) for p in dn) or '<li>No decliners yet.</li>'}</ul></div></div>")
    bigmove = f"{'+' if best['d1']>0 else '-'}{abs(best['d1'])*100:.1f} pts" if best else "–"
    chips = "".join(f"<button class=chip data-f='{c}' aria-pressed={'true' if c=='All' else 'false'}>{c}</button>" for c in ("All", "Senate", "House", "Governor", "Control"))
    page = TEMPLATE
    for k, v in {"__UPDATED__": mk.get("updated", ""), "__ISO__": mk.get("iso", ""), "__N__": str(len(rows)), "__TOTAL__": f"{total:,.0f}",
                 "__V24__": f"{v24:,.0f}", "__BIG__": bigmove, "__TAPE__": tape, "__ROWS__": body,
                 "__MOVERS__": mv, "__CHIPS__": chips}.items():
        page = page.replace(k, v)
    return page

TEMPLATE = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Girls Go Midterm Poly Markets</title>
<link rel=preconnect href=https://fonts.googleapis.com><link rel=stylesheet href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=Bricolage+Grotesque:wght@700&display=swap">
<style>
:root{--bg:#ffeef6;--ink:#3a0f2b;--mute:#8a5a78;--line:#f6cfe3;--card:#fffafc;--acc:#e0338a;--pos:#0f7b5f;--neg:#c0281e}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#1d0a16;--ink:#ffe6f2;--mute:#c493ae;--line:#43182f;--card:#2a0f20;--acc:#ff6fb5;--pos:#3ecf9e;--neg:#ff8a7a}}
*{box-sizing:border-box}html,body{margin:0}body{background:var(--bg);color:var(--ink);font:15px/1.5 'IBM Plex Sans',system-ui,sans-serif;padding:0 0 40px}
.tape{background:var(--acc);color:#fff;overflow:hidden;white-space:nowrap;padding:max(8px,env(safe-area-inset-top)) 0 8px;font-size:13px}
.tape div{display:inline-block;animation:slide 60s linear infinite}.tape:hover div{animation-play-state:paused}
.tk{margin:0 22px}.tk em{font-style:normal;font-weight:600}.tape .pos,.tape .neg{color:#fff}
@keyframes slide{to{transform:translateX(-50%)}}
main{max-width:1040px;margin:24px auto 0;padding:0 20px}h1{font:700 34px 'Bricolage Grotesque','IBM Plex Sans',sans-serif;margin:0 0 4px;color:var(--acc)}
h2{font:700 18px 'Bricolage Grotesque','IBM Plex Sans',sans-serif;margin:0 0 8px;color:var(--acc)}
.sub{color:var(--mute);margin:0 0 24px;max-width:70ch}.stats{display:flex;gap:32px;flex-wrap:wrap;margin-bottom:24px}
.stats div{font-size:13px;color:var(--mute)}.stats b{display:block;font-size:24px;color:var(--ink);font-variant-numeric:tabular-nums}
.tabs,.chips{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}
.tabs button,.chip{font:600 14px 'IBM Plex Sans',sans-serif;padding:8px 18px;border-radius:99px;border:1px solid var(--line);background:var(--card);color:var(--mute);cursor:pointer}
.chip{padding:5px 14px;font-size:13px}.tabs button[aria-selected=true],.chip[aria-pressed=true]{background:var(--acc);border-color:var(--acc);color:#fff}
button:focus-visible,th:focus-visible,a:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.wrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;min-width:900px;font-variant-numeric:tabular-nums}
th,td{padding:10px 12px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th{font-weight:600;color:var(--mute);font-size:13px;cursor:pointer;position:sticky;top:0;background:var(--card)}
td:nth-child(2),th:nth-child(2){text-align:left}td:first-child,th:first-child{text-align:center;color:var(--mute)}
td.bet{white-space:normal;min-width:250px}td.bet a{color:var(--ink);text-decoration:none;font-weight:600}td.bet a:hover{color:var(--acc)}
small{display:block;color:var(--mute);font-size:12px}tr:last-child td{border-bottom:0}tbody tr:hover{background:color-mix(in srgb,var(--acc) 8%,transparent)}
.pos{color:var(--pos)}.neg{color:var(--neg)}td.pos,td.neg{background:color-mix(in srgb,currentColor calc(var(--i,0)*22%),transparent);font-weight:600}
.bar{position:relative;min-width:120px}.bar i{position:absolute;left:0;top:6px;bottom:6px;background:var(--acc);opacity:.22;border-radius:0 3px 3px 0}.bar b{position:relative;font-weight:600}
.spark{display:block;margin-left:auto}.spark polyline{fill:none;stroke:currentColor;stroke-width:2;stroke-linejoin:round;stroke-dasharray:1;animation:draw 1.4s ease-out}
@keyframes draw{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:20px}
ul.mv{list-style:none;margin:0;padding:0;background:var(--card);border:1px solid var(--line);border-radius:8px}
ul.mv li{display:grid;grid-template-columns:1fr auto auto 90px;gap:12px;align-items:center;padding:10px 14px;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}
ul.mv li:last-child{border:0}ul.mv a{color:var(--ink);text-decoration:none;font-weight:600}ul.mv .px{color:var(--mute)}
aside.disc{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--acc);border-radius:8px;padding:10px 14px;margin:0 0 24px;font-size:13px;color:var(--mute);max-width:78ch}aside.disc b{color:var(--ink)}
footer.disc2{max-width:1040px;margin:0 auto;padding:0 20px;color:var(--mute);font-size:12px}
p.note{color:var(--mute);font-size:13px;max-width:72ch;margin:16px 0}[hidden]{display:none}
@media(prefers-reduced-motion:reduce){.tape{overflow-x:auto}.tape div{animation:none}.spark polyline{animation:none}}
</style></head><body>
<div class=tape aria-label="Market ticker"><div>__TAPE____TAPE__</div></div>
<main>
<h1>Girls Go Midterm Poly Markets</h1>
<p class=sub>The biggest 2026 midterm markets on Polymarket, with how their odds are moving. Updated <time id=ago datetime="__ISO__">__UPDATED__</time>.</p>
<aside class=disc role=note><b>Just for fun and research.</b> This page only aggregates publicly available data from Polymarket. It is not financial advice, not betting advice, and not a recommendation to buy or sell anything. Prediction markets carry real risk, so do your own research.</aside>
<div class=stats><div>Total volume<b>__TOTAL__</b></div><div>Traded in 24h<b>__V24__</b></div><div>Biggest 24h move<b>__BIG__</b></div></div>
<div class=tabs role=tablist><button role=tab id=tab-m aria-selected=true aria-controls=p-m>Markets</button><button role=tab id=tab-v aria-selected=false aria-controls=p-v>Movers</button></div>
<section id=p-m role=tabpanel aria-labelledby=tab-m>
<div class=chips>__CHIPS__</div>
<div class=wrap><table id=t><thead><tr><th>#</th><th>Market</th><th>Yes odds</th><th>24h</th><th>7d</th><th>30d</th><th>7d trend</th><th>Volume</th><th>24h vol</th></tr></thead><tbody>__ROWS__</tbody></table></div>
<p class=note>Yes odds are Polymarket's current price for Yes. 24h, 7d and 30d are the change in percentage points. Click a column to sort and a market to open it on Polymarket.</p></section>
<section id=p-v role=tabpanel aria-labelledby=tab-v hidden>__MOVERS__
<p class=note>Biggest 24-hour price moves among the 60 most traded midterm markets. A big move on thin volume can reverse fast, so check the volume before reading much into it.</p></section>
</main>
<footer class=disc2>Data comes from Polymarket's public API and is not verified by this site. Not financial or betting advice. A fun way to help with Polymarket research.</footer><script>
const tabs=[...document.querySelectorAll('[role=tab]')];
const show=t=>tabs.forEach(o=>{const on=o===t;o.setAttribute('aria-selected',on);document.getElementById(o.getAttribute('aria-controls')).hidden=!on});
tabs.forEach(t=>t.onclick=()=>{show(t);history.replaceState(null,'','#'+t.id)});
const first=tabs.find(t=>'#'+t.id==location.hash);if(first)show(first);
const ago=document.getElementById('ago'),stamp=Date.parse(ago.getAttribute('datetime'));
const tick=()=>{if(isNaN(stamp))return;const m=Math.max(0,Math.round((Date.now()-stamp)/60000));ago.textContent=m<1?'just now':m<60?m+' min ago':Math.round(m/60)+' hr ago'};tick();setInterval(tick,30000);
setTimeout(function r(){document.hidden?setTimeout(r,60000):location.reload()},15*60*1000);
const rows=()=>[...document.querySelectorAll('#t tbody tr')];
document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{document.querySelectorAll('.chip').forEach(o=>o.setAttribute('aria-pressed',o===c));rows().forEach(r=>r.hidden=c.dataset.f!='All'&&r.dataset.cat!=c.dataset.f)});
document.querySelectorAll('#t th').forEach((h,i)=>{h.tabIndex=0;const s=()=>{const b=document.querySelector('#t tbody'),d=h.dataset.d=h.dataset.d=='1'?'-1':'1';
const v=r=>{const c=r.cells[i];return c.dataset.v!==undefined?parseFloat(c.dataset.v):c.innerText};
[...b.rows].sort((x,y)=>{const a=v(x),c=v(y);return (typeof a=='number'&&typeof c=='number'?a-c:String(a).localeCompare(String(c)))*d}).forEach(r=>b.append(r))};h.onclick=s;h.onkeydown=e=>e.key=='Enter'&&s()});
</script></body></html>"""

if __name__ == "__main__":
    main()
