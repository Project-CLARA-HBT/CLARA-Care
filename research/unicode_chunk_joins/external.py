"""Score pinned catalogs and long nonstarter probes, optionally exporting native benchmark inputs."""

import argparse
import csv
import ctypes as c
import gettext
import hashlib
import io
import json
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import icu74 as icu
from compare import TARGETS, window

PINS = {
    "vi": "e16b70aca8589ab8b6a5f5692a1ace14b8737708ba2fd792b8320e9c91ab354b",
    "ko": "482727cd3763b9279d389539b584ee660a4a023156cecd4ccee06dab207ac2b2",
}
FIELDS = (
    "cuts",
    "direct",
    "safe",
    "errors",
    "unnecessary",
    "safe_gain_vs_union",
    "safe_loss_vs_union",
)


def native(name):
    return icu.bind(
        "unorm2_" + name,
        icu.integer,
        icu.ptr,
        icu.pointer(icu.unit),
        icu.integer,
        icu.integer,
        icu.pointer(icu.unit),
        icu.integer,
        icu.pointer(icu.integer),
    )


append = native("append")
normalize_append = native("normalizeSecondAndAppend")


def join(fn, form, left, right):
    a, b = icu.units(left), icu.units(right)
    capacity = len(a) + len(b) + 1
    while True:
        dest = (icu.unit * capacity)()
        c.memmove(dest, a, 2 * len(a))
        err = icu.integer()
        size = fn(icu.instance(form), dest, len(a), capacity, b, len(b), c.byref(err))
        if err.value != 15:
            icu.check(err)
            return bytes(dest)[: 2 * size].decode(icu.codec)
        capacity = size + 1


def cases(root):
    for lang, pin in PINS.items():
        data = (root / lang / "LC_MESSAGES/debconf.mo").read_bytes()
        if hashlib.sha256(data).hexdigest() != pin:
            raise ValueError(f"catalog digest mismatch for {lang}")
        catalog = gettext.GNUTranslations(io.BytesIO(data))._catalog
        for entry, key in enumerate(sorted(k for k in catalog if k), 1):
            original = catalog[key]
            for rendering, s in (("packaged", original), ("NFD", icu.normalize("NFD", original))):
                yield lang, rendering, entry, s, range(1, len(s))
    for length in (64, 256):
        # U+0316 has class 220 and cannot compose with A. Grave (230) can.
        for case, tail in (("ordered", "\u0316"), ("reordered", "\u0334"), ("remote", "\u0300")):
            s = "A" + "\u0316" * length + tail
            yield "stress", case, length, s, range(1, len(s))


def predictions(form, left, right):
    a, b = ord(left[-1]), ord(right[0])
    before = bool(icu.before(icu.instance(form), b))
    after = bool(icu.after(icu.instance(form), a))
    either = before or after
    bounded = either or window(form, left, right, 4)[0]
    cb = icu.ccc(b)
    form_aware = bounded if form.endswith("C") else cb == 0 or icu.ccc(a) <= cb
    return dict(
        before=before,
        after=after,
        union=either,
        window4=bounded,
        unbounded=either or window(form, left, right, None)[0],
        form_aware=form_aware,
        full=icu.is_normal(form, left + right),
        starter=cb == 0,
        pair=icu.is_normal(form, left[-1] + right[0]),
    )


def score(root, out, bench):
    stats = defaultdict(Counter)
    examples = {}
    for lang, rendering, entry, s, cuts in cases(root):
        for form in TARGETS:
            expected = icu.normalize(form, s)
            if expected != unicodedata.normalize(form, s):
                raise ValueError((lang, rendering, entry, form, "whole-input controls disagree"))
            for cut in cuts:
                left = icu.normalize(form, s[:cut])
                raw = s[cut:]
                right = icu.normalize(form, raw)
                direct = left + right
                repaired = join(append, form, left, right)
                streamed = join(normalize_append, form, left, raw)
                p = predictions(form, left, right)
                group = (lang, rendering, str(entry) if lang == "stress" else "all", form)
                if bench and lang != "stress":
                    fields = [x.encode("utf-16-le").hex() for x in (left, right, raw, expected)]
                    print(*group, int(p["form_aware"]), *fields, sep="\t", file=bench)
                safe = direct == expected
                for name, take in {
                    **p,
                    "append": repaired == direct,
                    "normalize_append": streamed == direct,
                }.items():
                    output = streamed if name == "normalize_append" else repaired
                    if name in p and take:
                        output = direct
                    cell = stats[group + (name,)]
                    cell.update(
                        dict(
                            zip(
                                FIELDS,
                                (
                                    1,
                                    take,
                                    safe,
                                    output != expected,
                                    safe and not take,
                                    safe and take and not p["union"],
                                    safe and not take and p["union"],
                                ),
                                strict=True,
                            )
                        )
                    )
                    if output != expected:
                        locator = "/".join((*group, name))
                        examples.setdefault(locator, {"entry": entry, "scalar_cut": cut})
    out.mkdir(parents=True, exist_ok=True)
    with (out / "counts.csv").open("w") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["corpus", "rendering", "run_length", "form", "policy", *FIELDS])
        for key, cell in sorted(stats.items()):
            writer.writerow([*key, *(cell[k] for k in FIELDS)])
    (out / "first-errors.json").write_text(json.dumps(examples, indent=2, sort_keys=True) + "\n")
    for key, cell in stats.items():
        if key[-1] not in {"starter", "pair"} and cell["errors"]:
            raise ValueError((key, cell))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("locale_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--bench-input", type=argparse.FileType("x"))
    args = parser.parse_args()
    score(args.locale_root, args.output, args.bench_input)
