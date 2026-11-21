"""Paired development experiment on detached instructions and review findings."""

import argparse
import itertools
import json
import math
import sqlite3
import subprocess
import sys
from collections import Counter
from contextlib import closing
from pathlib import Path
from types import ModuleType

from . import pg_smallbank
from .reuse_spec import bank_instruction, finding_valid

ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = "services/api/src/clara_api/lifemap/review_findings.py"
REVISIONS = (
    "f7a33fd429814c6e1450bd987576e8c2a61b0d78",
    "2977d152adf1214947d9271cec73153ced9ea6a3",
)
IDS = ("a", "b", "c")
BANK_MANUAL = {"deposit": [], "withdraw": ["savings"], "check": ["savings", "checking"]}


class SqlAdapter:
    def __init__(self, db):
        self.db = db

    def execute(self, statement, params):
        return self.db.execute(statement.replace("%s", "?"), params)


def run_bank(operation, initial):
    watched = set()

    def observe(action, table, column, db_name, trigger):
        if action == sqlite3.SQLITE_READ and column == "bal":
            watched.add(table)
        return sqlite3.SQLITE_OK

    with closing(sqlite3.connect(":memory:", cached_statements=0)) as db:
        db.executescript((pg_smallbank.SOURCE / "schema.sql").read_text())
        db.execute("INSERT INTO accounts VALUES (1, ?)", ("0" * 64,))
        for table, balance in initial.items():
            db.execute(f"INSERT INTO {table} VALUES (1, ?)", (balance,))
        db.set_authorizer(observe)
        refused = False
        try:
            pg_smallbank.procedure(SqlAdapter(db), "ssi", operation, 0, [])
        except pg_smallbank.InsufficientSavings:
            refused = True
        db.set_authorizer(None)
        target, tenths = bank_instruction(operation, **initial)
        if refused != (target == "refused"):
            raise ValueError(("business decision mismatch", operation, initial))
        for table, balance in initial.items():
            actual, = db.execute(f"SELECT bal FROM {table}").fetchone()
            expected = balance + (tenths / 10 if table == target else 0)
            if not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-12):
                raise ValueError(("balance mismatch", operation, initial, table, actual, expected))
    return watched, (target, tenths)


def decision_row(family, case, before, after, labels, templates):
    return dict(
        family=family, case=case, before=before, after=after,
        original=labels[0], replay=labels[1], valid=labels[0] == labels[1],
        dependencies={arm: sorted(keys) for arm, keys in templates.items()},
        admit={arm: all(before[k] == after[k] for k in keys) for arm, keys in templates.items()},
    )


def bank_rows():
    states = [dict(savings=s, checking=c) for s, c in itertools.product((0, 21), (0, 6))]
    for operation, manual in BANK_MANUAL.items():
        observed = [run_bank(operation, state) for state in states]
        for i, j in itertools.product(range(len(states)), repeat=2):
            derived, original = observed[i]
            yield decision_row(operation, operation, states[i], states[j],
                               (original, observed[j][1]), dict(derived=derived, manual=manual))


class MembershipView:
    """Implement the validator's subset query by observing point membership reads."""

    def __init__(self, values, reads):
        self.values = values
        self.reads = reads

    def __ge__(self, requested):
        for ref in requested:
            self.reads.add(f"member.{ref}")
            if ref not in self.values:
                return False
        return True


class FieldView(dict):
    def __init__(self, values, reads):
        super().__init__(values)
        self.reads = reads

    def get(self, key, default=None):
        self.reads.add(f"field.{key}")
        return super().get(key, default)


def load_rule(revision):
    source = subprocess.check_output(["git", "show", f"{revision}:{VALIDATOR}"], cwd=ROOT)
    module = ModuleType(f"review_{revision}")
    sys.modules[module.__name__] = module  # dataclass annotations resolve via the defining module
    exec(compile(source, f"{revision}:{VALIDATOR}", "exec"), module.__dict__)
    return module.validate_model_proposals


def registry(state):
    return {ref: "history" if state[f"field.{ref}"] else "other"
            for ref in IDS if state[f"member.{ref}"]}


def findings(rule, proposal, fields, bound, reads=None):
    members = frozenset(fields)
    kwargs = dict(authorized_revision_ids=members)
    if reads is not None:
        kwargs["authorized_revision_ids"] = MembershipView(members, reads)
    if bound:
        kwargs["authorized_revision_fields"] = fields if reads is None else FieldView(fields, reads)
    return [finding.as_dict() for finding in rule([proposal], **kwargs)]


def clinical_rows():
    before = {f"{kind}.{ref}": True for kind in ("member", "field") for ref in IDS}
    for revision in REVISIONS:
        bound = revision == REVISIONS[1]
        rule = load_rule(revision)
        for refs in itertools.combinations(IDS, 2):
            proposal = dict(source="nli", revision_ids=list(refs), field_key="history",
                            relation="possible_duplicate")
            derived = set()
            original = findings(rule, proposal, registry(before), bound)
            if len(original) != 1 or findings(rule, proposal, registry(before), bound, derived) != original:
                raise ValueError(("preparation mismatch", revision, refs))
            lag = {f"member.{ref}" for ref in refs}
            manual = lag | ({f"field.{ref}" for ref in refs} if bound else set())
            templates = dict(derived=derived, manual=manual, lag=lag)
            for bits in itertools.product((False, True), repeat=len(before)):
                after = dict(zip(before, bits, strict=True))
                fields = registry(after)
                replay = findings(rule, proposal, fields, bound)
                if (original == replay) != finding_valid(refs, fields, bound):
                    raise ValueError(("registry specification mismatch", revision, refs, after))
                yield decision_row(revision[:8], refs, before, after, (original, replay), templates)


def summarize(rows):
    summary = {}
    for row in rows:
        counts = summary.setdefault(row["family"], Counter())
        valid, arms = row["valid"], row["admit"]
        counts["valid" if valid else "invalid"] += 1
        for arm, admit in arms.items():
            counts[f"{arm}_false_admit"] += int(admit and not valid)
            counts[f"{arm}_false_reject"] += int(valid and not admit)
            if arm != "derived":
                outcome = "tie" if arms["derived"] == admit else "win" if arms["derived"] == valid else "loss"
                counts[f"vs_{arm}_{outcome}"] += 1
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", type=Path)
    args = parser.parse_args()
    rows = [*bank_rows(), *clinical_rows()]
    args.rows.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))
    print(json.dumps(summarize(rows), indent=2))


if __name__ == "__main__":
    main()
