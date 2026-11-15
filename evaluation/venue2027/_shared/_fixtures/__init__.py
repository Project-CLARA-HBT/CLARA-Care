"""Shared evaluation fixture package (tiny real candidate/baseline modules).

These modules exist so the oracle independence scan has REAL candidate and
baseline code to scan against — they are not mocks of the oracle. The oracle
contract must refuse importing any of them.
"""

from __future__ import annotations
