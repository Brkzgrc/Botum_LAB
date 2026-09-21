# PUMP WATCH → PUMP ENTRY — MASTER SESSION README

> **THIS FILE IS THE HANDOFF / CONTINUITY FILE FOR THIS RESEARCH.**
>
> A completely new ChatGPT session must be able to read ONLY this README first and understand what this project is, what is locked, what has actually been done, what has not been verified, and exactly how to continue.
>
> **Mandatory maintenance rule:** Every session that materially changes code, methodology, workflow status, results, conclusions, or next steps MUST update this README before ending. Never write an unverified result/status here as fact.

## 1. New-session startup instructions

When the user says something like **“Read the README in gpt/PUMP-WATCH-to-PUMP-ENTRY and continue”**, the new session must:

1. Work only in `Brkzgrc/Botum_LAB/gpt/PUMP-WATCH-to-PUMP-ENTRY/` for this research unless the user explicitly authorizes another location.
2. Read this README completely.
3. Inspect the files listed in **Current project files**.
4. Inspect the actual GitHub Actions workflow/run state before saying a test is running, completed, failed, or produced results.
5. Read the newest result artifact/report if one exists.
6. Continue from **NEXT ACTION** below. Do not restart the research from scratch unless required by an actual failure.
7. Never infer workflow completion from the existence of a workflow file.
8. Never report fabricated/intermediate metrics as validated findings.
9. Update this README at the end of meaningful work.

## 2. Objective

Develop a **Binance Spot USDT LONG** signal system based on:

**🟡 PUMP WATCH → 🟢 PUMP ENTRY**

The user wants a system with:
- high win rate,
- high net P&L,
- strong Profit Factor / positive expectancy,
- robustness outside the discovery sample,
- not necessarily thousands of signals.

Quality takes priority over raw signal count.

The research is specifically interested in whether **movement/evolution of indicators and price structure** detects opportunities better than static indicator thresholds.

## 3. Locked scope — DO NOT silently change

- Research period: **2026-01-01 through 2026-09-21**.
- Market: **Binance Spot USDT**.
- Direction: **LONG only**.
- Stablecoin and fiat base assets excluded by **exact asset names**, not substring matching.
- **JUP and SYRUP MUST remain included.**
- Round-trip trading cost: **0.20%**.
- No paid APIs.
- No futures entries / no leverage.
- No look-ahead.
- Signal decision may use **only fully closed candles**.
- A tradable signal enters at the **NEXT candle OPEN**.
- The HIGH/LOW of the signal candle or any future candle must never influence the signal decision.
- Future HIGH/LOW is allowed only after timestamp `t` for labels/outcome/MFE/MAE.
- If stop and target are both touched in the same unresolved OHLC candle, use a conservative rule or lower timeframe resolution; never assume target first just to improve results.

## 4. Intended architecture

### 🟡 PUMP WATCH
Early-warning stage. Search for accumulation/compression and improving behavior before obvious breakout.

### 🟢 PUMP ENTRY
Tradable confirmation after WATCH. The eventual entry should preferably use 15M ignition/confirmation while respecting 1H setup and 4H context.

Timeframe roles:
- **4H:** regime/context.
- **1H:** setup, compression, accumulation and motion.
- **15M:** ignition / entry trigger.
- **1D:** optional broader context if later shown useful.

The current Phase-1 runner is a **4H discovery search**, not the finished multi-timeframe system.

## 5. Core research hypothesis

Do not ask only whether an indicator crossed a fixed number. Test whether behavior is changing before strong upward moves.

Candidate trajectory:

**volatility contraction + increasingly higher lows + shrinking pullbacks + repeated resistance pressure + improving normalized momentum + strengthening volume/OBV → expansion/15M ignition**

Candidate motion features:
- higher-low progression and ATR-normalized slope,
- pivot-low sequence,
- pullback magnitude decay,
- pullback-duration decay,
- repeated resistance tests,
- touch imbalance,
- reaction decay,
- shrinking distance to resistance,
- time between resistance tests,
- ADX slope and acceleration,
- DI+ minus DI− spread evolution,
- normalized MACD histogram slope/acceleration,
- RSI/StochRSI/KDJ direction and persistence,
- OBV slope and acceleration,
- RVOL trajectory,
- volume/median trajectory,
- MFI slope,
- BB Width slope/percentile,
- ATR% / range contraction and expansion onset,
- BTC 4H context,
- altcoin/BTC relative strength where useful.

Raw MACD values across differently priced coins should not be compared directly; normalize where appropriate by price or ATR.

## 6. Required comparisons

At minimum compare on the same data:

A. **Static WATCH baseline**  
B. **Motion-based WATCH**  
C. **Hybrid WATCH** = motion + minimal quality filters  
D. **WATCH → ENTRY** confirmation system

Do not loosen a good candidate merely to manufacture more signals.

## 7. Labels / episode research

Upward episodes may be identified using future prices because they are **labels only**, never inputs to the signal.

Useful episode thresholds:
- +10%
- +15%
- +20%
- +30%

Use non-overlapping episode logic so one pump is not counted dozens of times.

For pre-pump characterization inspect approximately:
- 48H before,
- 24H before,
- 12H before,
- 6H before.

Compare with matched non-pump/control windows. Avoid obvious leakage and survivorship bias where practical.

## 8. Validation rules

Discovery and validation MUST be separated.

Current predeclared Phase-1 split:
- discovery/training: **2026-01-01 → 2026-06-30**
- validation: **2026-07-01 → 2026-09-21**

Later research should also examine monthly / rolling walk-forward stability.

