"""Aggregate midterm positions across platforms, rank the top 50, write docs/."""
import csv, json, urllib.request, datetime, html, collections

TOP_N, BUY_EDGE, SELL_EDGE = 50, 0.08, -0.05

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "midterm-dashboard"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)

def kalshi_yes(ticker):
    m = get(f"https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}")["market"]
    def c(k):  # handles cents (int) or dollar strings
        v = m.get(k + "_dollars", m.get(k))
        if v in (None, "", 0): return None
        v = float(v)
        return v if k + "_dollars" in m else v / 100
    bid, ask, last = c("yes_bid"), c("yes_ask"), c("last_price")
    return (bid + ask) / 2 if bid and ask else last

def polymarket_yes(slug):
    m = get(f"https://gamma-api.polymarket.com/markets?slug={slug}")[0]
    prices = m["outcomePrices"]
    prices = json.loads(prices) if isinstance(prices, str) else prices
    return float(prices[0])

def live_price(row):
    """Return (price of the side held, source). Falls back to manual price_override."""
    try:
        if row["platform"] == "kalshi" and row["market_id"]:
            yes, src = kalshi_yes(row["market_id"]), "live"
        elif row["platform"] == "polymarket" and row["market_id"]:
            yes, src = polymarket_yes(row["market_id"]), "live"
        else:
            raise ValueError("manual")
        if yes is None: raise ValueError("no quote")
        return (yes if row["side"] == "YES" else 1 - yes), src
    except Exception:
        return float(row["price_override"] or row["avg_price"]), "manual"

def call(edge):
    if edge is None: return "No view"
    return "Buy" if edge >= BUY_EDGE else "Sell" if edge <= SELL_EDGE else "Hold"

def main():
    groups = collections.OrderedDict()
    for row in csv.DictReader(open("positions.csv")):
        sh, avg = float(row["shares"]), float(row["avg_price"])
        px, src = live_price(row)
        g = groups.setdefault(row["bet_on"], dict(bet_on=row["bet_on"], platforms=set(),
            shares=0, cost=0, value=0, probs=[], stale=False, legs=[]))
        g["platforms"].add(row["platform"]); g["shares"] += sh
        g["cost"] += sh * avg; g["value"] += sh * px
        g["stale"] |= src == "manual" and row["platform"] != "susqies"
        if row["my_prob"]: g["probs"].append(float(row["my_prob"]))
        g["legs"].append(row["label"])
    out = []
    for g in groups.values():
        price = g["value"] / g["shares"]
        prob = sum(g["probs"]) / len(g["probs"]) if g["probs"] else None
        edge = None if prob is None else prob - price
        out.append(dict(bet_on=g["bet_on"], platforms=", ".join(sorted(g["platforms"])),
            legs=len(g["legs"]), shares=g["shares"], avg=g["cost"] / g["shares"],
            price=price, value=g["value"], pnl=g["value"] - g["cost"],
            pnl_pct=(g["value"] / g["cost"] - 1) * 100, prob=prob, edge=edge, call=call(edge)))
    out.sort(key=lambda r: -r["value"])
    out = out[:TOP_N]
    total = sum(r["value"] for r in out)
    for i, r in enumerate(out, 1):
        r["rank"], r["share"] = i, r["value"] / total * 100
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%b %d, %Y %H:%M UTC")
    summary = dict(updated=now, total=total, pnl=sum(r["pnl"] for r in out),
                   n=len(out), top3=sum(r["share"] for r in out[:3]))
    json.dump(dict(summary=summary, positions=out), open("docs/data.json", "w"), indent=1)
    open("docs/index.html", "w").write(render(summary, out))
    print(f"{len(out)} bets, total {total:,.0f}, updated {now}")

