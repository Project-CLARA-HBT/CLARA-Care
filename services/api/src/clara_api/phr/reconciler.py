"""Unified medication reconciliation + allergy-aware conflict logic (Component F).

Pure functions consumed by ``careguard.auto-ddi-check`` (and surfaced via a PHR
reconciliation projection). Reconciliation is a *read-time projection*: it never
mutates or drops the PHR medication list or the ``MedicineCabinet`` — both source
stores are preserved and referenced (Req 7.1, 7.2, 7.6, Correctness Property 8).

Items sharing a non-empty RXCUI collapse into one reconciled medication; uncoded
items are keyed by normalized name so they are conserved but never wrongly merged.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReconciledMedication:
    """One reconciled medication grouping PHR + cabinet source references."""

    key: str
    rx_cui: str
    display_name: str
    normalized_name: str
    # Source-record references retained for both stores (Req 7.2, 7.6).
    sources: dict[str, list[str]] = field(default_factory=lambda: {"phr": [], "cabinet": []})

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "rx_cui": self.rx_cui,
            "display_name": self.display_name,
            "normalized_name": self.normalized_name,
            "sources": {"phr": list(self.sources["phr"]), "cabinet": list(self.sources["cabinet"])},
        }


@dataclass
class ReconciliationResult:
    medications: list[ReconciledMedication]

    def as_dict(self) -> dict:
        return {"medications": [m.as_dict() for m in self.medications]}


def _grouping_key(rx_cui: str, normalized_name: str, store: str, source_id: str) -> str:
    rx_cui = (rx_cui or "").strip()
    if rx_cui:
        return f"rxcui:{rx_cui}"
    normalized = (normalized_name or "").strip().lower()
    if normalized:
        return f"name:{normalized}"
    # Uncoded + unnamed: keep distinct so nothing is lost (conservation).
    return f"{store}:{source_id}"


def reconcile(
    phr_meds: list[dict],
    cabinet_items: list[dict],
) -> ReconciliationResult:
    """Reconcile PHR meds with cabinet items keyed by RXCUI (Req 7.1, 7.2, 7.6).

    ``phr_meds`` items are dicts with ``id``/``rx_cui``/``normalized_name``/
    ``name``; ``cabinet_items`` are dicts with ``id``/``rx_cui``/
    ``normalized_name``/``drug_name``. Every input id appears in exactly one
    reconciled group's source refs; inputs are never mutated or dropped.
    """

    groups: dict[str, ReconciledMedication] = {}

    def _ingest(item: dict, store: str) -> None:
        source_id = str(item.get("id") or "")
        rx_cui = str(item.get("rx_cui") or "").strip()
        normalized_name = str(item.get("normalized_name") or "").strip()
        display_name = str(item.get("name") or item.get("drug_name") or normalized_name or "")
        key = _grouping_key(rx_cui, normalized_name, store, source_id)
        group = groups.get(key)
        if group is None:
            group = ReconciledMedication(
                key=key,
                rx_cui=rx_cui,
                display_name=display_name,
                normalized_name=normalized_name,
            )
            groups[key] = group
        else:
            # Prefer a non-empty rx_cui / display once known.
            if not group.rx_cui and rx_cui:
                group.rx_cui = rx_cui
            if not group.display_name and display_name:
                group.display_name = display_name
            if not group.normalized_name and normalized_name:
                group.normalized_name = normalized_name
        group.sources[store].append(source_id)

    for item in phr_meds:
        _ingest(item, "phr")
    for item in cabinet_items:
        _ingest(item, "cabinet")

    return ReconciliationResult(medications=list(groups.values()))


def find_allergy_conflicts(
    reconciled: ReconciliationResult,
    allergies: list[dict],
) -> list[dict]:
    """Surface medication↔allergy conflicts (Req 7.4, Correctness Property 9).

    A conflict exists iff a reconciled medication matches a recorded allergy under
    the conflict rule: same coded substance id matching the medication RXCUI, or a
    normalized-name substring match between the allergy substance and the
    medication's normalized/display name.
    """

    conflicts: list[dict] = []
    for med in reconciled.medications:
        med_rxcui = (med.rx_cui or "").strip()
        med_name = (med.normalized_name or med.display_name or "").strip().lower()
        for allergy in allergies:
            substance = str(allergy.get("substance") or allergy.get("name") or "").strip().lower()
            coded_id = str(allergy.get("coded_substance_id") or "").strip()
            matched = False
            reason = ""
            if coded_id and med_rxcui and coded_id == med_rxcui:
                matched = True
                reason = "rxcui"
            elif substance and med_name and (substance in med_name or med_name in substance):
                matched = True
                reason = "name"
            if matched:
                conflicts.append(
                    {
                        "medication_key": med.key,
                        "medication": med.display_name,
                        "allergy": str(allergy.get("name") or allergy.get("substance") or ""),
                        "severity": str(allergy.get("severity") or "unknown"),
                        "match": reason,
                    }
                )
    return conflicts
