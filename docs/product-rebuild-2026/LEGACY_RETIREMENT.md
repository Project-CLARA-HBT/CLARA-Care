# CLARA Care Product Rebuild — Legacy Retirement & Migration Plan

**Status:** Normative Guidance  
**Date:** 2026-08-19  

---

## 1. Executive Summary

This document establishes the retirement criteria and disposition schedule for legacy frontend routes, duplicated UI components, and deprecated API contracts under the Consumer-First Product Rebuild.

In accordance with RFC strangler-migration principles (**MIG-001**):
1. No working safety-critical code or endpoint is deleted on flag-day.
2. Canonical replacements provide full functional and semantic parity before legacy code is decommissioned.
3. Compatibility adapters and HTTP 308 permanent redirects preserve direct deep links and bookmarks (**PRD-004**, **MIG-007**).

---

## 2. Route Disposition & Retirement Schedule

| Route / Module | Classification | Canonical Target | Current Status | Retirement Gate |
| :--- | :--- | :--- | :--- | :--- |
| `/today` | Redirect | `/home` | **Active 308 Redirect** | 100% consumer canary + 30-day zero-traffic window |
| `/chat` (consumer) | Redirect | `/ask` | **Active 308 Redirect** | 100% consumer canary + 30-day zero-traffic window |
| `/phr` | Redirect | `/health` | **Active 308 Redirect** | 100% consumer canary + 30-day zero-traffic window |
| `/lifemap` | Redirect | `/health/timeline` | **Active 308 Redirect** | 100% consumer canary + 30-day zero-traffic window |
| `/medicines` | Redirect | `/health/medications` | **Active 308 Redirect** | 100% consumer canary + 30-day zero-traffic window |
| `/careguard` | Redirect | `/health/medications` | **Active 308 Redirect** | 100% consumer canary + 30-day zero-traffic window |
| `/selfmed/*` | Redirect | `/health/medications` | **Active 308 Redirect** | 100% consumer canary + 30-day zero-traffic window |
| `/visits` | Redirect | `/care/visits` | **Active 308 Redirect** | 100% consumer canary + 30-day zero-traffic window |
| `/family` | Redirect | `/you/sharing` | **Active 308 Redirect** | 100% consumer canary + 30-day zero-traffic window |
| `/account/consent` | Redirect | `/you/privacy` | **Active 308 Redirect** | 100% consumer canary + 30-day zero-traffic window |
| `/account/data` | Redirect | `/you/privacy` | **Active 308 Redirect** | 100% consumer canary + 30-day zero-traffic window |
| `/council/*` | Professional Mode | `/council/*` | **Preserved (Role-Gated)**| Retained in clinician workspace |
| `/scribe/*` | Professional Mode | `/scribe/*` | **Preserved (Role-Gated)**| Retained in clinician workspace |
| `/research/*` | Professional Mode | `/research/*` | **Preserved (Role-Gated)**| Retained in researcher workspace |
| `/dashboard` | Professional Mode | `/dashboard` | **Preserved (Role-Gated)**| Retained in pro workspace |
| `/admin/*` | Admin Mode | `/admin/*` | **Preserved (Admin-Only)**| Retained in admin control tower |

---

## 3. Backend API Retirement Schedule

| Legacy API Endpoint | Status | Canonical Replacement | Retirement Condition |
| :--- | :--- | :--- | :--- |
| `PUT /api/v1/phr/record` (Whole-record upsert) | Deprecated (Compatibility) | `PATCH /api/v2/health/demographics`<br>`POST /api/v2/health/allergies`<br>`POST /api/v2/health/conditions` | Minimum client version migration complete; zero mobile v1 client traffic |
| `/api/v1/lifemap/today` | Active (v1 support) | `GET /api/v2/home` | Retained for old client backward compatibility |
| `/api/v1/chat` (unstructured) | Active (v1 support) | `POST /api/v2/ask` | Retained for legacy integration compatibility |

---

## 4. Feature Flag Decommissioning Plan

1. **`consumer_shell_v2`**: Default `true` across environments. To be removed after 30-day stabilization.
2. **`consumer_home_v2`**: Default `true`. To be removed after 30-day stabilization.
3. **`consumer_health_v2`**: Default `true`. To be removed after 30-day stabilization.
4. **`consumer_care_v2`**: Default `true`. To be removed after 30-day stabilization.
5. **`consumer_ask_simple_composer`**: Default `true`. To be removed after 30-day stabilization.
6. **`universal_capture_v2`**: Default `true`. To be removed after 30-day stabilization.
7. **`model_gateway_v2`**: Active and authoritative for task-first routing.
8. **`model_route_gemini_fast` & `model_route_gemini_quality`**: Feature-flag gated deployment aliases; promotable per task based on locked benchmark evidence.
