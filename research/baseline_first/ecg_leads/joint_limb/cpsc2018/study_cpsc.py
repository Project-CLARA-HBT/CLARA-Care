"""Score authenticated public CPSC ECG records selected by hashed path."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import time

import numpy as np
import requests
from scipy.io import loadmat

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from study import ARMS, encode, decode

BASE = "https://physionet.org/files/challenge-2021/1.0.3/training/cpsc_2018/"
LEADS = "I II III AVR AVL AVF V1 V2 V3 V4 V5 V6".split()


def hash_bytes(data):
    return hashlib.sha256(data).hexdigest()


def get(url):
    for attempt in range(4):
        try:
            response = requests.get(url,timeout=45)
            response.raise_for_status()
            return response.content
        except requests.RequestException:
            if attempt==3:
                raise
            time.sleep(2**attempt)


def choose():
    groups = re.findall(rb'href="(g\d+/)"',get(BASE))
    paths = [group.decode()+file.decode() for group in groups
             for file in re.findall(rb'href="(A\d+\.hea)"',get(BASE+group.decode()))]
    assert len(paths)==6877 and len(set(paths))==6877
    return sorted(paths,key=lambda path:hash_bytes(path.encode()))[:32]


def read_record(path,cache):
    def fetch(name):
        file = cache/name
        if not file.exists():
            file.parent.mkdir(exist_ok=True,parents=True)
            data=get(BASE+name)
            file.write_bytes(data)
        return file.read_bytes()
    header = fetch(path)
    mat = fetch(path.replace(".hea",".mat"))
    lines=[line.split() for line in header.decode().splitlines() if line and not line.startswith("#")]
    assert lines[0][1:3]==["12","500"]
    sigs=lines[1:]
    assert [s[-1].upper() for s in sigs]==LEADS
    assert all(re.fullmatch(r"1000(?:\.0+)?(?:\(0\))?/mV",s[2]) and int(s[4])==0 for s in sigs)
    raw=loadmat(io.BytesIO(mat))["val"]
    assert np.issubdtype(raw.dtype,np.integer)
    assert raw.shape==(12,int(lines[0][3]))
    assert np.array_equal(raw[:,0],[int(s[5]) for s in sigs])
    assert np.array_equal(raw.sum(axis=1)%65536,[int(s[6])%65536 for s in sigs])
    adc=raw[:,:5000].T.astype(np.int64)
    row=dict(record=path,header_sha256=hash_bytes(header),mat_sha256=hash_bytes(mat),
             n=len(adc),raw_length=raw.shape[1])
    for arm in ARMS:
        stream=encode(adc,arm)
        np.testing.assert_array_equal(decode(stream),adc)
        row[arm]=len(stream)
    return row


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("cache",type=Path)
    cache=ap.parse_args().cache
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(lambda p:read_record(p,cache),choose()))
    print(json.dumps({"rows":rows,"totals":{arm:sum(r[arm] for r in rows) for arm in ARMS}},indent=2))
