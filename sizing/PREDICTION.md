# Step 2, buffer sizing: predictions fixed before the simulation

Written 2026-11-15, before any sizing run. Already seen: step 1 results (inflow mix 81% node payouts, 13% mints, 5%
recycled; 62,066 ETH forwarded above the 1% cap in total; refills drained within seconds under a discount), and the
daily burn sizes (median 102 ETH, 95th percentile 1,009 ETH, worst week 6,826 ETH). Not yet seen: when the forwarded
ETH left, or any counterfactual.

## Question
For a buffer target between 0.5% and 5% of rETH value, on what share of days could the buffer have paid every exit,
and what would the idle ETH have cost rETH holders in yield? And under Saturn 2's design (1% deposit pool buffer plus
a queue), how long would exits have waited?

## Method, fixed now
- Daily replay over the 196 days. Each day: inflows arrive (node payouts and recycled deposits as they happened, mints
  as they happened), the buffer is capped at the target (the excess goes to the deposit pool, as now), then exit demand
  is paid from the buffer. Unpaid demand that day marks a day without an exit. Inflows-first and burns-first orders are
  both run; the gap is reported.
- Start: the true buffer on 2026-05-01 (844 ETH), capped at the target.
- Exit demand, three scenarios:
  - S1 observed: demand equals the burns that happened. A floor, since on empty days burns could not exceed inflows.
  - S2 latent: on days the real buffer was empty, demand is drawn from the funded days' burns as a share of supply
    (1,000 bootstrap runs, seed 7); other days as observed. Median and 5th to 95th percentile reported.
  - S3 stress: S2 plus the worst observed week (6,826 ETH over 7 days) added once, at the start of the long spell.
- Yield cost: average idle buffer as a share of rETH value, times the rETH rate's growth over the window (2.11% a year),
  in bps of holder yield a year.
- Saturn 2: target 1%; unpaid demand joins a FIFO queue served by later inflows; waits reported without forced exits.
  RPIP-71 estimates about 5 days for exits to free ETH; that is quoted, not modelled.
- Also the reservoir (Rippl) measure: the buffer that would never have run dry under each scenario, with no cap.

## Predictions
P10. Under S1, some target at or below 3% pays every exit on at least 90% of days.
P11. That target costs rETH holders under 5 bps of yield a year.
P12. Under S2, no target at or below 3% reaches 90% of days at the median: the buffer alone cannot cover latent exit
     demand through a spell like August to October.
P13. Under Saturn 2 with S2 demand, the median exit waits less than 7 days without forced exits.
