"""Measure a finite development ceiling using original integer ECG samples."""

import argparse
import csv
import hashlib
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import soundfile as sf

SOURCE = "https://physionet.org/files/ptb-xl/1.0.3/"
LEADS = "I II III AVR AVL AVF V1 V2 V3 V4 V5 V6".split()


def fetch(path, cache):
    target = cache / path
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(SOURCE + path, timeout=60) as response:
            target.write_bytes(response.read())
    return target.read_bytes()


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def encode(values):
    subtype = "PCM_16" if values.min() >= -32768 and values.max() <= 32767 else "PCM_24"
    if subtype == "PCM_16":
        pcm = values.astype(np.int16)
    else:
        assert values.min() >= -(1 << 23) and values.max() < (1 << 23)
        pcm = (values << 8).astype(np.int32)
    output = io.BytesIO()
    with sf.SoundFile(
        output,
        "w",
        samplerate=500,
        channels=values.shape[1],
        format="FLAC",
        subtype=subtype,
        compression_level=1.0,
    ) as stream:
        stream.write(pcm)
    size = output.getbuffer().nbytes
    assert size > 42 and output.getvalue().startswith(b"fLaC")
    output.seek(0)
    recovered, rate = sf.read(output, dtype="int32", always_2d=True)
    assert rate == 500
    recovered >>= 16 if subtype == "PCM_16" else 8
    np.testing.assert_array_equal(values, recovered)
    return size, recovered


def predictors(x, j):
    options = {"direct": np.zeros(len(x), dtype=np.int32)}
    i, ii = x.T[:2]
    if 2 <= j < 6:
        options["limb"] = [ii - i, (-(i + ii)) // 2, i - ii // 2, ii - i // 2][j - 2]
    for k in range(j):
        options[f"lead_{k}"] = x[:, k]
    if j >= 2:
        a, b = x[:, j - 1], x[:, j - 2]
        options["mean"] = (a + b) // 2
        options["linear"] = a * 2 - b
    return options


def measure(path, cache):
    header = fetch(path + ".hea", cache)
    blob = fetch(path + ".dat", cache)
    lines = [s.split() for s in header.decode().splitlines() if s and not s.startswith("#")]
    assert lines[0][1:4] == ["12", "500", "5000"]
    channels = lines[1:]
    assert [c[-1].upper() for c in channels] == LEADS
    assert all(c[1] == "16" and c[0] == Path(path).name + ".dat" for c in channels)
    # ADC values can be combined directly only under common gain and baseline.
    assert all(re.fullmatch(r"1000(?:\.0+)?\(0\)/mV", c[2]) for c in channels)
    x = np.frombuffer(blob, "<i2").astype(np.int32).reshape(5000, 12)
    np.testing.assert_array_equal(x[0], [int(c[5]) for c in channels])
    np.testing.assert_array_equal(x.sum(axis=0) % 65536, [int(c[6]) % 65536 for c in channels])
    baselines = {
        f"original_group_{width}": sum(encode(x[:, j : j + width])[0] for j in range(0, 12, width))
        for width in [2, 6]
    }
    by_lead = []
    for j in range(12):
        sizes = {}
        for name, prediction in predictors(x, j).items():
            size, recovered = encode((x[:, j] - prediction)[:, None])
            np.testing.assert_array_equal(recovered[:, 0] + prediction, x[:, j])
            sizes[name] = size
        by_lead.append(sizes)
    baselines.update(
        direct=sum(s["direct"] for s in by_lead),
        limb=sum(s.get("limb", s["direct"]) for s in by_lead),
        limb_chest=sum(
            s[f"lead_{j - 1}"] if j > 6 else s.get("limb", s["direct"])
            for j, s in enumerate(by_lead)
        ),
    )
    return {
        "record": Path(path).name,
        "adc_sha256": digest(blob),
        "header_sha256": digest(header),
        "bytes_by_lead": by_lead,
        "baselines": baselines,
        "free_choice_bytes": sum(min(s.values()) for s in by_lead),
    }


def main(cache):
    raw = fetch("ptbxl_database.csv", cache)
    paths = {}
    for row in csv.DictReader(io.StringIO(raw.decode())):
        if int(row["strat_fold"]) in range(1, 9):
            patient = row["patient_id"]
            candidate = (int(row["ecg_id"]), row["filename_hr"])
            paths[patient] = min(candidate, paths.get(patient, candidate))
    patients = sorted(paths, key=lambda p: (digest(p.encode()), p))[:32]
    assert len(patients) == 32
    with ThreadPoolExecutor(max_workers=4) as executor:
        records = list(executor.map(lambda p: measure(paths[p][1], cache), patients))
    totals = {name: sum(r["baselines"][name] for r in records) for name in records[0]["baselines"]}
    print(
        json.dumps(
            {
                "ptbxl": "1.0.3",
                "metadata_sha256": digest(raw),
                "soundfile": sf.__version__,
                "libsndfile": sf.__libsndfile_version__,
                "numpy": np.__version__,
                "baseline_bytes": totals,
                "free_choice_bytes": sum(r["free_choice_bytes"] for r in records),
                "records": records,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    main(parser.parse_args().cache)
