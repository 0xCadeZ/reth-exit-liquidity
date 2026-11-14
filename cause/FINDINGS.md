# Cause and direction: does the empty buffer suppress minting, or does low minting empty the buffer?

Block-level rebuild of the rETH contract's ETH balance, 2026-05-01 to 2026-11-13, from 233,154 contract events.
Script `scripts/21_cause.py`; outputs `results.json`, `refills.csv`, `hourly.csv`. Predictions fixed beforehand in
`PREDICTION.md`.

## Answer

Mostly the first. Mints supply only 13% of the ETH that reaches the buffer; 81% comes from node operators' payouts.
And the buffer does not stay empty for lack of inflow. While rETH trades at a discount, arbitrage takes every ETH that
arrives, usually within one block. The empty state locks itself in: ETH keeps arriving and keeps being taken, until
enough arrives at once to outrun the arbitrage. Hour by hour, a funded buffer predicts more minting over the next day
even after controlling for the previous day's minting and for the price. Minting also makes a funded buffer more
likely, but the effect is small.

## Where the buffer's ETH comes from

| Source | ETH in | Share |
|---|---|---|
| Node operators (megapool and minipool payouts: exits and rewards) | 92,258 | 81% |
| New mints (deposit pool, same transaction as a deposit) | 14,899 | 13% |
| Recycled deposits (deposit pool, other transactions) | 6,040 | 5% |

ETH out through burns: 49,969. ETH above the 1% target is forwarded to the deposit pool without an event; the rebuild
caps the balance at the target after each transaction.

## The lock

- 10,684 ETH arrived while the DEX price was more than 5 bps under the rate. All of it left through burns within
  24 hours, and 95% of those burns used rETH bought from a DEX pool in the same transaction.
- 35 times the buffer went from under 1 ETH to 10 ETH or more. The typical refill was 24 ETH: the depositors' share
  of one exited validator.
- During the 73-day empty spell there were 16 refills. All 16 were emptied within the hour, typically in 12 seconds.
  14 of them were taken entirely by arbitrage burns.
- The spell ended on 2026-10-17 when two 24 ETH payouts landed ten minutes apart and the second one stuck. The DEX
  price went from -32.5 bps to -1.5 bps within six hours. Mints went from 0 the day before to 44 the day after.

## The direction test (hourly, 4,654 hours, Newey-West errors over 24 lags)

| Model | Funded buffer effect on rETH minted over the next 24 h | t |
|---|---|---|
| Controlling for rETH minted in the previous 24 h | +83 | 4.7 |
| Also controlling for the DEX price | +67 | 3.8 |
| One observation per day, no overlap (194 days) | +76 | 3.4 |
| Without the top 1% of minting hours | +61 | 5.8 |
| Placebo: the buffer's state one week later, alongside the real state | real +66 (t 4.6), placebo +24 (t 1.8) | |
| Reverse: rETH minted in the previous 24 h on being funded now | about +1 point of probability per 100 rETH | 2.4 |

The placebo is not zero, so part of the link is slow-moving: periods that are funded for other reasons may also be
periods of higher demand. The real state still carries most of the effect.

## Predictions

- P6, non-mint refills move the price at least 5 bps toward the rate, upward in 70% or more: **fail**. Median +3.2 bps,
  upward in 81%. Most refills were drained before they could move the price.
- P7, non-mint refills of 100 ETH or more raise next-day minting in 60% or more: **not testable**. There was one.
  It did, which proves nothing.
- P8, most ETH arriving under a discount leaves through arbitrage burns within 24 hours: **pass**. 100% and 95%.
- P9, a funded buffer predicts next-day minting after controlling for prior minting: **pass**. +83, t 4.7.

## Checks
- At 60 random blocks where the rebuilt balance was under 50 ETH, 59 matched the true balance within 0.01 ETH and the
  worst was 0.035 ETH. At higher balances, near the 1% cap, it is off by up to 24 ETH.
- The rebuild flagged 336 possible refills. Each was checked by reading the true balance before and after its block;
  35 were real and only those are used.
- Block times are interpolated from daily marks, so hour boundaries can be off by a few minutes.

## Limits
- Observational. A long-run common factor, such as ETH market conditions in August to October, can still explain part
  of the link.
- How much ETH has to arrive at once to break the lock is not measured here; it depends on the size of the discount
  and on DEX depth. That is the sizing question for the next step.
