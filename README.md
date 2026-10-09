# Girls Go Midterm Poly Markets

Ranks your top 50 bets by value, merging positions across platforms.

## Setup
1. Push this repo to GitHub.
2. Settings > Pages > Deploy from branch > `main` / `/docs`.
3. Actions > Daily dashboard > Run workflow. It then runs every day at 14:00 UTC.

## Edit positions.csv
- `platform`: `kalshi`, `polymarket`, or `susqies` (or any other name; those use `price_override`).
- `bet_on`: the result you are betting on. Positions with the same text merge, so
  "R YES" and "D NO" on the same race share one `bet_on` and show as one exposure.
- `market_id`: Kalshi market ticker, or Polymarket slug. Live price replaces `price_override`.
- `price_override`: current price of the side you hold, used when there is no live feed.
- `my_prob`: your probability the bet pays out. Leave blank for "No view".
