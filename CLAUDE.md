# CLAUDE.md — Botum_LAB

## User Interaction Preferences

- Always respond in Turkish.
- Explain technical topics clearly, practically, and step by step.
- Assume the user has limited coding knowledge.
- When code is required, prefer complete, ready-to-run solutions over partial snippets.
- The user's local environment is Windows; when local terminal commands are relevant, prefer PowerShell-compatible commands.
- If a long-running task is already in progress, do not start an unrelated new command, workflow, or experiment until it finishes, unless a critical correction is required.
- Give instructions in chronological order.
- Avoid guidance that requires the user to backtrack, such as "do this first, but before that do something else."
- Do not silently make major assumptions. If an ambiguity could materially change the research result, state it clearly before proceeding.
- Do not overwhelm the user with unnecessary implementation detail when a simpler explanation is sufficient.

---

## Purpose

This repository is a cryptocurrency research laboratory.

It is NOT the live production system.

Research, experiments, backtests, signal studies, data analysis, validation work,
prototype systems, and exploratory implementations belong here.

Nothing in this repository should be assumed to be:
- production-ready
- approved for live trading
- connected automatically to the live Botum system
- connected automatically to Render
- connected automatically to portfolio_tracker
- connected automatically to Anton

Research results must remain isolated from production unless the user explicitly requests
a separate integration task.

---

## Workspace Ownership

Claude must work only under:

`claude/`

GPT-owned work is under:

`gpt/`

Do not modify, reorganize, delete, move, rename, stage, or commit files inside another
agent's workspace unless the user explicitly asks.

Directory convention:

`claude/<project>/<work>/`

Examples:

`claude/spot-sinyal-arastirmasi/2026-09-15_dip-tarama/`

`claude/spot-sinyal-arastirmasi/2026-09-15_hareket-tespiti/`

For a new research project:
- create a new project folder under `claude/`
- keep each experiment/work unit in its own dated or clearly named subfolder
- keep that work's notes, scripts, outputs, reports, intermediate artifacts, and result files inside it
- reuse an existing project folder when the new work clearly belongs to an existing research line
- create a new project folder only when the research question is materially different

Do not scatter project-specific files across the repository root.

Do not place Claude research files inside `gpt/`.

Do not move GPT files into `claude/`.

---

## Git Discipline

This repository may have multiple independent jobs, agents, or workflows pushing to `main`.

- Never use unrestricted `git add -A`.
- Never stage the entire repository unless the user explicitly requests it.
- Stage only the active Claude project/work path.
- Prefer:

  `git add -A claude/<project>/<work>/`

- Do not stage GPT workspace changes.
- Do not stage unrelated user changes.
- Preserve concurrent work.
- Inspect `git status` before committing substantial work.
- Do not discard, reset, overwrite, or clean unrelated changes.
- Do not use destructive git commands on user work unless explicitly authorized.

Workflow files must live under:

`.github/workflows/`

Workflow names should:
- be unique
- identify the relevant project/work
- preferably begin with the relevant Claude project or experiment name

For automated pushes:
- use `git pull --rebase --autostash`
- retry when concurrent pushes race
- use distinct concurrency groups
- avoid reusing the same cron minute for independent jobs
- avoid workflows overwriting each other's output
- keep workflow write scope limited to the intended research area

---

## Public Repository Safety

This repository is PUBLIC.

Never commit:
- API keys
- tokens
- passwords
- cookies
- authentication headers
- exchange secrets
- Binance API secrets
- Telegram bot tokens
- Render secrets
- private database credentials
- private URLs containing credentials
- personal identifiers
- private production configuration
- `.env` files containing secrets
- session tokens
- private SSH keys
- cloud credentials

Use:
- placeholders
- environment-variable names
- example values
- sanitized configuration templates

If a task requires a secret:
- do not invent one
- do not hard-code one
- do not commit one
- tell the user exactly which environment variable or external configuration is required

Do not copy secrets from another local project into this repository.

---

## Research Scope

Primary market scope:

