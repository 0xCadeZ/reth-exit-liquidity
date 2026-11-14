# Prediction, fixed before the analysis

Written 2026-11-13, while the raw pulls were still running and before any daily series existed.

## The prediction (from the brief, unchanged)
On days when the DEX price of rETH is at a premium to the protocol exchange rate and the deposit pool
has capacity, mint volume is at least 3x the mint volume on discount days.

## Definitions, fixed now
- Window: 2026-05-01 to the end block in data/discovery.json.
- DEX price: volume-weighted daily rETH/ETH price over the Uniswap v3 0.01% pool and the Uniswap v4
  rETH/ETH pool (the two venues that carried rETH in the discovery scan).
- Premium day: daily VWAP above the protocol rate. Discount day: below. The protocol rate for the day is
  the value at the day's first block.
- Capacity: deposits enabled and deposit pool balance below the maximum pool size.
- Mint volume: rETH Transfer events from the zero address, in rETH, per UTC day.
- Test: mean daily mint volume on premium days divided by mean on discount days. Pass at 3.0 or above.
  The median ratio is reported next to it.

## What had already been seen when this was written (disclosure)
- A 7-day scan of raw rETH transfers: 937 rETH minted, 2,551 burned.
- Current state: deposit pool 0.34 ETH against a 6.0M ETH cap; deposits enabled; fee 0.05%;
  670 validators queued for pool ETH; 2,006 ETH of burn collateral in the rETH contract.
- One Uniswap v4 swap priced rETH within about 1 bp of the protocol rate.

None of these is a daily premium-versus-discount split, so the prediction is still a real test.

## Second prediction, added now because the first look suggests it
If burns are open (collateral above zero) and the mint fee is 0.05%, the DEX price should sit inside a
band from the rate (burn floor) to rate x 1.0005 (mint ceiling) on at least 90% of days. If it does,
"discount" is the wrong word for what the DEX shows and the first test may have too few premium days
to mean anything; that would be reported as a finding, not patched.
