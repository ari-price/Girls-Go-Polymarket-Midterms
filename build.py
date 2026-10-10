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
    pool = mk["pool"]; rows = pool[:TOP_N]
    total = sum(r["volume"] for r in rows) or 1
    v24 = sum(r["vol24"] for r in rows)
    movers = [p for p in pool if p["d1"] is not None]
    best = max(movers, key=lambda p: abs(p["d1"]), default=None)
    body = ""
    for i, m in enumerate(rows, 1):
        share = m["volume"] / total * 100
        flag = "<span class=thin title='Low liquidity or wide spread: prices may be hard to trade at'>thin</span>" if thin(m) else ""
        liq = "–" if m["liq"] is None else f"{m['liq']:,.0f}"
        sp = "–" if m["spread"] is None else f"{m['spread']*100:.1f}"
        body += (f"<tr data-cat='{m['cat']}'><td>{i}</td><td class=bet><a href='{html.escape(m['url'])}' target=_blank rel=noopener>{html.escape(m['market'])}</a><small>{m['cat']} {flag}</small></td>"
                 f"<td data-v={m['yes']:.4f}>{m['yes']*100:.0f}%</td>{chg(m['d1'])}{chg(m['d7'])}{chg(m['d30'])}"
                 f"<td class=sp>{spark(m.get('hist'))}</td>"
                 f"<td class=bar data-v={m['volume']:.0f}><i style='width:{min(share*2.5,100):.0f}%'></i><b>{m['volume']:,.0f}</b></td>"
                 f"<td data-v={m['liq'] or 0:.0f}>{liq}</td><td data-v={m['spread'] or 0:.4f}>{sp}</td><td>{html.escape(m['end'] or '–')}</td></tr>")
    body = body or "<tr><td></td><td class=bet>No data yet. The next scheduled run will fill this in.</td>" + "<td></td>" * 9 + "</tr>"
    def tk(r):
        d = r["d1"]
        e = "" if d is None else f"<em class={'pos' if d>0 else 'neg' if d<0 else ''}>{'▲' if d>0 else '▼' if d<0 else ''} {abs(d)*100:.1f}</em>"
        return f"<span class=tk><b>{short(r['market'], 32)}</b> {r['yes']*100:.0f}% {e}</span>"
    tape = "".join(tk(r) for r in rows)
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
.form{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.form select,.form input,.form button{font:inherit;padding:7px 10px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
.form select{max-width:100%;min-width:220px;flex:1}.form button{background:var(--acc);color:#fff;border-color:var(--acc);font-weight:600;cursor:pointer}
p.note{color:var(--mute);font-size:13px;max-width:72ch;margin:16px 0}[hidden]{display:none!important}
footer{max-width:1040px;margin:0 auto;padding:0 20px;color:var(--mute);font-size:12px}
@media(max-width:700px){table{min-width:0}th:nth-child(6),td:nth-child(6),th:nth-child(8),td:nth-child(8),th:nth-child(11),td:nth-child(11),th:nth-child(1),td:nth-child(1){display:none}th,td{padding:8px 6px}h1{font-size:26px}}
@media(prefers-reduced-motion:reduce){.tape{overflow-x:auto}.tape div{animation:none}.spark polyline{animation:none}}
</style></head><body>
<div class=tape aria-label="Market ticker"><div>__TAPE____TAPE__</div></div>
<main>
<h1>Girls Go Midterm Poly Markets</h1>
<p class=sub>The biggest 2026 midterm markets on Polymarket, with how their odds are moving. Updated <time id=ago datetime="__ISO__">__UPDATED__</time>. <b id=eday></b></p>
<aside class=banner id=stale hidden>This data may be out of date. The last update was more than 3 hours ago.</aside>
<aside class=disc role=note><b>Just for fun and research.</b> This page only aggregates publicly available data from Polymarket. It is not financial advice, not betting advice, and not a recommendation to buy or sell anything. Prediction markets carry real risk, so do your own research.</aside>
<div class=gauges>__HOUSE____SENATE__</div>
<div class=stats><div>Total volume<b>__TOTAL__</b></div><div>Traded in 24h<b>__V24__</b></div><div>Biggest 24h move<b>__BIG__</b></div></div>
<div class=tabs role=tablist><button role=tab id=tab-m aria-selected=true aria-controls=p-m>Markets</button><button role=tab id=tab-v aria-selected=false aria-controls=p-v>Movers</button><button role=tab id=tab-s aria-selected=false aria-controls=p-s>Start here</button><button role=tab id=tab-p aria-selected=false aria-controls=p-p>Practice</button><button role=tab id=tab-a aria-selected=false aria-controls=p-a>About</button></div>
<section id=p-m role=tabpanel aria-labelledby=tab-m>
<div class=chips>__CHIPS__</div>
<div class=wrap><table id=t><thead><tr><th>#</th><th>Market</th><th>Yes odds</th><th>24h</th><th>7d</th><th>30d</th><th>7d trend</th><th>Volume</th><th>Liquidity</th><th>Spread</th><th>Ends</th></tr></thead><tbody>__ROWS__</tbody></table></div>
<p class=note>Yes odds are Polymarket's current price for Yes. 24h, 7d and 30d are changes in percentage points. Spread is in points. A "thin" tag means low liquidity or a wide spread. Click a column to sort and a market to open it on Polymarket.</p></section>
<section id=p-v role=tabpanel aria-labelledby=tab-v hidden>__MOVERS__
<p class=note>Biggest 24-hour moves among the 60 most traded midterm markets. A big move on thin volume can reverse fast, so check liquidity before reading much into it.</p></section>
<section id=p-s role=tabpanel aria-labelledby=tab-s class=prose hidden>
<h2>Start here</h2>
<p><b>Before anything else:</b> most people lose money on prediction markets, and this page is not encouraging anyone to bet. Check that Polymarket is available where you live and that you meet its age requirement. Never use money you can't afford to lose.</p>
<h3>How a market works</h3>
<p>A market asks a yes-or-no question, like "Will Democrats win control of the House?" Each share of Yes costs between 0 and $1 and pays $1 if the answer is Yes, and nothing if it's No. A price of 62¢ means the market thinks Yes is about 62% likely. Buying Yes at 62¢ risks 62¢ to win 38¢. Buying No at 38¢ is the mirror image.</p>
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
<section id=p-p role=tabpanel aria-labelledby=tab-p class=prose hidden>
<h2>Practice with fake money</h2>
<p>Pick a market, choose Yes or No, and enter a pretend amount. This tracks how your pick would be doing at today's price. Picks are saved only in this browser and never sent anywhere.</p>
<div class=form><select id=pk-m aria-label=Market></select><select id=pk-s aria-label=Side><option>Yes</option><option>No</option></select><input id=pk-a type=number min=1 value=100 aria-label="Pretend amount in dollars"><button id=pk-add>Add pick</button></div>
<div class=wrap><table style="min-width:0"><thead><tr><th style="text-align:left">Pick</th><th>Entry</th><th>Now</th><th>Pretend P&amp;L</th><th></th></tr></thead><tbody id=pk-b></tbody></table></div>
<p class=note id=pk-t></p></section>
<section id=p-a role=tabpanel aria-labelledby=tab-a class=prose hidden>
<h2>About and methods</h2>
<p>This is a personal, just-for-fun project. It is not affiliated with or endorsed by Polymarket.</p>
<ul><li><b>Source:</b> Polymarket's public data, pulled automatically about once an hour. The page also reloads itself every 15 minutes.</li>
<li><b>Which markets:</b> open 2026 markets whose question mentions Senate, House, Governor, Congress or midterms, ranked by total volume. The table shows the top 20.</li>
<li><b>Control gauges:</b> taken from the most traded "control of" market for each chamber. If no match is found, the gauge says so.</li>
<li><b>Changes and trends:</b> price changes come from Polymarket's own figures and the 7-day lines from its price history. Missing values show as a dash.</li>
<li><b>Accuracy:</b> data is not verified by this site and may be delayed or wrong. Always check the market on Polymarket.</li></ul></section>
</main>
<footer>Data comes from Polymarket's public API and is not verified by this site. Not financial or betting advice. A fun way to help with Polymarket research.</footer>
<script>
window.MK=__DATA__;
const tabs=[...document.querySelectorAll('[role=tab]')];
const show=t=>tabs.forEach(o=>{const on=o===t;o.setAttribute('aria-selected',on);document.getElementById(o.getAttribute('aria-controls')).hidden=!on});
tabs.forEach(t=>t.onclick=()=>{show(t);history.replaceState(null,'','#'+t.id)});
const first=tabs.find(t=>'#'+t.id==location.hash);if(first)show(first);
const ago=document.getElementById('ago'),stamp=Date.parse(ago.getAttribute('datetime'));
const tick=()=>{if(isNaN(stamp))return;const m=Math.max(0,Math.round((Date.now()-stamp)/60000));ago.textContent=m<1?'just now':m<60?m+' min ago':Math.round(m/60)+' hr ago';document.getElementById('stale').hidden=m<180};tick();setInterval(tick,30000);
const d=Math.ceil((Date.UTC(2026,10,3,12)-Date.now())/864e5);document.getElementById('eday').textContent=d>0?'Election Day is in '+d+' days.':d==0?'Election Day is today.':'';
setTimeout(function r(){document.hidden?setTimeout(r,60000):location.reload()},15*60*1000);
const rows=()=>[...document.querySelectorAll('#t tbody tr')];
document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{document.querySelectorAll('.chip').forEach(o=>o.setAttribute('aria-pressed',o===c));rows().forEach(r=>r.hidden=c.dataset.f!='All'&&r.dataset.cat!=c.dataset.f)});
document.querySelectorAll('#t th').forEach((h,i)=>{h.tabIndex=0;const s=()=>{const b=document.querySelector('#t tbody'),d=h.dataset.d=h.dataset.d=='1'?'-1':'1';
const v=r=>{const c=r.cells[i];return c.dataset.v!==undefined?parseFloat(c.dataset.v):c.innerText};
[...b.rows].sort((x,y)=>{const a=v(x),c=v(y);return (typeof a=='number'&&typeof c=='number'?a-c:String(a).localeCompare(String(c)))*d}).forEach(r=>b.append(r))};h.onclick=s;h.onkeydown=e=>e.key=='Enter'&&s()});
const K='ggm_picks';let picks=[];try{picks=JSON.parse(localStorage.getItem(K)||'[]')}catch(e){}
const save=()=>{try{localStorage.setItem(K,JSON.stringify(picks))}catch(e){}};
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const sel=document.getElementById('pk-m');MK.forEach((m,i)=>sel.add(new Option(m.q.slice(0,90),i)));
function draw(){let val=0,cost=0;document.getElementById('pk-b').innerHTML=picks.map((p,i)=>{const m=MK.find(x=>x.q==p.q),cur=m?(p.side=='Yes'?m.y:1-m.y):null;
let pl='–';if(cur!=null){const v=p.amt*cur/p.entry;val+=v;cost+=p.amt;pl=(v-p.amt>=0?'+$':'-$')+Math.abs(v-p.amt).toFixed(2)}
return '<tr><td style="text-align:left;white-space:normal">'+esc(p.q)+'<small>'+p.side+' · $'+p.amt+'</small></td><td>'+(p.entry*100).toFixed(0)+'¢</td><td>'+(cur==null?'–':(cur*100).toFixed(0)+'¢')+'</td><td>'+pl+'</td><td><button class=chip data-i='+i+'>Remove</button></td></tr>'}).join('')||'<tr><td colspan=5 style="text-align:center">No picks yet.</td></tr>';
document.getElementById('pk-t').textContent=picks.length?'Total pretend P&L: '+(val-cost>=0?'+$':'-$')+Math.abs(val-cost).toFixed(2)+'. This is fake money for practice only.':'';
document.querySelectorAll('#pk-b button').forEach(b=>b.onclick=()=>{picks.splice(+b.dataset.i,1);save();draw()})}
document.getElementById('pk-add').onclick=()=>{const m=MK[+sel.value],side=document.getElementById('pk-s').value,amt=parseFloat(document.getElementById('pk-a').value);
if(!m||!(amt>0))return;const e=side=='Yes'?m.y:1-m.y;if(e<=0)return;picks.push({q:m.q,side,amt,entry:e});save();draw()};draw();
</script></body></html>"""

if __name__ == "__main__":
    main()