- Binance Spot
- real spot crypto assets
- no real SHORT positions
- no leveraged trading assumptions unless a specific research task explicitly requires studying them
- prefer analysis, signal generation, signal detection, research, and decision support over automatic order execution
- no automatic live trading unless the user explicitly changes the scope in a separate production task

The user's practical trading context is spot.

Bearish concepts may still be studied as:
- market risk
- avoid/sell context
- downside regime
- bearish signal
- risk filter
- crash/liquidation context

But they must not be silently converted into real SHORT portfolio logic.

---

## Spot Universe Filtering

When building or modifying Binance Spot symbol universes:

- include only genuine Binance Spot markets relevant to the research
- exclude actual stablecoins and fiat instruments when the research scope requires it
- do not accidentally exclude legitimate crypto assets through naive substring matching
- do not classify an asset only by partial text inside its ticker
- strings such as `UP`, `DOWN`, `BULL`, or `BEAR` inside a normal asset symbol do NOT by themselves make it a leveraged token
- legitimate assets such as `SYRUP` or `JUP` must not be removed merely because their symbol contains `UP`
- prefer Binance metadata and explicit asset classification over substring filters
- use, where available:
  - symbol identity
  - base asset
  - quote asset
  - market type
  - trading status
  - spot eligibility
  - explicit stablecoin lists
  - explicit fiat lists
  - explicit leveraged-token metadata/classification
- when uncertain, verify before excluding

The objective is:

- exclude stablecoins that are outside scope
- exclude fiat instruments/parities that are outside scope
- preserve legitimate Binance Spot crypto assets
- avoid false-positive exclusion filters
- avoid shrinking the research universe because of careless string matching

Do not silently change the symbol universe between experiments.

Every meaningful backtest/research report should record or make reproducible:
- the universe definition
- exclusion rules
- number of symbols
- important filters applied

---

## Research Integrity

Clearly separate:

- hypothesis
- implementation
- code behavior
- exploratory test
- backtest
- walk-forward test
- holdout test
- out-of-sample test
- paper/simulation result
- shadow/live observation
- real live result

Never present one as another.

Do not treat an old claimed:
- win rate
- target rate
- PnL
- return
- Sharpe-like metric
- success rate
- MFE
- MAE
- score

as validated evidence unless it is reproducible from the current code/data or its original evidence is clearly preserved.

Negative results are valuable.

Failed research must not be:
- silently deleted
- rewritten as successful
- omitted merely because the result is disappointing
- later reintroduced as a strong candidate without acknowledging the earlier failure

Record, when applicable:

- research question
- hypothesis
- code/version
- dataset
- data source
- date range
- number of symbols
- symbol universe
- timeframe
- entry logic
- exit logic
- target logic
- stop logic
- maximum holding period
- forced-close behavior
- fees
- slippage assumptions
- sample count
- win/loss definition
- result metrics
- MFE/MAE
- limitations
- failure reason
- unresolved questions

Do not optimize repeatedly on the same sample until a result looks good and then report that
optimized result as independent evidence.

If optimization is performed:
- label it as optimization/in-sample work
- keep holdout/out-of-sample evidence separate

If a metric definition changes, for example:
- MFE
- MAE
- win rate
- realized return
- target hit
- stop hit
- expiry
- forced-close return

treat that as a semantic change.

Before combining old and new records:
- verify that the definitions are equivalent
- otherwise keep them separate or explicitly version the metric definition

Do not mix incompatible historical metrics under the same label.

---

## Evidence Strength

Prefer evidence in roughly this order:

1. reproducible holdout / out-of-sample result
2. reproducible walk-forward result
3. reproducible backtest
4. controlled paper/shadow observation
5. real live observation with sufficient sample size
6. code inspection
7. hypothesis / intuition / anecdotal claim

A small live sample can be important, but must not automatically override much larger validated evidence.

A large backtest can also be misleading if:
- leakage exists
- the same sample was over-optimized
- fees/slippage were ignored
- symbol selection was biased
- future information was accidentally used

Always inspect methodology before treating a strong number as strong evidence.

---

## Existing Research

Before starting a new experiment:

