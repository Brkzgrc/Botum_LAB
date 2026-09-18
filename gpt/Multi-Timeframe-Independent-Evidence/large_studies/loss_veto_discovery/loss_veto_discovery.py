from __future__ import annotations

# Recovery wrapper: execute the frozen original study source, with one narrowly
# scoped aggregation fix. Keeping the source pinned prevents unrelated project
# code from changing while the loss-veto experiment is recovered.
import requests

SOURCE_URL = "https://raw.githubusercontent.com/Brkzgrc/Botum_LAB/4b78da7029b630abf88250c220dda9ed8a7538a6/gpt/Multi-Timeframe-Independent-Evidence/large_studies/loss_veto_discovery/loss_veto_discovery.py"
source = requests.get(SOURCE_URL, timeout=30).text
source = source.replace(
    'def base_metrics(x):\n    if len(x)==0:return {"n":0}',
    'def base_metrics(x):\n    if len(x)==0:return {"n":0,"symbols":0,"net24":float("nan"),"net72":float("nan"),"win24":float("nan"),"win72":float("nan"),"bad_pct":float("nan"),"hard_loss_pct":float("nan"),"dead_signal_pct":float("nan"),"clean_winner_pct":float("nan"),"delayed_winner_pct":float("nan")}'
)
if 'def aggregate_main' not in source:
    raise RuntimeError('Pinned loss-veto source could not be loaded')
exec(compile(source, SOURCE_URL, 'exec'), globals(), globals())
