"""Personal Health Record (enhanced) pure-logic services.

Every capability in this package is additive and gated behind a PHR feature flag
that defaults OFF (see :mod:`clara_api.phr.features`). With all flags off the
legacy ``GET/PUT /api/v1/phr/record`` path and CareGuard's cabinet-only DDI path
stay byte-for-byte equivalent to today (Requirement 18.1, Correctness Property
22). The modules here are deliberately free of FastAPI/HTTP concerns so they can
be unit/property-tested in isolation and reused by the API endpoints, CareGuard,
and the research personal-context builder.
"""
