from __future__ import annotations
import argparse,json,math,importlib.util
from pathlib import Path
import numpy as np,pandas as pd

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/"r2_movement_expansion"/"r2_movement_expansion.py"
spec=importlib.util.spec_from_file_location("base",BASE)
base=importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(base)

KS=(8,12,16,20,24)
TARGET_LOW=.30
TARGET_HIGH=.65

def impute_scale_fit(d,features,fitmask):
    X=np.empty((len(d),len(features)),dtype=float)
    stats=[]
    for j,c in enumerate(features):
        s=pd.to_numeric(d[c],errors="coerce").replace([np.inf,-np.inf],np.nan)
        fit=s[fitmask].dropna()
        med=float(fit.median());q1=float(fit.quantile(.25));q3=float(fit.quantile(.75));scale=q3-q1
        if not np.isfinite(scale) or abs(scale)<1e-12:scale=float(fit.std())
        if not np.isfinite(scale) or abs(scale)<1e-12:scale=1.0
        arr=((s.fillna(med)-med)/scale).clip(-5,5).to_numpy(float)
        X[:,j]=arr;stats.append((c,med,scale))
    return X,stats

def pca_fit_transform(X,fitmask,ncomp=16):
    fit=X[fitmask]
    mean=fit.mean(axis=0)
    Z=fit-mean
    # deterministic PCA fit on Discovery only
    _,_,vt=np.linalg.svd(Z,full_matrices=False)
    comp=vt[:min(ncomp,vt.shape[0])]
    Y=(X-mean)@comp.T
    return Y,mean,comp

def kmeans_fit(X,k,seed=260921,iters=100):
    rng=np.random.default_rng(seed+k)
    n=len(X)
    # kmeans++ style deterministic-seeded init
    centers=[X[rng.integers(0,n)]]
    for _ in range(1,k):
        C=np.vstack(centers)
        d2=((X[:,None,:]-C[None,:,:])**2).sum(axis=2).min(axis=1)
        p=d2/d2.sum() if d2.sum()>0 else np.full(n,1/n)
        centers.append(X[rng.choice(n,p=p)])
    C=np.vstack(centers)
    labels=np.zeros(n,dtype=int)
    for _ in range(iters):
        dist=((X[:,None,:]-C[None,:,:])**2).sum(axis=2)
        new=dist.argmin(axis=1)
        if np.array_equal(new,labels):break
        labels=new
        for j in range(k):
            pts=X[labels==j]
            if len(pts):C[j]=pts.mean(axis=0)
    return C

def assign(X,C):
    return ((X[:,None,:]-C[None,:,:])**2).sum(axis=2).argmin(axis=1)

def cluster_quality(d,sm,labels,k):
    rows=[]
    for cl in range(k):
        rec={"cluster":cl}
        ok=True
        for split in ("DISCOVERY","CALIBRATION"):
            z=d[sm[split]&(labels==cl)]
            m=base.metrics(z);rec[split]=m
            if m["n"]<30:ok=False
        if not ok:
            rec["score"]=-1e9
        else:
            D,C=rec["DISCOVERY"],rec["CALIBRATION"]
            rec["score"]=min(D["mean24"],C["mean24"])+.020*min(D["win24"],C["win24"])+.012*min(D["up3_before_dn2"],C["up3_before_dn2"])-.010*max(D["danger_dn2_first"],C["danger_dn2_first"])
        rows.append(rec)
    return rows

