"""Reconstruct a fixed regional predictor's exact error on measured fields."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]


def errors(folder, truth, start):
    rows = list(csv.DictReader((ROOT/folder/"fields.csv").open()))
    field_ids = np.arange(start, start + len(truth))
    parts = {}
    for arm in ("pattern", "boost_pattern"):
        vals = [r for r in rows if r["arm"]==arm]
        assert [int(r.get("index",r.get("training_index"))) for r in vals] == field_ids.tolist()
        parts[arm] = np.array([[float(r[k]) for k in ("all","interior","exterior")] for r in vals])
    mask = np.ones((32,32),bool)
    mask[::2,::2] = False
    edge = np.indices((32,32)).max(axis=0)==31
    weight = np.square(truth[:,mask & ~edge]).sum(1)/np.square(truth[:,mask]).sum(1)
    def join(i,e):
        return np.sqrt(weight*parts[i][:,1]**2 + (1-weight)*parts[e][:,2]**2)
    for name in parts:
        np.testing.assert_allclose(join(name,name),parts[name][:,0],rtol=5e-6)
    return {"pattern":parts["pattern"][:,0],"boost":parts["boost_pattern"][:,0],
            "pattern_inside":join("pattern","boost_pattern"),"boost_inside":join("boost_pattern","pattern")}


if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    for key in ("neuralop","pdeinv","pdebench","out"):
        ap.add_argument(key,type=Path)
    args=ap.parse_args()
    args.out.mkdir(exist_ok=True,parents=True)
    groups=[("material_patterns",args.neuralop,512,640),("pdeinv241",args.pdeinv,128,192),
            ("pdebench_screen",args.pdebench,128,192),("independent_generator",None,512,640)]
    summary={}
    with (args.out/"fields.csv").open("w") as f:
        writer=csv.writer(f,lineterminator="\n")
        writer.writerow(["cohort","field","pattern","boost","pattern_inside","boost_inside"])
        for folder,path,start,stop in groups:
            if path is None:
                truth=np.load(ROOT/folder/"fields.npz")["pressure"][start:stop]
            else:
                truth=torch.load(path/"darcy_train_32.pt",weights_only=True)["y"][start:stop].numpy()
            scores=errors(folder,truth.astype(float),start)
            writer.writerows((folder,i,*v) for i,v in enumerate(zip(*scores.values()),start))
            candidate=scores["pattern_inside"]
            summary[folder]={k:{"mean":v.mean(),"gain_pct":100*(1-candidate.mean()/v.mean()),
                                "wins":int(np.sum(candidate<v))} for k,v in scores.items()}
    (args.out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
