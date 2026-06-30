"""Effective PHR feature-flag resolution (Component A / Req 18.1).

The PHR enhancement is governed by a master switch (``phr_enhanced_enabled``)
plus per-capability sub-flags. A sub-flag has effect only when the master flag
is also on, so callers never re-implement the ``master AND sub`` logic — they
ask :func:`phr_features` for the effective flags. With the master flag off every
effective flag is ``False`` and the legacy PHR behavior is preserved exactly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from clara_api.core.config import Settings, get_settings


@dataclass(frozen=True)
class PhrFeatureFlags:
    """Effective (``master AND sub``) PHR feature flags."""

    enhanced: bool
    consent_enforcement: bool
    reconciliation: bool
    allergy_aware_ddi: bool
    ocr_import: bool
    observations: bool
    export: bool
    sharing: bool
    reminders: bool
    completeness_meter: bool

    def as_dict(self) -> dict[str, bool]:
        return asdict(self)


def phr_features(settings: Settings | None = None) -> PhrFeatureFlags:
    """Resolve the effective PHR flags.

    Each sub-capability is ``master AND sub`` so that turning the master flag off
    reverts every enhancement at once (Requirement 18.1).
    """

    settings = settings or get_settings()
    master = bool(settings.phr_enhanced_enabled)

    def eff(sub: bool) -> bool:
        return master and bool(sub)

    return PhrFeatureFlags(
        enhanced=master,
        consent_enforcement=eff(settings.phr_consent_enforcement_enabled),
        reconciliation=eff(settings.phr_reconciliation_enabled),
        allergy_aware_ddi=eff(settings.phr_allergy_aware_ddi_enabled),
        ocr_import=eff(settings.phr_ocr_import_enabled),
        observations=eff(settings.phr_observations_enabled),
        export=eff(settings.phr_export_enabled),
        sharing=eff(settings.phr_sharing_enabled),
        reminders=eff(settings.phr_reminders_enabled),
        completeness_meter=eff(settings.phr_completeness_meter_enabled),
    )