def render(s, rows):
    def pct(x): return "–" if x is None else f"{x*100:.0f}%"
    def cls(x): return "pos" if x > 0 else "neg" if x < 0 else ""
    body = ""
    for r in rows:
        edge = "–" if r["edge"] is None else f"{r['edge']*100:+.0f}"
        body += (f"<tr><td>{r['rank']}</td><td class=bet>{html.escape(r['bet_on'])}"
          f"<small>{r['legs']} leg{'s' if r['legs']>1 else ''} · {html.escape(r['platforms'])}</small></td>"
          f"<td class=bar><i style='width:{min(r['share']*2.2,100):.0f}%'></i><b>{r['value']:,.0f}</b></td>"
          f"<td>{r['share']:.1f}%</td><td>{r['avg']:.3f}</td><td>{r['price']:.3f}</td>"
          f"<td class={cls(r['pnl'])}>{r['pnl']:+,.0f} ({r['pnl_pct']:+.1f}%)</td>"
          f"<td>{pct(r['prob'])}</td><td class={cls(r['edge'] or 0)}>{edge}</td>"
          f"<td><span class='tag {r['call'].replace(' ','').lower()}'>{r['call']}</span></td></tr>")
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Girls Go Midterm Poly Markets</title>
<link rel=preconnect href=https://fonts.googleapis.com><link rel=stylesheet href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=Bricolage+Grotesque:wght@700&display=swap">
<style>
:root{{--bg:#ffeef6;--ink:#3a0f2b;--mute:#8a5a78;--line:#f6cfe3;--card:#fffafc;--pos:#0f7b5f;--neg:#c0281e;--acc:#e0338a}}
@media(prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#1d0a16;--ink:#ffe6f2;--mute:#c493ae;--line:#43182f;--card:#2a0f20;--pos:#3ecf9e;--neg:#ff8a7a;--acc:#ff6fb5}}}}
*{{box-sizing:border-box}}html,body{{margin:0}}body{{background:var(--bg);color:var(--ink);font:15px/1.5 'IBM Plex Sans',system-ui,sans-serif;padding:max(24px,env(safe-area-inset-top)) 20px 40px}}
main{{max-width:1100px;margin:auto}}h1{{font:700 34px 'Bricolage Grotesque','IBM Plex Sans',sans-serif;margin:0 0 4px;color:var(--acc)}}
.sub{{color:var(--mute);margin:0 0 24px}}.stats{{display:flex;gap:32px;flex-wrap:wrap;margin-bottom:24px}}
.stats div{{font-size:13px;color:var(--mute)}}.stats b{{display:block;font-size:24px;color:var(--ink);font-variant-numeric:tabular-nums}}
.wrap{{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:8px}}
table{{border-collapse:collapse;width:100%;min-width:860px;font-variant-numeric:tabular-nums}}
th,td{{padding:10px 12px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}}
th{{font-weight:600;color:var(--mute);font-size:13px;cursor:pointer;position:sticky;top:0;background:var(--card)}}
th:focus-visible{{outline:2px solid var(--acc)}}td:nth-child(2),th:nth-child(2){{text-align:left}}td:first-child,th:first-child{{text-align:center;color:var(--mute)}}
.bet small{{display:block;color:var(--mute);font-size:12px}}.bar{{position:relative;min-width:110px}}
.bar i{{position:absolute;left:0;top:6px;bottom:6px;background:var(--acc);opacity:.22;border-radius:0 3px 3px 0}}.bar b{{position:relative;font-weight:600}}
.pos{{color:var(--pos)}}.neg{{color:var(--neg)}}tr:last-child td{{border-bottom:0}}
.tag{{padding:2px 9px;border-radius:99px;font-size:12px;font-weight:600;border:1px solid var(--line)}}
.buy{{color:var(--pos);border-color:var(--pos)}}.sell{{color:var(--neg);border-color:var(--neg)}}.noview{{color:var(--mute)}}
p.note{{color:var(--mute);font-size:13px;max-width:70ch;margin-top:16px}}
</style></head><body><main>
<h1>Girls Go Midterm Poly Markets</h1><p class=sub>Top {s['n']} bets by value, positions combined across platforms. Updated {s['updated']}.</p>
<div class=stats><div>Total value<b>{s['total']:,.0f}</b></div><div>Unrealized P&amp;L<b class={cls(s['pnl'])}>{s['pnl']:+,.0f}</b></div><div>Top 3 bets<b>{s['top3']:.0f}% of value</b></div></div>
<div class=wrap><table id=t><thead><tr><th>#</th><th>Bet</th><th>Value</th><th>Share</th><th>Avg cost</th><th>Price</th><th>P&amp;L</th><th>My odds</th><th>Edge (pts)</th><th>Call</th></tr></thead><tbody>{body}</tbody></table></div>
<p class=note>Edge is my odds minus current price. Buy at +{BUY_EDGE*100:.0f} or more, Sell at {SELL_EDGE*100:.0f} or less, otherwise Hold. Rows with no odds show No view. Bets that pay out on the same result are merged into one row, so duplicate exposure shows up in the ranking. Not financial advice.</p>
</main><script>
document.querySelectorAll('#t th').forEach((h,i)=>{{h.tabIndex=0;const s=()=>{{const b=document.querySelector('#t tbody'),d=h.dataset.d=h.dataset.d=='1'?'-1':'1';
[...b.rows].sort((x,y)=>{{const a=x.cells[i].innerText,c=y.cells[i].innerText,n=v=>parseFloat(v.replace(/[^0-9.+-]/g,''));
return (isNaN(n(a))||isNaN(n(c))?a.localeCompare(c):n(a)-n(c))*d}}).forEach(r=>b.append(r))}};h.onclick=s;h.onkeydown=e=>e.key=='Enter'&&s()}});
</script></body></html>"""

if __name__ == "__main__":
    main()