- inspect relevant existing Claude research folders
- inspect related README/result/state files
- inspect `SPOT_STRATEJI_KURALLARI.txt` when relevant
- identify whether the same idea was already tested
- identify whether a similar feature/system exists under another project name
- reuse validated findings instead of unknowingly repeating the same experiment
- preserve failed findings so the same failure is not rediscovered repeatedly
- identify whether the proposed test is genuinely new

Do not modify previous experiment outputs merely to make a new experiment cleaner.

Create a new work folder when:
- the research question materially changes
- the dataset changes materially
- the evaluation protocol changes materially
- the strategy architecture changes materially
- the metric definition changes materially

If prior research and new evidence conflict:
- preserve both
- document the contradiction
- state which evidence is newer
- state which evidence is methodologically stronger when this can be determined
- do not silently overwrite the old conclusion

---

## Reproducibility

Research should be reproducible where practical.

Prefer:
- explicit configuration
- deterministic rules
- fixed date ranges
- recorded symbol lists or reproducible universe rules
- saved result files
- versioned scripts
- documented dependencies
- fixed random seeds where randomness exists

Do not introduce randomness into success metrics unless the experiment explicitly studies randomized behavior.

Never use fabricated/random results as research evidence.

If an external data source changes over time, record enough context to understand what was used.

---

## Data Handling

Do not commit unnecessarily large raw datasets unless the repository already intentionally stores them.

For large datasets:
- keep scripts/configuration/results where practical
- document the data source
- document how to reproduce/download it
- store summaries/manifests when full data storage is unnecessary

Do not silently alter raw source data.

Prefer derived outputs in separate files/directories.

Do not overwrite important historical result files when a new run can be stored separately.

---

## Timeouts and Long-Running Work

Long-running research must not be allowed to hang indefinitely.

For:
- backtests
- downloads
- GitHub Actions
- large scans
- data preparation
- optimization jobs

use appropriate timeout/error handling when practical.

Before launching expensive work:
- validate inputs
- perform a small smoke test when appropriate
- verify paths
- verify imports/dependencies
- verify output location
- verify that an obvious configuration error will not waste the entire run

If a workflow fails:
- inspect the failure
- correct the root cause
- validate the fix before relaunching a long job

Do not repeatedly launch a known-broken workflow.

---

## LLM Wiki Integration

This repository contributes research knowledge to the persistent Kripto LLM Wiki.

Preferred local wiki location when available:

`D:\EĞİTİM SETİ\KRİPTO\_0_0_Kripto-Wiki`

When the wiki is accessible and a task produces durable, materially new crypto knowledge:

- process it according to the Kripto Wiki's own `CLAUDE.md`
- record meaningful validated findings
- record meaningful invalidated findings
- record important failed approaches
- record reusable modules/features
- record significant dataset/API findings
- record important methodology findings
- record version/canonical-file relationships
- record contradictions with earlier research
- update relevant Anton capability/integration knowledge when applicable

Examples of knowledge worth synchronizing:

- a signal feature repeatedly works or fails
- a filter is demonstrated to harm results
- a backtest invalidates a previous claim
- a data source is unreliable
- a metric definition is found to be wrong
- a reusable module is discovered
- a previously unknown system overlaps with Anton
- a useful old implementation is found
- a new experiment materially changes the current research conclusion

Do NOT update the wiki merely because:
- a file was opened
- a file was mentioned
- a trivial script ran
- a temporary error occurred
- an insignificant implementation detail changed
- an experiment produced no reusable information

Only synchronize:
- durable
- reusable
- materially new
knowledge.

Do not deeply ingest into the wiki:
- huge OHLCV files
- parquet/csv/pkl datasets
- caches
- temp files
- virtual environments
- build artifacts
- repetitive logs
- secrets
- meaningless backups
- byte-identical copies

For large datasets, use inventory/manifest-level knowledge unless deeper inspection is specifically required.

If the wiki is NOT accessible, such as in a GitHub/Cloud environment:

- do not pretend the wiki was updated
- do not invent local file access
- document the research result properly inside the active Claude project folder
- preserve enough context for later synchronization
- explicitly state in the completion report that the result should be synchronized to the Kripto LLM Wiki later

