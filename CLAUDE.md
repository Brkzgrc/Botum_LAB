# CLAUDE.md — Botum_LAB

## Purpose

This repository is a cryptocurrency research laboratory.

It is NOT the live production system.

Research, experiments, backtests, signal studies, data analysis, and prototype
systems belong here.

Nothing in this repository should be assumed to be production-ready or
automatically connected to the live Botum/Render/portfolio system.

## Workspace Ownership

Claude must work only under:

`claude/`

GPT-owned work is under:

`gpt/`

Do not modify, reorganize, delete, or stage files inside another agent's workspace
unless the user explicitly asks.

Directory convention:

`claude/<project>/<work>/`

Examples:

`claude/spot-sinyal-arastirmasi/2026-09-15_dip-tarama/`
`claude/spot-sinyal-arastirmasi/2026-09-15_hareket-tespiti/`

For a new research project:
- create a new project folder under `claude/`
- keep each experiment/work unit in its own dated or clearly named subfolder
- keep that work's notes, scripts, outputs, reports, and intermediate artifacts inside it

Do not scatter project-specific files across repository root.

## Git Discipline

This repository may have multiple independent jobs pushing to main.

- Never use unrestricted `git add -A`.
- Stage only the active Claude workspace/project path.
- Prefer:
  `git add -A claude/<project>/<work>/`
- Do not stage GPT workspace changes.
- Do not stage unrelated user changes.
- Preserve concurrent work.

Workflow files must live under:

`.github/workflows/`

Workflow names should be unique and begin with the relevant Claude project/work name.

For automated pushes:
- use `git pull --rebase --autostash`
- retry when concurrent pushes race
- use distinct concurrency groups
- avoid reusing the same cron minute for independent jobs

## Public Repository Safety

This repository is PUBLIC.

Never commit:
- API keys
- tokens
- passwords
- cookies
- private URLs containing credentials
- exchange secrets
- Telegram bot tokens
- Render secrets
- personal identifiers
- private production configuration

Use placeholders or environment-variable names only.

If a task requires a secret, stop and tell the user what variable/configuration
must be provided outside the repository.

## Research Scope

Primary market scope:

- Binance Spot
- real spot crypto assets
- no real SHORT positions
- no leveraged trading assumptions unless a specific research task explicitly says otherwise

Spot universe filtering:

- exclude actual stablecoins and fiat instruments when the research scope requires it
- do not exclude legitimate assets using naive substring filtering
- strings such as `UP`, `DOWN`, `BULL`, or `BEAR` inside a normal asset symbol do
  not by themselves make it a leveraged token
- legitimate assets such as `SYRUP` or `JUP` must not be removed merely because
  their symbols contain `UP`
- prefer Binance metadata, asset identity, spot eligibility, trading status,
  quote asset, and explicit stablecoin/fiat classification
- when uncertain, verify before excluding

## Research Integrity

Clearly separate:
- hypothesis
- code behavior
- backtest result
- walk-forward result
- holdout result
- paper/simulation result
- live result

Never present one as another.

Do not treat an old claimed win rate, PnL, or success rate as validated evidence
unless it is reproducible from the current code/data.

Negative or failed research is valuable and must not be silently deleted.

Record:
- what was tested
- dataset/time period
- symbols
- timeframe
- fees/slippage assumptions
- entry/exit rules
- result metrics
- failure reason when known

Do not optimize a system until it looks good and then report the optimized sample
as independent evidence.

## Existing Research

Before starting a new experiment:
- inspect relevant existing Claude research folders
- inspect `SPOT_STRATEJI_KURALLARI.txt` when relevant
- reuse previous findings instead of unknowingly repeating the same experiment
- identify whether the proposed test is genuinely new

Do not modify previous experiment outputs merely to make a new experiment cleaner.
Create a new work folder when the research question materially changes.

## LLM Wiki Integration

This repository contributes research knowledge to the persistent Kripto LLM Wiki.

Preferred local wiki location when available:

`D:\EĞİTİM SETİ\KRİPTO\_0_0_Kripto-Wiki`

When the wiki is accessible and a task produces durable, materially new crypto knowledge:
- process it according to the Kripto Wiki's own `CLAUDE.md`
- record meaningful validated or invalidated findings
- record reusable modules/features
- record important failed approaches
- record contradictions with earlier research
- record significant dataset/API findings
- update relevant Anton capability/integration knowledge when applicable

Do not update the wiki merely because a file was opened or a trivial experiment ran.

If the wiki is not accessible, such as in a GitHub/Cloud environment:
- do not pretend the wiki was updated
- keep the research result properly documented inside the active Claude project folder
- explicitly report that the result should later be synchronized to the Kripto LLM Wiki

## Production Separation

The separate Botum production repository and any Render/portfolio-tracker deployment
must be treated as a different system.

Do not:
- deploy Botum_LAB experiments automatically
- push experimental signals into the live portfolio
- modify Render production configuration
- assume an experimental strategy is approved for production

Any future integration from research into:
- Botum
- Render
- portfolio_tracker
- Anton

requires a separate explicit integration task and validation.

## Working Style

Before substantial work:
1. identify the active research project
2. identify or create the correct `claude/<project>/<work>/` folder
3. inspect relevant prior work
4. state the research question and success criteria
5. work only inside the active scope
6. verify outputs
7. document results, including failures

Do not expand scope silently.

## Completion Report

For substantial research, report:
- active project/work folder
- research question
- files created/changed
- data period and symbol universe
- methodology
- tests/backtests performed
- metrics/results
- limitations
- whether findings support, reject, or leave the hypothesis unresolved
- whether any result should be synchronized to the LLM Wiki
- whether anything is potentially suitable for later Anton/Botum evaluation

Do not deploy or integrate into production unless explicitly requested.