def subset_eval(d,sm,labels,clusters,k):
    mask=pd.Series(np.isin(labels,list(clusters)),index=d.index)
    rec={"k":k,"clusters":list(map(int,clusters))}
    for split,m in sm.items():
        z=d[mask&m]
        rec[split]={"metrics":base.metrics(z),"retention":float(len(z)/max(1,int(m.sum())))}
    D=rec["DISCOVERY"];C=rec["CALIBRATION"]
    if not(TARGET_LOW<=D["retention"]<=TARGET_HIGH and TARGET_LOW<=C["retention"]<=TARGET_HIGH):
        rec["selection_score"]=-1e9;return rec,mask
    dm,cm=D["metrics"],C["metrics"]
    if min(dm["n"],cm["n"])<250 or min(dm["mean24"],cm["mean24"])<=0 or min(dm["pf24"] or 0,cm["pf24"] or 0)<=1:
        rec["selection_score"]=-1e9;return rec,mask
    avgret=(D["retention"]+C["retention"])/2
    rec["selection_score"]=min(dm["mean24"],cm["mean24"])+.025*min(dm["win24"],cm["win24"])+.015*min(dm["up3_before_dn2"],cm["up3_before_dn2"])-.010*max(dm["danger_dn2_first"],cm["danger_dn2_first"])-2.5*abs(avgret-.50)
    return rec,mask

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--indicator-dir",type=Path,required=True)
    ap.add_argument("--r2-dataset-dir",type=Path,required=True)
    ap.add_argument("--outdir",type=Path,required=True)
    ap.add_argument("--preflight",action="store_true")
    a=ap.parse_args();a.outdir.mkdir(parents=True,exist_ok=True)
    pf=base.preflight(a.indicator_dir,a.r2_dataset_dir)
    d=base.load(a.indicator_dir,a.r2_dataset_dir);sm=base.split_masks(d)
    feats=base.movement_features(d,sm["DISCOVERY"])
    if len(feats)<80:raise RuntimeError(f"too few movement features {len(feats)}")
    # Coverage-first subset; PCA handles redundancy.
    cov=[(c,int(pd.to_numeric(d.loc[sm["DISCOVERY"],c],errors="coerce").notna().sum())) for c in feats]
    cov.sort(key=lambda x:x[1],reverse=True)
    feats=[c for c,_ in cov[:160]]
    if a.preflight:
        out={**pf,"movement_features":len(feats),"ks":list(KS)}
        (a.outdir/"preflight.json").write_text(json.dumps(out,indent=2),encoding="utf-8")
        print(json.dumps(out));return

    X,_=impute_scale_fit(d,feats,sm["DISCOVERY"])
    Y,_,_=pca_fit_transform(X,sm["DISCOVERY"].to_numpy(bool),ncomp=18)
    candidates=[];cluster_reports=[]
    for k in KS:
        C=kmeans_fit(Y[sm["DISCOVERY"].to_numpy(bool)],k)
        labels=assign(Y,C)
        cr=cluster_quality(d,sm,labels,k)
        cluster_reports.append({"k":k,"clusters":cr})
        ordered=[x["cluster"] for x in sorted(cr,key=lambda r:r["score"],reverse=True)]
        # cumulative best movement states; also allow removing worst from all
        for m in range(1,k+1):
            rec,mask=subset_eval(d,sm,labels,ordered[:m],k)
            if rec["selection_score"]>-1e8:candidates.append((rec,mask))
    candidates.sort(key=lambda x:x[0]["selection_score"],reverse=True)
    champ=candidates[0] if candidates else None
    status="NO_STABLE_MOVEMENT_CLUSTER_EXPANSION"
    result=None
    if champ:
        rec,mask=champ
        periods={
          "DISCOVERY":(pd.Timestamp("2023-01-01",tz="UTC"),pd.Timestamp("2024-12-31",tz="UTC")),
          "CALIBRATION":(pd.Timestamp("2025-01-01",tz="UTC"),pd.Timestamp("2025-12-31",tz="UTC")),
          "CROSS_HOLDOUT_PRE2026":(pd.Timestamp("2023-01-01",tz="UTC"),pd.Timestamp("2025-12-31",tz="UTC")),
          "FINAL_SYMBOL_HOLDOUT_2026":(pd.Timestamp("2026-01-01",tz="UTC"),pd.Timestamp("2026-09-17",tz="UTC")),
          "ALL_2026":(pd.Timestamp("2026-01-01",tz="UTC"),pd.Timestamp("2026-09-17",tz="UTC")),
        }
        rec["frequency"]={sp:base.freq(d[mask&sm[sp]],*periods[sp]) for sp in sm}
        r2_26=base.metrics(d[d.r2&sm["ALL_2026"]]);a26=rec["ALL_2026"]["metrics"]
        rec["quality_vs_r2_all2026"]={
          "win24_delta_pp":a26["win24"]-r2_26["win24"],
          "mean24_delta_pct":a26["mean24"]-r2_26["mean24"],
          "up3_delta_pp":a26["up3_before_dn2"]-r2_26["up3_before_dn2"],
          "r2_quality_preserved":bool(a26["win24"]>=r2_26["win24"] and a26["mean24"]>=r2_26["mean24"])
        }
        result=rec
        status="DEV_STABLE_MOVEMENT_CLUSTER_EXPANSION"
        if rec["frequency"]["ALL_2026"]["signals_per_day"]>=2 and a26["mean24"]>0 and (a26["pf24"] or 0)>1:
            status="OOS_POSITIVE_MOVEMENT_CLUSTER_EXPANSION"
        if rec["frequency"]["ALL_2026"]["signals_per_day"]>=2 and rec["quality_vs_r2_all2026"]["r2_quality_preserved"]:
            status="TARGET_FREQUENCY_R2_QUALITY_PRESERVED"

    out={
      "status":status,"preflight":pf,
      "purpose":"Unsupervised nonlinear movement-state analysis: PCA and k-means are fit on Discovery movement features only; cluster subsets are selected using Discovery+Calibration outcomes; holdouts remain untouched until final evaluation.",
      "movement_features":len(feats),"pca_components":18,"ks":list(KS),
      "baselines":base.eval_baselines(d,sm),
      "champion":result,
      "cluster_reports":cluster_reports,
      "candidate_count":len(candidates),
      "top_candidates":[x[0] for x in candidates[:20]],
    }
    (a.outdir/"summary.json").write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    print(json.dumps({"status":status,"champion":result,"candidate_count":len(candidates)},ensure_ascii=False,allow_nan=False))

if __name__=="__main__":main()