When the wiki IS updated:
- follow the wiki's own schema
- follow its index rules
- follow its log rules
- follow backlink conventions
- follow inventory/manifest conventions
- run the relevant wiki lint/health check when required by the wiki instructions

---

## Production Separation

The separate Botum production repository and any Render/portfolio-tracker deployment
must be treated as a different system.

Botum_LAB is research.

The production Botum system may later be used for:
- live signal delivery
- Render-hosted services
- portfolio_tracker
- remote portfolio visibility
- future Anton integration

But none of those production relationships are automatic.

Do NOT:

- deploy Botum_LAB experiments automatically
- publish experimental signals to the live system automatically
- push experimental trades into a live portfolio
- modify production Render configuration
- modify production databases
- modify production secrets
- enable automatic trading
- assume an experiment is production-approved
- copy research code directly into production without validation

Any future integration from research into:

- Botum
- Render
- portfolio_tracker
- Anton

requires:
- explicit user request
- separate integration scope
- validation
- regression testing
- production safety review where relevant

Research success does not equal production approval.

---

## Anton Relationship

Anton is a separate decision-support application.

Botum_LAB may discover:
- features
- modules
- indicators
- filters
- calibration ideas
- portfolio ideas
- data sources
- signal logic
- failure evidence

that may later be relevant to Anton.

Do not automatically modify Anton from Botum_LAB.

If research produces an Anton-relevant result:
- document it
- synchronize it to the LLM Wiki when possible
- mention it in the completion report
- leave actual Anton integration for a separate explicit task

Do not duplicate functionality in Anton without first checking whether Anton already has it.

---

## Automatic Trading

Default scope is analysis and decision support.

Do not:
- place Binance orders
- enable exchange trading
- create automatic buy/sell execution
- add private exchange API requirements
- add production auto-close/order logic

unless the user explicitly requests a separate production trading implementation.

Public market-data access is acceptable when needed for research.

---

## Working Style

Before substantial work:

1. identify the active research project
2. identify or create the correct `claude/<project>/<work>/` folder
3. inspect relevant existing work
4. inspect relevant rules/documents
5. define the research question
6. define success/failure criteria
7. verify data/universe assumptions
8. perform a small validation/smoke test when appropriate
9. execute the research
10. verify outputs
11. document results, including failures
12. synchronize durable knowledge to the LLM Wiki when accessible
13. report clearly what was done

Do not expand scope silently.

If the task changes materially during execution:
- state the change
- create a new work unit when appropriate
- do not quietly turn one experiment into a different experiment

---

## Change Discipline

- Touch only files required by the current task.
- Preserve pre-existing user changes.
- Do not silently stage unrelated modified/untracked files.
- Do not refactor unrelated code while implementing research support.
- Do not delete old research merely because a newer approach exists.
- Do not overwrite historical evidence without preserving provenance.
- Reuse existing code/modules when suitable.
- Do not create unnecessary duplicate implementations.
- Prefer simple, testable, deterministic research code.
- Separate data acquisition, signal logic, evaluation, and presentation when practical.
- Keep experimental code understandable enough to reproduce later.

---

## Completion Report

For substantial research, report:

- active project
- active work folder
- research question
- hypothesis
- files created
- files changed
- code/version used
- data source
- data period
- symbol universe
- exclusions/filters
- timeframe
- methodology
- fees/slippage assumptions
- tests/backtests performed
- sample count
- metrics/results
- MFE/MAE when relevant
- limitations
- failure modes
- whether the hypothesis was:
  - supported
  - rejected
  - unresolved
- whether previous research was contradicted
- whether anything should be synchronized to the LLM Wiki
- whether the wiki was actually updated or was inaccessible
- whether anything is potentially suitable for later Anton evaluation
- whether anything is potentially suitable for later Botum production evaluation
- whether any workflow/automation was created
- whether any unrelated user files were left untouched

Do not claim production readiness unless a separate production-validation task has explicitly established it.

Do not deploy or integrate into production unless explicitly requested.