A candidate is not successful merely because its in-sample WR is high.

Required metrics:
- signals/trades,
- unique symbols,
- signals/day,
- win rate,
- net P&L after 0.20% cost,
- average trade return,
- median trade return,
- Profit Factor,
- expectancy,
- max drawdown,
- max loss streak,
- MFE / MAE,
- +5/+8/+10/+15/+20/+25 hit rates,
- 6h/12h/24h/48h/72h forward returns,
- WATCH→ENTRY lead time,
- false WATCH alerts,
- monthly stability,
- regime stability,
- discovery vs validation degradation.

## 9. Current project files

Repository: `Brkzgrc/Botum_LAB`

Research directory:
`gpt/PUMP-WATCH-to-PUMP-ENTRY/`

Currently created:
- `README.md` — **this master handoff file**.
- `RESEARCH_PLAN.md` — initial research plan.
- `research_spec.json` — locked machine-readable scope.
- `research_runner.py` — Phase-1 4H motion candidate search.

Workflow:
- `.github/workflows/pump-watch-entry-research.yml`

Expected Phase-1 output:
- `gpt/PUMP-WATCH-to-PUMP-ENTRY/results/phase1_4h_motion_search.json`
- GitHub artifact name: `pump-watch-entry-phase1`

## 10. What has ACTUALLY been done

### Confirmed
- New dedicated project directory was created under `gpt/`.
- It is separate from `gpt/Multi-Timeframe-Independent-Evidence/`.
- README, research plan and research specification were committed.
- `research_runner.py` was committed.
- A dedicated GitHub Actions workflow was committed.
- The runner explicitly uses next-4H-bar OPEN for Phase-1 trade entry and includes 0.20% round-trip cost.
- JUP/SYRUP are force-included in the intended universe logic.

### Pilot work before the dedicated folder
A small pilot examined JUP, SYRUP, ID and PUMP to verify Binance historical data and episode labeling. Those episode counts were **not trading signals and not validated strategy results**. Do not confuse them with system performance.

### NOT YET VERIFIED
At the time this README was updated, the session **had not successfully verified the GitHub Actions run state after workflow creation**. A GitHub API fetch attempt for the run list was rejected by the connector route.

Therefore:
- Do NOT say Phase 1 completed unless GitHub Actions is actually checked.
- Do NOT quote a Phase-1 WR/P&L/PF yet.
- Do NOT treat the workflow file's existence as proof that it ran successfully.

## 11. Important implementation warning

The current `research_runner.py` is **Phase 1 only** and intentionally incomplete relative to the final architecture.

It currently searches a parameter grid on 4H motion-like features. Before promotion to a real candidate, audit at least:
- stable/fiat exclusion completeness,
- delisted/historical-symbol survivorship bias,
- entry/exit candle ambiguity,
- structural stop implementation,
- parameter-search overfitting,
- validation sample size,
- P&L aggregation interpretation,
- missing median/MFE/MAE/drawdown metrics,
- lack of 1H + 15M WATCH→ENTRY sequence,
- lack of BTC context,
- lack of matched pump/non-pump characterization.

Do not call Phase-1 output the final system.

## 12. NEXT ACTION — start here in a new session

1. Inspect GitHub Actions for `pump-watch-entry-research.yml`.
2. If a run exists, inspect its real status and logs.
3. If failed, diagnose from logs and fix only inside this project/workflow.
4. If successful, retrieve `phase1_4h_motion_search.json` artifact.
5. Audit Phase-1 results for sample size and train→validation degradation.
6. Do not promote a candidate unless validation remains strong.
7. Then build Phase 2 around actual pre-pump trajectory vs matched controls.
8. Progress toward the real **4H context → 1H PUMP WATCH → 15M PUMP ENTRY** architecture.
9. Maintain strict next-bar entry/no-look-ahead rules.
10. Update this README with actual run IDs, commits, results, conclusions, rejected ideas, and the next exact action.

## 13. README maintenance protocol

This README is a **living project state file**.

Every meaningful research session must update these sections:
- **What has ACTUALLY been done**
- **Current verified workflow/run state**
- **Validated results**
- **Rejected/failed experiments**
- **NEXT ACTION**
- **Change log**

Rules:
1. Never delete important historical conclusions merely because the project advanced.
2. Mark obsolete conclusions as superseded and state what replaced them.
3. Record exact filenames and workflow names.
4. Record run ID / commit SHA when available.
5. Separate **verified fact**, **hypothesis**, and **planned work**.
6. Never write “running”, “successful”, “failed”, or performance numbers without checking the actual source.
7. A new session should not need the previous chat transcript to continue safely.
8. If README and actual repository state disagree, inspect the repository/workflow and correct the README.
9. Keep this file concise enough to read at session start but complete enough to prevent loss of state.

## 14. Validated results

**None yet.**

No strategy candidate has yet earned validated status in this dedicated project.

## 15. Rejected / failed experiments

None formally recorded yet in this dedicated project.

## 16. Current verified workflow/run state

**UNKNOWN / NOT YET VERIFIED after workflow creation.**

Do not convert this to RUNNING/SUCCESS/FAILURE without checking GitHub Actions.

## 17. Change log

### 2026-09-21
- Dedicated `gpt/PUMP-WATCH-to-PUMP-ENTRY/` research area created.
- Locked scope documented.
- Phase-1 `research_runner.py` added.
- Dedicated `pump-watch-entry-research.yml` workflow added.
- README upgraded into the master cross-session handoff/state document.
- Explicit README self-maintenance protocol added.
