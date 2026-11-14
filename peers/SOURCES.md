# Peer designs, rETH exit rules and prior art (sourced 2026-11-14)

Starred items were checked against the primary page on 2026-11-14. Unstarred items are as found, with links; check before relying on them.

## How each token exits at its rate
| Token | Exit at the rate | When the buffer is empty | Mint fee |
|---|---|---|---|
| stETH | Lido withdrawal queue, 1-5 days normally | Queue still pays as ETH arrives | none |
| cbETH | Custodial unwrap at Coinbase | n/a, custodial (terms unconfirmed: help pages blocked) | unconfirmed |
| ETHx | Stader withdrawal queue, 7-10 days per docs | Validators are exited | none |
| osETH | StakeWise redeemer queue, 12 h checkpoints | Forced exits after a grace period | none stated |
| mETH | Mantle unstake queue, 12 h minimum, 40+ days worst case | Waits for validator exits | 0.04% |
| rETH | Instant burn from collateral, no queue | **Burn reverts. No protocol exit.** | 0.05% |

Sources: docs.lido.fi/deployed-contracts, help.lido.fi (withdrawal times), stader.gitbook.io (withdraw guide),
docs.stakewise.io/docs/ostoken/ostoken-redemptions, docs.mantle.xyz/meth/concepts/other/unstake-lifecycle,
github.com/rocket-pool/rocketpool RocketTokenRETH.sol.

## rETH rules
- Burns pay from the rETH contract's ETH plus deposit pool excess; if short, `burn()` reverts.
- Target collateral rate `network.reth.collateral.target` is 1% (RPIP-65, passed 2025-03-19). Actual on 2026-11-14: 0.56%.
- Saturn 1: new mint ETH fills the rETH contract first; only excess above 1% goes to the deposit pool.
- * RPIP-71 (rETH withdrawal queue): status Review. Queue opens 28 days after the upgrade; requests cannot be cancelled;
  collateral target goes from 1% to 0, replaced by a 1% deposit pool collateral target; ~5 days average wait estimated.
  https://rpips.rocketpool.net/RPIPs/RPIP-71
- * Saturn 2 package: the queue won ~97.6% in an October 2026 snapshot (The Defiant, cryptobriefing); full package still
  needs ratification. Indicative launch May 2027 (not firm). https://thedefiant.io/news/defi/rocket-pool-voters-back-reth-withdrawals-keep-4-eth-bonds
  https://dao.rocketpool.net/t/rpip-86-saturn-2-upgrade/4012

## Prior art on dao.rocketpool.net
- * 2026-09-22 filipe.leonor (Round 41 application, $30k): rETH below its rate on 69% of 364 days, mean -10.1 bps,
  beyond -25 bps on 27% of days. No rETH contract balance, no burn collateral, no mint volumes. https://dao.rocketpool.net/t/4043/4
- 2025-01-21 Kevster.eth "below peg for too long" /t/3488/3; 2025-02-07 Valdorff proposes the withdrawal buffer /t/3504;
  2025-07-21 samus: secondary market often the only exit /t/3673/2; 2025-10-27 drdoofus: "the discount will keep the
  amount of rETH minted low" /t/3812; 2026-03-12 ken: redemptions depend on the ~1% buffer /t/3908/6;
  2026-10-26 nishikawa.butterfly: average discount 0.13%, supply down 45%; knoshua: "what we care about is the deposit
  pool balance" /t/4116.
- * 2026-11-12 ASHC2000, Round 43, $500: "rETH Minting Funnel Briefing", 90 days, mint/burn, deposit pool, mint-vs-buy
  gap. No rETH contract collateral, no withdrawal queue. https://dao.rocketpool.net/t/4154/5
- "rETH Exit Advisor" (estimator for withdrawal time, yield cost, redeem vs sell), thread 4136: appears in search, now 404. Unverified.

## Not found anywhere
- A link between the discount and the rETH contract's own balance running empty.
- Anything on the October 2026 recycle (62,066 ETH) or the 58,528 ETH assignment.
- Discord and X were not searched (login needed).
