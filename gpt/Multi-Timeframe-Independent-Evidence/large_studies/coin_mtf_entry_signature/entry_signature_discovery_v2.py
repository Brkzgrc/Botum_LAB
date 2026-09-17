from __future__ import annotations

import numpy as np
import pandas as pd

import entry_signature_discovery as study


def robust_effects_fixed(df: pd.DataFrame, features: list[str], subsets: dict[str, pd.Series]) -> list[dict]:
    out = []
    for c in features:
        rec = {"feature": c}
        signs = []
        ok = True
        mags = []
        for name, mask in subsets.items():
            q = df.loc[mask, [c, "h1_confirm_within4h"]].replace([np.inf, -np.inf], np.nan).dropna()
            if len(q) < 50:
                ok = False
                break
            # Pandas 3 / NumPy 2 no longer permits quantile interpolation directly on bool.
            vals = pd.to_numeric(q[c], errors="coerce").astype(float)
            target = q["h1_confirm_within4h"].astype(int)
            good = vals.notna()
            vals = vals[good]
            target = target[good]
            a = vals[target == 1]
            b = vals[target == 0]
            if len(a) < 15 or len(b) < 15:
                ok = False
                break
            iqr = float(vals.quantile(.75) - vals.quantile(.25))
            if not np.isfinite(iqr) or iqr == 0:
                ok = False
                break
            eff = float((a.median() - b.median()) / iqr)
            rec[f"{name}_effect_iqr"] = eff
            signs.append(np.sign(eff))
            mags.append(abs(eff))
        if ok:
            rec["same_direction_all"] = bool(len(set(int(s) for s in signs if s != 0)) <= 1)
            rec["min_abs_effect"] = float(min(mags))
            out.append(rec)
    out.sort(key=lambda r: (r["same_direction_all"], r["min_abs_effect"]), reverse=True)
    return out[:25]


study.robust_effects = robust_effects_fixed
study.main()
