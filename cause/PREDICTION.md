# Step 1, cause and direction: predictions fixed before the analysis

Written 2026-11-15, before the block-level pull. Already seen: the daily results in ../FINDINGS.md; that the rETH
contract emits only EtherDeposited, TokensMinted and TokensBurned; and one case, 2026-10-18, when a large recycle of
exited minipool ETH refilled the buffer, the DEX price returned to the rate the next day and mints went from about 21
to 57 rETH a day.

## The question
Since Saturn 1, ETH from new mints fills the rETH contract first. So "the buffer is empty when minting is low" could be
mint demand emptying the buffer, not the buffer suppressing mints. To separate them, use refills that do not come
from mints.

## Method, fixed now
- Rebuild the rETH contract's ETH balance at every block from EtherDeposited (in) and TokensBurned ethAmount (out),
  starting from eth_getBalance at the block before the window. Check against the 197 daily balance readings. Any
  unexplained gap is reported, not smoothed.
- Label each inflow:
  - mint-driven: sent by the deposit pool in a transaction that also has a DepositReceived event;
  - recycled: sent by the deposit pool in any other transaction (exited validators' ETH returning);
  - node: sent by any other address (megapool and minipool distributions, rewards, exits).
- Empty: under 1 ETH. A refill: a transaction that takes the balance from under 1 ETH to 10 ETH or more.
  Exogenous refill: the inflow that does it is recycled or node, not mint-driven.
- Price: every Uniswap v3 0.01% and v4 rETH/ETH swap, mid price against the protocol rate at that block.

## Predictions
P6. Exogenous refills move the price toward the rate: the median change in DEX premium from the 6 hours before to the
    6 hours after is at least +5 bps, and the change is positive in at least 70% of refills that had swaps on both sides.
P7. Exogenous refills of 100 ETH or more are followed by more minting: rETH minted in the 24 hours after exceeds the
    24 hours before in at least 60% of them.
P8. Arbitrage drains refills: of all ETH that arrived while the DEX price was more than 5 bps under the rate, more
    than half left through burns within 24 hours, and most of those burns bought rETH from a DEX pool in the same
    transaction.
P9. Direction, hourly: whether the buffer held 10 ETH or more at the start of an hour predicts rETH minted over the
    next 24 hours, with a positive coefficient and t above 2, after controlling for rETH minted in the previous 24 hours.

If P6 and P7 fail, the claim "an empty buffer suppresses minting" is withdrawn from the sheet and the application,
and the evidence supports only "low minting leaves the buffer empty".
