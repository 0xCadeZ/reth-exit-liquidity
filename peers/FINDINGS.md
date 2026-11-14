# rETH against five rival staking tokens

Same 196 days (2026-05-01 to 2026-11-12), same daily blocks, each protocol's own exchange-rate function, and the
market price from that token's main pool at the first block of each day. Chainlink's market feed is shown beside it
as an outside check where one exists. Scripts 10 to 14 in `scripts/`; data in this folder.

## Answer

A withdrawal queue on its own does not keep a token at its rate. Two rivals with queues, ETHx and osETH, traded as far
below their rates as rETH, or further. The tokens that held their rates had a fast exit and a deep market: stETH,
cbETH and mETH. rETH with ETH in its burn buffer behaved like the best of them. rETH with an empty buffer was worse than
everything except osETH.

| Token | Exit when no instant liquidity | Days within 10 bps of rate, pool / Chainlink | Median vs rate | Longest run below -10 bps | Supply change | Yield |
|---|---|---|---|---|---|---|
| rETH, buffer funded (102 days) | instant burn | 100% / 100% | +1.0 bps | 0 days | | |
| rETH, buffer empty (94 days) | none | 32% / 32% | -22.4 bps | 45 days | | |
| **rETH, all days** | none until Saturn 2 | 67% / 67% | -0.4 bps | 45 days | -8.2% | 2.11% |
| stETH (Lido) | queue, 1-5 days | 97% / 96% | -1.1 bps | 6 days | +7.0% | 2.40% |
| cbETH (Coinbase) | custodial unwrap | 86% / 92% | -4.0 bps | 11 days | 0.0% | 2.47% |
| mETH (Mantle) | queue, 12 h minimum | 80% / 90% | -7.4 bps | 8 days | -3.6% | 2.00% |
| ETHx (Stader) | queue, 7-10 days | 66% / 64% | -7.6 bps | 26 days | -51.2% | 2.32% |
| osETH (StakeWise) | redeemer queue | 0% / no feed | -81 bps | 72 days | -4.7% | 2.20% |

Yield is each rate's growth over the window, annualised. cbETH supply did not change at all in the window.

## What this means for Saturn 2
- Rocket Pool has voted for a withdrawal queue (RPIP-71, about 97.6% in October; package not yet ratified;
  indicative launch May 2027). It gives rETH what stETH, ETHx, osETH and mETH already have.
- The rivals show that the queue is necessary but not enough. ETHx has a 7-10 day queue, a thin Curve market and a
  supply that halved; it sat 5 to 17 bps under its rate most days. osETH trades on a pool with a median of 7 ETH a day
  and sat about 80 bps under.
- RPIP-71 keeps a 1% ETH buffer, moved to the deposit pool. So the buffer size still decides whether rETH trades at its
  rate after Saturn 2, as it did on the 102 funded days here.
- rETH's mint fee is the highest of the group: 0.05%, against 0 for stETH and ETHx and 0.04% for mETH.

## osETH after its redemption vote
StakeWise announced on 2026-08-27 that the vote to open osToken redemptions was live ("Soon, osETH discounts will be a
thing of the past"). osETH's median gap to its rate was -93 bps before that date, -69 bps from 2026-08-27 to 09-30, and
-34 bps since October. It never came within 10 bps on any day. The vote date is known, the activation date is not, so
this shows a narrowing after redemptions were approved, not how long a queue takes to work.

## Checks
- ETHx pool price against Chainlink's ETHx/ETH feed: within 2 bps on 11 of 13 sampled days.
- stETH and cbETH pool prices against Chainlink: median gap 1.2 and 4.3 bps.
- mETH: the Uniswap pool is one-sided and reads 3-4 bps below Chainlink. The Chainlink column is the better figure.
- osETH has no Chainlink feed. CoinGecko shows a -68 bps median. CoinGecko reads 19-27 bps above the chain for every
  token checked, including rETH, so the two agree on a large discount.
- These Chainlink feeds update on a 0.5-2% move or every 24 hours, so they are a coarse check, not a precise one.

## Predictions fixed before the data (PREDICTION.md)
- P3, rETH has the fewest days near its rate: **fail**. ETHx (66%) and osETH (0%) had fewer.
- P4, rETH's supply fell more than the peer median: **pass**. -8.2% against -3.6%. ETHx fell further, -51%.
- P5, no peer has a 30-day run below -10 bps: **fail**. osETH ran 72 days.

## Limits
- One pool per token, read once a day. ETHx and osETH markets are thin, so their prices are noisy.
- osETH is priced from swaps, fee-adjusted, on 190 of 196 days. When its redeemer opened to all holders is not
  established here, so its discount may predate the queue.
- Exit designs and fees come from each project's docs (`SOURCES.md`); cbETH terms could not be confirmed.
- Correlation, not cause. ETHx's discount sits beside a halving supply; heavy exits and a slow queue both fit.
