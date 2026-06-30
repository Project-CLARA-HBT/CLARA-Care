"""Observability building blocks for the CLARA Admin & Observability feature.

Feature: clara-admin-observability

This package hosts the additive, flag-gated observability modules (alert engine,
admin-action audit trail, durable flow-event sink). Every capability is default
off; with its flag disabled the module is inert and adds no write path, so
request/response shapes equal the pre-feature baseline (Requirement 12.2).
"""

from __future__ import annotations
