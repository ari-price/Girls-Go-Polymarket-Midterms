"""Girls Go Midterm Poly Markets: free Polymarket midterm dashboard + beginner guide."""
import json, html, datetime, urllib.request

TOP_N = 20      # markets in the table
POOL_N = 60     # markets considered for Movers and control odds
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
                            liq=opt(m.get("liquidityNum", m.get("liquidity"))), spread=opt(m.get("spread")),
                            end=str(m.get("endDate") or "")[:10], token=(t or [None])[0],
                            url="https://polymarket.com/event/" + str(e.get("slug", ""))))
    pool = [x for x in pool if x["volume"] > 0]
    for x in pool: x["dec"] = x["yes"] <= 0.01 or x["yes"] >= 0.99  # effectively decided (eliminated or locked in)
    pool.sort(key=lambda r: -r["volume"])
    return [x for x in pool if not x["dec"]][:POOL_N] + [x for x in pool if x["dec"]][:10]

def history(token):
    d = get(f"https://clob.polymarket.com/prices-history?market={token}&interval=1w&fidelity=180")
    h = [float(x["p"]) for x in d["history"]]
    step = max(1, len(h) // 40)
    return h[::step] + ([h[-1]] if h and (len(h) - 1) % step else [])

def main():
    try:
        pool = scan()
        for r in [p for p in pool if not p["dec"]][:TOP_N]:
            try: r["hist"] = history(r["token"])
            except Exception as ex: print(f"history failed: {ex}")
        mk = dict(pool=pool)
    except Exception as ex:
        print(f"Polymarket scan failed: {ex}")  # keep last good snapshot
        try: mk = json.load(open("docs/markets.json"))
        except Exception: mk = dict(pool=[])
    now = datetime.datetime.now(datetime.timezone.utc)
    mk["updated"], mk["iso"] = now.strftime("%b %d, %Y %H:%M UTC"), now.isoformat()
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

def pct(y):
    return "&lt;1%" if y < 0.01 else "&gt;99%" if y > 0.99 else f"{y*100:.0f}%"

def short(q, n=44):
    q = q.replace("Will ", "").replace("?", "")
    return html.escape(q if len(q) <= n else q[:n - 1] + "…")

def thin(m):
    return (m["liq"] is not None and m["liq"] < 10000) or (m["spread"] is not None and m["spread"] > 0.04)

def control(pool, chamber):
    """Market-implied chance Democrats control a chamber (None if no matching market)."""
    for p in pool:
        q = p["market"].lower()
        if "control" in q and chamber in q:
            if "democrat" in q: return p["yes"]
            if "republican" in q: return 1 - p["yes"]
    return None

def gauge(name, d):
    if d is None: return f"<div class=g><b>{name}</b><span class=sub2>No matching market found</span></div>"
    return (f"<div class=g><b>{name}</b><div class=gb role=img aria-label='{name}: Democrats {d*100:.0f}%, Republicans {(1-d)*100:.0f}%'>"
            f"<i style='width:{d*100:.0f}%'></i></div><span><u>Dem {d*100:.0f}%</u> <s>GOP {(1-d)*100:.0f}%</s></span></div>")

def render(mk):
    allp = mk["pool"]
    pool = [p for p in allp if not p.get("dec")]; rows = pool[:TOP_N]; dead = [p for p in allp if p.get("dec")]
    total = sum(r["volume"] for r in rows) or 1
    v24 = sum(r["vol24"] for r in rows)
    movers = [p for p in pool if p["d1"] is not None]
    best = max(movers, key=lambda p: abs(p["d1"]), default=None)
    body = ""
    for i, m in enumerate(rows + dead, 1):
        dec = bool(m.get("dec"))
        share = m["volume"] / total * 100
        flag = "<span class=thin title='Low liquidity or wide spread: prices may be hard to trade at'>thin</span>" if thin(m) else ""
        liq = "–" if m["liq"] is None else f"{m['liq']:,.0f}"
        sp = "–" if m["spread"] is None else f"{m['spread']*100:.1f}"
        body += (f"<tr data-cat='{m['cat']}' data-dec={int(dec)}{' hidden' if dec else ''}><td>{'–' if dec else i}</td><td class=bet><a href='{html.escape(m['url'])}' target=_blank rel=noopener>{html.escape(m['market'])}</a><small>{m['cat']} {flag}</small></td>"
                 f"<td data-v={m['yes']:.4f}>{pct(m['yes'])}</td>{chg(m['d1'])}{chg(m['d7'])}{chg(m['d30'])}"
                 f"<td class=sp>{spark(m.get('hist'))}</td>"
                 f"<td class=bar data-v={m['volume']:.0f}><i style='width:{min(share*2.5,100):.0f}%'></i><b>{m['volume']:,.0f}</b></td>"
                 f"<td data-v={m['liq'] or 0:.0f}>{liq}</td><td data-v={m['spread'] or 0:.4f}>{sp}</td><td>{html.escape(m['end'] or '–')}</td></tr>")
    body = body or "<tr><td></td><td class=bet>No data yet. The next scheduled run will fill this in.</td>" + "<td></td>" * 9 + "</tr>"
    def tk(r):
        d = r["d1"]
        e = "" if d is None else f"<em class={'pos' if d>0 else 'neg' if d<0 else ''}>{'▲' if d>0 else '▼' if d<0 else ''} {abs(d)*100:.1f}</em>"
        return f"<span class=tk><b>{short(r['market'], 32)}</b> {pct(r['yes'])} {e}</span>"
    tape = "".join(tk(r) for r in rows)
    hist = {r["market"]: r.get("hist") for r in rows}
    def card(p):
        return (f"<li><a href='{html.escape(p['url'])}' target=_blank rel=noopener>{short(p['market'], 60)}</a>"
                f"<span class={'pos' if p['d1']>0 else 'neg'}>{'▲' if p['d1']>0 else '▼'} {abs(p['d1'])*100:.1f} pts</span>"
                f"<span class=px>{pct(p['yes'])}</span>{spark(hist.get(p['market']))}</li>")
    up = sorted((p for p in movers if p["d1"] > 0), key=lambda p: -p["d1"])[:6]
    dn = sorted((p for p in movers if p["d1"] < 0), key=lambda p: p["d1"])[:6]
    mv = (f"<div class=cols><div><h2>Gaining today</h2><ul class=mv>{''.join(card(p) for p in up) or '<li>No gainers yet.</li>'}</ul></div>"
          f"<div><h2>Falling today</h2><ul class=mv>{''.join(card(p) for p in dn) or '<li>No decliners yet.</li>'}</ul></div></div>")
    bigmove = f"{'+' if best['d1']>0 else '-'}{abs(best['d1'])*100:.1f} pts" if best else "–"
    chips = "".join(f"<button class=chip data-f='{c}' aria-pressed={'true' if c=='All' else 'false'}>{c}</button>" for c in ("All", "Senate", "House", "Governor", "Control", "Decided"))
    data = json.dumps([dict(q=p["market"], y=p["yes"]) for p in pool]).replace("</", "<\\/")
    page = TEMPLATE
    for k, v in {"__UPDATED__": mk.get("updated", ""), "__ISO__": mk.get("iso", ""), "__TOTAL__": f"{total:,.0f}",
                 "__V24__": f"{v24:,.0f}", "__BIG__": bigmove, "__TAPE__": tape, "__ROWS__": body, "__MOVERS__": mv,
                 "__CHIPS__": chips, "__HOUSE__": gauge("House", control(pool, "house")),
                 "__SENATE__": gauge("Senate", control(pool, "senate")), "__DATA__": data}.items():
        page = page.replace(k, v)
    return page

TEMPLATE = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Girls Go Midterm Poly Markets</title>
<meta name=description content="A free, just-for-fun dashboard of the biggest 2026 midterm markets on Polymarket. Aggregate data only. Not financial or betting advice.">
<meta property=og:title content="Girls Go Midterm Poly Markets"><meta property=og:type content=website>
<meta property=og:description content="Live odds, price moves and a beginner guide for the 2026 midterm markets on Polymarket. Just for fun and research.">
<link rel=preconnect href=https://fonts.googleapis.com><link rel=stylesheet href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=Bricolage+Grotesque:wght@700&display=swap">
<style>
:root{--bg:#ffeef6;--ink:#3a0f2b;--mute:#7d4d6b;--line:#f6cfe3;--card:#fffafc;--acc:#c9206f;--pos:#0f7b5f;--neg:#c0281e;--dem:#2f5bea}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#1d0a16;--ink:#ffe6f2;--mute:#c493ae;--line:#43182f;--card:#2a0f20;--acc:#ff6fb5;--pos:#3ecf9e;--neg:#ff8a7a;--dem:#7c9bff}}
*{box-sizing:border-box}html,body{margin:0}body{background:var(--bg);color:var(--ink);font:15px/1.5 'IBM Plex Sans',system-ui,sans-serif;padding:0 0 40px}
.tape{background:var(--acc);color:#fff;overflow:hidden;white-space:nowrap;padding:max(8px,env(safe-area-inset-top)) 0 8px;font-size:13px}
.tape div{display:inline-block;animation:slide 60s linear infinite}.tape:hover div{animation-play-state:paused}
.tk{margin:0 22px}.tk em{font-style:normal;font-weight:600}.tape .pos,.tape .neg{color:#fff}@keyframes slide{to{transform:translateX(-50%)}}
main{max-width:1040px;margin:24px auto 0;padding:0 20px}h1{font:700 34px 'Bricolage Grotesque','IBM Plex Sans',sans-serif;margin:0 0 4px;color:var(--acc)}
h2{font:700 18px 'Bricolage Grotesque','IBM Plex Sans',sans-serif;margin:0 0 8px;color:var(--acc)}h3{margin:20px 0 4px;font-size:15px}
header.top{display:flex;align-items:flex-end;justify-content:space-between;gap:12px 24px;flex-wrap:wrap;border-bottom:1px solid var(--line);margin-bottom:12px}
.nav{display:flex;gap:4px;flex-wrap:wrap}.nav button{font:600 14px 'IBM Plex Sans',sans-serif;background:none;border:0;border-bottom:3px solid transparent;padding:8px 12px;color:var(--mute);cursor:pointer;margin-bottom:-1px}
.nav button:hover{color:var(--ink)}.nav button[aria-current=page]{color:var(--acc);border-bottom-color:var(--acc)}
.sub{color:var(--mute);margin:0 0 16px;max-width:70ch}.stats{display:flex;gap:32px;flex-wrap:wrap;margin-bottom:20px}
.stats div{font-size:13px;color:var(--mute)}.stats b{display:block;font-size:24px;color:var(--ink);font-variant-numeric:tabular-nums}
.gauges{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;margin-bottom:24px}
.g{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;font-size:13px}.g b{display:block;font-size:15px}
.gb{height:12px;border-radius:99px;background:var(--neg);margin:8px 0;overflow:hidden}.gb i{display:block;height:100%;background:var(--dem)}
.g u{text-decoration:none;color:var(--dem);font-weight:600}.g s{text-decoration:none;color:var(--neg);font-weight:600;float:right}.sub2{color:var(--mute)}
aside.banner{background:var(--neg);color:#fff;padding:8px 14px;border-radius:8px;margin-bottom:16px;font-size:13px}
aside.disc{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--acc);border-radius:8px;padding:10px 14px;margin:0 0 20px;font-size:13px;color:var(--mute);max-width:78ch}aside.disc b{color:var(--ink)}
.tabs,.chips{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}
.tabs button,.chip{font:600 14px 'IBM Plex Sans',sans-serif;padding:8px 18px;border-radius:99px;border:1px solid var(--line);background:var(--card);color:var(--mute);cursor:pointer}
.chip{padding:5px 14px;font-size:13px}.tabs button[aria-selected=true],.chip[aria-pressed=true]{background:var(--acc);border-color:var(--acc);color:#fff}
button:focus-visible,th:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.wrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;min-width:1000px;font-variant-numeric:tabular-nums}
th,td{padding:10px 12px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th{font-weight:600;color:var(--mute);font-size:13px;cursor:pointer;position:sticky;top:0;background:var(--card)}
td:nth-child(2),th:nth-child(2){text-align:left}td:first-child,th:first-child{text-align:center;color:var(--mute)}
td.bet{white-space:normal;min-width:240px}td.bet a{color:var(--ink);text-decoration:none;font-weight:600}td.bet a:hover{color:var(--acc)}
small{display:block;color:var(--mute);font-size:12px}tr:last-child td{border-bottom:0}tbody tr:hover{background:color-mix(in srgb,var(--acc) 8%,transparent)}
.thin{border:1px solid var(--neg);color:var(--neg);border-radius:99px;padding:0 7px;font-size:11px;font-weight:600;margin-left:4px}
.pos{color:var(--pos)}.neg{color:var(--neg)}td.pos,td.neg{background:color-mix(in srgb,currentColor calc(var(--i,0)*22%),transparent);font-weight:600}
.bar{position:relative;min-width:120px}.bar i{position:absolute;left:0;top:6px;bottom:6px;background:var(--acc);opacity:.22;border-radius:0 3px 3px 0}.bar b{position:relative;font-weight:600}
.spark{display:block;margin-left:auto}.spark polyline{fill:none;stroke:currentColor;stroke-width:2;stroke-linejoin:round;stroke-dasharray:1;animation:draw 1.4s ease-out}
@keyframes draw{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:20px}
ul.mv{list-style:none;margin:0;padding:0;background:var(--card);border:1px solid var(--line);border-radius:8px}
ul.mv li{display:grid;grid-template-columns:1fr auto auto 90px;gap:12px;align-items:center;padding:10px 14px;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}
ul.mv li:last-child{border:0}ul.mv a{color:var(--ink);text-decoration:none;font-weight:600}ul.mv .px{color:var(--mute)}
.prose{max-width:72ch}.prose dt{font-weight:600;margin-top:10px}.prose dd{margin:0;color:var(--mute)}.prose li{margin:4px 0}.prose a{color:var(--acc)}
.chest{position:relative;overflow:hidden;background:linear-gradient(135deg,#c9206f,#6d1250);color:#fff;border-radius:12px;padding:18px 20px;margin:12px 0}
.chest small{display:block;opacity:.85;color:#fff;font-size:12px}.chest .big b{font:700 44px 'Bricolage Grotesque','IBM Plex Sans',sans-serif;margin-right:4px}
.cs{display:flex;gap:28px;flex-wrap:wrap;margin-top:8px}.cs div{font-size:12px}.cs b{display:block;font-size:20px;font-variant-numeric:tabular-nums}.chest .pos,.chest .neg{color:#fff}
.coin{position:absolute;top:-28px;font-size:22px;pointer-events:none;animation:drop 1.2s ease-in forwards}@keyframes drop{to{transform:translateY(190px) rotate(360deg);opacity:0}}
table.cmp{min-width:0}table.cmp th,table.cmp td{text-align:left;white-space:normal;vertical-align:top}table.cmp thead th{position:static;cursor:default}table.cmp tbody th{color:var(--ink);font-size:14px;width:26%}table.cmp td:first-child,table.cmp th:first-child{text-align:left;color:inherit}
.form{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.form select,.form input,.form button{font:inherit;padding:7px 10px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
.form select{max-width:100%;min-width:220px;flex:1}.form button{background:var(--acc);color:#fff;border-color:var(--acc);font-weight:600;cursor:pointer}
p.note{color:var(--mute);font-size:13px;max-width:72ch;margin:16px 0}[hidden]{display:none!important}
footer{max-width:1040px;margin:0 auto;padding:0 20px;color:var(--mute);font-size:12px}
@media(max-width:700px){table{min-width:0}#t th:nth-child(6),#t td:nth-child(6),#t th:nth-child(8),#t td:nth-child(8),#t th:nth-child(11),#t td:nth-child(11),#t th:nth-child(1),#t td:nth-child(1){display:none}th,td{padding:8px 6px}h1{font-size:26px}}
@media(prefers-reduced-motion:reduce){.tape{overflow-x:auto}.tape div{animation:none}.spark polyline{animation:none}}
</style></head><body>
<div class=tape aria-label="Market ticker"><div>__TAPE____TAPE__</div></div>
<main>
<header class=top><h1>Girls Go Midterm Poly Markets</h1>
<nav class=nav aria-label="Site pages"><button data-v=dash aria-current=page>Dashboard</button><button data-v=start aria-current=false>Start here</button><button data-v=practice aria-current=false>Practice</button><button data-v=about aria-current=false>About</button></nav></header>
<p class=sub>The biggest 2026 midterm markets on Polymarket, with how their odds are moving. Updated <time id=ago datetime="__ISO__">__UPDATED__</time>. <b id=eday></b></p>
<aside class=banner id=stale hidden>This data may be out of date. The last update was more than 3 hours ago.</aside>
<aside class=disc role=note><b>Just for fun and research.</b> This page only aggregates publicly available data from Polymarket. It is not financial advice, not betting advice, and not a recommendation to buy or sell anything. Prediction markets carry real risk, so do your own research.</aside>
<div id=v-dash>
<div class=gauges>__HOUSE____SENATE__</div>
<div class=stats><div>Total volume<b>__TOTAL__</b></div><div>Traded in 24h<b>__V24__</b></div><div>Biggest 24h move<b>__BIG__</b></div></div>
<div class=tabs role=tablist aria-label="Chart view"><button role=tab id=tab-m aria-selected=true aria-controls=p-m>Markets</button><button role=tab id=tab-v aria-selected=false aria-controls=p-v>Movers</button></div>
<section id=p-m role=tabpanel aria-labelledby=tab-m>
<div class=chips>__CHIPS__</div>
<div class=wrap><table id=t><thead><tr><th>#</th><th>Market</th><th>Yes odds</th><th>24h</th><th>7d</th><th>30d</th><th>7d trend</th><th>Volume</th><th>Liquidity</th><th>Spread</th><th>Ends</th></tr></thead><tbody>__ROWS__</tbody></table></div>
<p class=note>Yes odds are Polymarket's current price for Yes. 24h, 7d and 30d are changes in percentage points. Spread is in points. A "thin" tag means low liquidity or a wide spread. Markets priced under 1% or over 99% (for example candidates knocked out in a primary) are treated as decided. They are hidden from the ranking and shown under the Decided button. Click a column to sort and a market to open it on Polymarket.</p></section>
<section id=p-v role=tabpanel aria-labelledby=tab-v hidden>__MOVERS__
<p class=note>Biggest 24-hour moves among the 60 most traded midterm markets. A big move on thin volume can reverse fast, so check liquidity before reading much into it.</p></section>
</div>
<section id=v-start class=prose hidden>
<h2>Start here</h2>
<p><b>Before anything else:</b> most people lose money on prediction markets, and this page is not encouraging anyone to bet. Check that Polymarket is available where you live and that you meet its age requirement. Never use money you can't afford to lose.</p>
<p><b>A note on platforms:</b> this guide is written with Polymarket in mind, but most prediction markets run on the same basic idea. Prices sit between $0 and $1 and reflect the odds, and shares pay out $1 or $0 when the question resolves. Details like fees, rules, who is allowed to use them, and how disputes get settled differ from platform to platform, so read the rules of whichever one you use.</p>
<h3>How a market works</h3>
<p>A market asks a yes-or-no question, like "Will Democrats win control of the House?" Each share of Yes costs between 0 and $1 and pays $1 if the answer is Yes, and nothing if it's No. A price of 62¢ means the market thinks Yes is about 62% likely. Buying Yes at 62¢ risks 62¢ to win 38¢. Buying No at 38¢ is the mirror image.</p>
<h3>A Polymarket pick vs. owning a stock</h3>
<p>On a screen they can look alike. Both have a price that moves, and you can buy and sell both. But they're really different things.</p>
<p><b>When you own a stock, you own a tiny slice of a real company.</b> Its value follows how the business does: sales, profits, new products, the wider economy. There's no finish line. You can hold it for a week or for twenty years, and it never "resolves." That's why buying stocks is usually called investing. You're backing a company's ability to grow over time, though nothing is guaranteed and prices can fall as well as rise.</p>
<p><b>A Polymarket pick is a bet on how likely something is to happen.</b> You don't own anything. You're saying "I think this outcome is more (or less) likely than the crowd does." And there's a deadline. Until then, the price of a share moves between 0¢ and $1 as people's views change, and you can sell any time at the current price without waiting for the result. But the price is always being pulled toward the end: when the question resolves, your share becomes worth exactly $1 if you were right or $0 if you were wrong. Nothing grows in the background while you wait, and one side's win is the other side's loss.</p>
<div class=wrap><table class=cmp><thead><tr><th></th><th>Owning a stock</th><th>A Polymarket pick</th></tr></thead><tbody>
<tr><th>What you hold</th><td>A small piece of a company</td><td>A share of an outcome (Yes or No)</td></tr>
<tr><th>What moves the price</th><td>How the business and the market are doing</td><td>New information about how likely the outcome is</td></tr>
<tr><th>End date</th><td>None. Hold as long as you like</td><td>Yes. It resolves, then pays $1 or $0</td></tr>
<tr><th>Best case</th><td>No set limit</td><td>Capped at $1 per share, since the price can't go higher</td></tr>
<tr><th>Worst case</th><td>Can fall a lot, and some companies fail</td><td>Can drop to zero quickly</td></tr>
<tr><th>Where gains come from</th><td>The company's profits and growth over time, with no guarantees</td><td>Being right, or spotting a shift in the odds before others do. You can sell early, but the price still heads to $1 or $0 at the end</td></tr>
</tbody></table></div>
<p>Neither one is "better." They're different tools. Stocks are usually for patient, long-term money. Prediction markets are short, all-or-nothing questions about what will happen, which is why the Practice page keeps the stakes pretend. And just like everything on this page, none of this is advice either way.</p>
<h3>Reading this dashboard</h3>
<dl><dt>Yes odds</dt><dd>The current price of Yes, read as a probability.</dd>
<dt>24h / 7d / 30d</dt><dd>How many percentage points the price has moved over that time.</dd>
<dt>Volume</dt><dd>Total money traded in the market so far. More volume usually means a more reliable price.</dd>
<dt>Liquidity and spread</dt><dd>Liquidity is how much is available to trade. Spread is the gap between the best buy and sell price. A wide spread means you lose some value just entering and exiting.</dd>
<dt>Resolution</dt><dd>When the question is settled and winners get paid. "Ends" is the scheduled date, which can change.</dd></dl>
<h3>Mistakes worth avoiding</h3>
<ul><li>Buying a long shot because the payout looks big. Cheap usually means unlikely.</li>
<li>Putting a lot into one race, or several races that move together. If the national mood shifts, they all lose at once.</li>
<li>Trading thin markets. Check the "thin" tag and the spread first.</li>
<li>Chasing a big move. Prices that jump on little volume often snap back.</li>
<li>Not reading the resolution rules. The exact wording decides who gets paid, so read it on the market page.</li></ul>
<h3>Election calendar</h3>
<p>Election Day is Tuesday, November 3, 2026. Registration and early voting deadlines differ by state, so check your state's official election site, or start at <a href="https://vote.gov" target=_blank rel=noopener>vote.gov</a>.</p></section>
<section id=v-practice class=prose hidden>
<h2>🏴‍☠️ Practice cove</h2>
<p>Ahoy! You start with <b>1,000 doubloons</b>. They're pretend money with no real value. Pick a market, choose Yes or No, and spend some doubloons. Cash out any time to bank your winnings or cut your losses. Everything is saved in this browser only.</p>
<div class=chest id=chest aria-live=polite>
<div class=big><small>Treasure chest</small><b id=c-net>1,000</b> 🪙</div>
<div class=cs><div>In your pocket<b id=c-cash>1,000</b></div><div>On the table<b id=c-play>0</b></div><div>Profit / loss<b id=c-pl>+0</b></div><div>Your rank<b id=c-rank></b></div></div></div>
<div class=form><select id=pk-m aria-label=Market></select><select id=pk-s aria-label=Side><option>Yes</option><option>No</option></select><input id=pk-a type=number min=1 step=1 value=100 aria-label="Doubloons to spend"><button id=pk-add>Place pick 🪙</button></div>
<p class=note id=pk-p></p><p class=note id=pk-e role=status></p>
<div class=wrap><table style="min-width:0"><thead><tr><th style="text-align:left">Your pick</th><th>Price now</th><th>Doubloons +/−</th><th></th></tr></thead><tbody id=pk-b></tbody></table></div>
<p class=note id=pk-t></p>
<button class=chip id=pk-reset>Start over with 1,000 doubloons</button></section>
<section id=v-about class=prose hidden>
<h2>About and methods</h2>
<p>This is a personal, just-for-fun project. It is not affiliated with or endorsed by Polymarket.</p>
<ul><li><b>Source:</b> Polymarket's public data, pulled automatically about once an hour. The page also reloads itself every 15 minutes.</li>
<li><b>Which markets:</b> open 2026 markets whose question mentions Senate, House, Governor, Congress or midterms, ranked by total volume. The table shows the top 20 that are still undecided, and markets priced under 1% or over 99% go under the Decided button.</li>
<li><b>Control gauges:</b> taken from the most traded "control of" market for each chamber. If no match is found, the gauge says so.</li>
<li><b>Changes and trends:</b> price changes come from Polymarket's own figures and the 7-day lines from its price history. Missing values show as a dash.</li>
<li><b>Accuracy:</b> data is not verified by this site and may be delayed or wrong. Always check the market on Polymarket.</li></ul></section>
</main>
<footer>Data comes from Polymarket's public API and is not verified by this site. Not financial or betting advice. A fun way to help with Polymarket research.</footer>
<script>
window.MK=__DATA__;
const nav=[...document.querySelectorAll('.nav button')],dt=[...document.querySelectorAll('[role=tab]')],views=['dash','start','practice','about'];
function route(){let h=location.hash.slice(1)||'dash';const mov=h=='movers';if(mov)h='dash';if(!views.includes(h))h='dash';
views.forEach(v=>document.getElementById('v-'+v).hidden=v!=h);nav.forEach(b=>b.setAttribute('aria-current',b.dataset.v==h?'page':'false'));
dt.forEach(t=>{const on=(t.id=='tab-v')==mov;t.setAttribute('aria-selected',on);document.getElementById(t.getAttribute('aria-controls')).hidden=!on})}
nav.forEach(b=>b.onclick=()=>{location.hash=b.dataset.v});dt.forEach(t=>t.onclick=()=>{location.hash=t.id=='tab-v'?'movers':'dash'});
addEventListener('hashchange',route);route();
const ago=document.getElementById('ago'),stamp=Date.parse(ago.getAttribute('datetime'));
const tick=()=>{if(isNaN(stamp))return;const m=Math.max(0,Math.round((Date.now()-stamp)/60000));ago.textContent=m<1?'just now':m<60?m+' min ago':Math.round(m/60)+' hr ago';document.getElementById('stale').hidden=m<180};tick();setInterval(tick,30000);
const d=Math.ceil((Date.UTC(2026,10,3,12)-Date.now())/864e5);document.getElementById('eday').textContent=d>0?'Election Day is in '+d+' days.':d==0?'Election Day is today.':'';
setTimeout(function r(){document.hidden?setTimeout(r,60000):location.reload()},15*60*1000);
const rows=()=>[...document.querySelectorAll('#t tbody tr')];
document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{document.querySelectorAll('.chip').forEach(o=>o.setAttribute('aria-pressed',o===c));rows().forEach(r=>r.hidden=c.dataset.f=='Decided'?r.dataset.dec!='1':(r.dataset.dec=='1'||(c.dataset.f!='All'&&r.dataset.cat!=c.dataset.f)))});
document.querySelectorAll('#t th').forEach((h,i)=>{h.tabIndex=0;const s=()=>{const b=document.querySelector('#t tbody'),d=h.dataset.d=h.dataset.d=='1'?'-1':'1';
const v=r=>{const c=r.cells[i];return c.dataset.v!==undefined?parseFloat(c.dataset.v):c.innerText};
[...b.rows].sort((x,y)=>{const a=v(x),c=v(y);return (typeof a=='number'&&typeof c=='number'?a-c:String(a).localeCompare(String(c)))*d}).forEach(r=>b.append(r))};h.onclick=s;h.onkeydown=e=>e.key=='Enter'&&s()});
const K='ggm_chest',START=1000;let W={cash:START,picks:[]};
try{const x=JSON.parse(localStorage.getItem(K)||'null');if(x&&typeof x.cash=='number'&&Array.isArray(x.picks))W=x}catch(e){}
const save=()=>{try{localStorage.setItem(K,JSON.stringify(W))}catch(e){}};
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $=id=>document.getElementById(id),fmt=n=>Math.round(n).toLocaleString(),px=y=>y<.01?'<1¢':y>.99?'>99¢':Math.round(y*100)+'¢';
const calm=()=>matchMedia('(prefers-reduced-motion:reduce)').matches;
const sel=$('pk-m');MK.forEach((m,i)=>sel.add(new Option(m.q.slice(0,80)+' ('+Math.round(m.y*100)+'%)',i)));
const rank=n=>n>=1500?'👑 Pirate Queen':n>=1200?'⚓ Captain':n>=1000?'🧭 First Mate':n>=700?'🪢 Deckhand':'🌊 Shipwrecked';
const cur=p=>{const m=MK.find(x=>x.q==p.q);if(m)p.last=p.side=='Yes'?m.y:1-m.y;return p.last};
function pop(n){if(calm())return;const c=$('chest');for(let i=0;i<n;i++){const s=document.createElement('span');s.className='coin';s.textContent='🪙';s.style.left=(8+Math.random()*84)+'%';s.style.animationDelay=(i*90)+'ms';c.append(s);setTimeout(()=>s.remove(),1500)}}
let shown=0;function count(n){const el=$('c-net'),from=shown,t0=performance.now();shown=n;if(calm()){el.textContent=fmt(n);return}
(function f(t){const k=Math.min(1,(t-t0)/600);el.textContent=fmt(from+(n-from)*k);if(k<1)requestAnimationFrame(f)})(t0)}
function preview(){const m=MK[+sel.value],side=$('pk-s').value,amt=Math.floor(parseFloat($('pk-a').value)),el=$('pk-p');
if(!m||!(amt>0)){el.textContent='';return}const e=side=='Yes'?m.y:1-m.y;if(e<=.01||e>=.99){el.textContent='That side is basically decided, so pick a market that is still open.';return}
el.textContent='At '+px(e)+', '+fmt(amt)+' doubloons buys '+fmt(amt/e)+' shares. If '+side+' wins you collect '+fmt(amt/e)+' doubloons (+'+fmt(amt/e-amt)+'). If not, you lose all '+fmt(amt)+'.'}
function draw(){let play=0,top=0;
$('pk-b').innerHTML=W.picks.map((p,i)=>{const c=cur(p),v=p.amt*c/p.entry,d=v-p.amt;play+=v;top=Math.max(top,v);
return '<tr><td style="text-align:left;white-space:normal">'+esc(p.q)+'<small>'+p.side+' · '+fmt(p.amt)+' doubloons at '+px(p.entry)+'</small></td><td>'+px(c)+'</td><td class='+(d>=0?'pos':'neg')+'>'+(d>=0?'+':'−')+fmt(Math.abs(d))+'</td><td><button class=chip data-i='+i+'>Cash out '+fmt(v)+'</button></td></tr>'}).join('')
||'<tr><td colspan=4 style="text-align:center">No picks yet. Choose a market above!</td></tr>';
const net=W.cash+play,pl=net-START;
$('c-cash').textContent=fmt(W.cash);$('c-play').textContent=fmt(play);$('c-pl').textContent=(pl>=0?'+':'−')+fmt(Math.abs(pl));$('c-pl').className=pl>=0?'pos':'neg';$('c-rank').textContent=rank(net);count(net);
$('pk-t').textContent=W.picks.length&&top/net>.5?'Heads up: over half your chest is riding on one market. Spreading your picks lowers the risk.':'';
document.querySelectorAll('#pk-b button').forEach(b=>b.onclick=()=>{const p=W.picks[+b.dataset.i],v=p.amt*cur(p)/p.entry;W.cash+=v;W.picks.splice(+b.dataset.i,1);save();draw();pop(v>p.amt?8:2)})}
$('pk-add').onclick=()=>{const m=MK[+sel.value],side=$('pk-s').value,amt=Math.floor(parseFloat($('pk-a').value)),msg=$('pk-e');msg.textContent='';
if(!m||!(amt>=1))return;const e=side=='Yes'?m.y:1-m.y;if(e<=.01||e>=.99){msg.textContent='That side is basically decided. Pick a market that is still open.';return}
if(amt>W.cash){msg.textContent='Not enough doubloons. You have '+fmt(W.cash)+'.';return}
W.cash-=amt;W.picks.push({q:m.q,side,amt,entry:e,last:e});save();draw();pop(5)};
$('pk-reset').onclick=()=>{if(confirm('Start over with a fresh 1,000 doubloons? Your current picks will be cleared.')){W={cash:START,picks:[]};save();draw()}};
['pk-m','pk-s','pk-a'].forEach(id=>$(id).addEventListener('input',preview));preview();draw();
</script></body></html>"""

if __name__ == "__main__":
    main()
