# Peer comparison: predictions fixed before the data

Written 2026-11-14, before any peer time series was pulled. Already seen: each peer's current supply and rate,
which pools exist, and that the osETH and ETHx DEX markets are thin today.

## Peers
Lido stETH (priced through wstETH), Coinbase cbETH, Stader ETHx, StakeWise osETH, Mantle mETH. rETH is re-measured
with the same method so the comparison is like for like.

## Method, fixed now
- Days: the 197 daily marks in data/daily_state.csv (first block of each UTC day, 2026-05-01 to 2026-11-13).
- Rate: each protocol's own exchange-rate function at that block.
- Market price: pool spot at that block. wstETH Uniswap v3 0.01%, cbETH Uniswap v3 0.05%, mETH Uniswap v3 0.05%,
  rETH Uniswap v3 0.01%, ETHx Curve ethx-f (mid of 0.1-token quotes both ways). osETH: daily fee-adjusted
  swap price on the Balancer v3 osETH/waWETH pool, because it has no spot quote I can read; days without swaps blank.
- Premium = market price / rate - 1, in bps. Supply = totalSupply() (stETH totalSupply for Lido).

## Predictions
P3. Of the six tokens, rETH has the lowest share of days with its market price within 10 bps of its rate.
P4. rETH's supply change over the window, in percent, is below the median of the five peers.
P5. No peer has a spell of 30 or more consecutive days more than 10 bps below its rate.

A fail on any of these is reported as a finding. If P5 fails, rETH's discount is not unique and the pitch
must say so.
