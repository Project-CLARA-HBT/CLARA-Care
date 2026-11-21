"""Record the balance comparisons of the pinned three-procedure SmallBank port."""

import argparse
import json
import re
from pathlib import Path

from . import pg_smallbank
from .reuse_derivation import bank_rows, summarize


def value(expr, state):
    if isinstance(expr, str):
        return state[expr]
    if isinstance(expr, (int, float)):
        return expr
    op, left, right = expr
    a, b = value(left, state), value(right, state)
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "<":
        return a < b
    raise ValueError(op)


class Balance:
    def __init__(self, expr, connection):
        self.expr = expr
        self.connection = connection

    def __add__(self, other):
        return Balance(("+", self.expr, other.expr), self.connection)

    def __sub__(self, constant):
        return Balance(("-", self.expr, constant), self.connection)

    def __lt__(self, threshold):
        expr = ("<", self.expr, threshold)
        taken = value(expr, self.connection.state)
        self.connection.guards.append((expr, taken))
        return taken


class TraceConnection:
    """Model the fixed account and accept only the SQL shapes used in preparation."""

    def __init__(self, state):
        self.state = state
        self.guards = []
        self.instruction = None
        self.row = None

    def execute(self, sql, params):
        self.row = None
        if sql == "SELECT * FROM accounts WHERE name=%s" and params == ("0" * 64,):
            self.row = (1, params[0])
        elif match := re.fullmatch(r"SELECT bal FROM (checking|savings) WHERE custid=%s", sql):
            if params != (1,):
                raise ValueError(params)
            self.row = (Balance(match[1], self),)
        elif match := re.fullmatch(
            r"UPDATE (checking|savings) SET bal=bal([+-])%s WHERE custid=%s", sql
        ):
            delta, key = params
            if self.instruction or type(delta) not in (float, int) or key != 1:
                raise ValueError(params)
            self.instruction = (match[1], round(10 * delta) * (1 if match[2] == "+" else -1))
        else:
            raise ValueError(sql)
        return self

    def fetchone(self):
        return self.row


def prepare(operation, before):
    trace = TraceConnection(before)
    try:
        pg_smallbank.procedure(trace, "ssi", operation, 0, [])
    except pg_smallbank.InsufficientSavings:
        if trace.instruction is not None:
            raise ValueError("unexpected write before refusal")
        trace.instruction = ("refused", 0)
    return trace


def manual_class(operation, state):
    if operation == "deposit":
        return True
    if operation == "withdraw":
        return state["savings"] >= 20.2
    if operation == "check":
        return state["checking"] + state["savings"] >= 5
    raise ValueError(operation)


def rows():
    for row in bank_rows():
        op, before, after = row["case"], row["before"], row["after"]
        trace = prepare(op, before)
        if trace.instruction != row["original"]:
            raise ValueError(("trace instruction disagrees with replay", op, before))
        row["guards"] = trace.guards
        row["admit"] = {
            "coordinate_derived": row["admit"]["derived"],
            "coordinate_manual": row["admit"]["manual"],
            "derived": all(value(expr, after) == taken for expr, taken in trace.guards),
            "manual": manual_class(op, before) == manual_class(op, after),
        }
        row["coordinate_dependencies"] = row.pop("dependencies")
        yield row


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output
    paired = list(rows())
    output.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in paired))
    print(json.dumps(summarize(paired), indent=2))
