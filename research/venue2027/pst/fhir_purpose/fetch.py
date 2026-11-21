"""Download the references and all examples linked by the R5 publication."""

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import urlopen


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.examples = set()

    def handle_starttag(self, tag, attrs):
        ref = dict(attrs).get("href") or ""
        if tag == "a" and ref.endswith(".json.html") and "/" not in ref:
            self.examples.add(ref.removesuffix(".html"))


ROOT = "https://hl7.org/fhir/R5/"
THO = "https://terminology.hl7.org/5.1.0/"
REFERENCES = [
    ROOT + "auditevent-examples.html",
    ROOT + "auditevent.profile.json",
    THO + "ValueSet-v3-PurposeOfUse.json",
    THO + "CodeSystem-v3-ActReason.json",
]


def fetch(out, url):
    with urlopen(url, timeout=45) as res:
        data = res.read()
    (out / url.rsplit("/", 1)[-1]).write_bytes(data)
    return dict(url=url, sha256=hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("scratch", type=Path)
    work = p.parse_args().scratch
    work.mkdir(exist_ok=False)
    refs = [fetch(work, REFERENCES[0])]
    parser = Links()
    parser.feed((work / "auditevent-examples.html").read_text())
    if len(parser.examples) != 13:
        raise ValueError("example catalog changed")
    with ThreadPoolExecutor(max_workers=4) as pool:
        refs += list(
            pool.map(
                lambda u: fetch(work, u),
                REFERENCES[1:] + [ROOT + n for n in sorted(parser.examples)],
            )
        )
    print(json.dumps(refs, indent=2))
