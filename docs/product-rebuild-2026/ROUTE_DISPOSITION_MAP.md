# CLARA Care Product Rebuild — Route Disposition Map

**Status:** Canonical Reference  
**Date:** 2026-08-19  

---

## 1. Web Route Matrix

| Legacy / Current Path | Target Disposition | Canonical Target | Access Roles | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `/` | Canonical | `/` (Public) | Public | Modern consumer-first landing page |
| `/login` | Canonical | `/login` | Public | Light-first accessible login |
| `/register` | Canonical | `/register` | Public | Account creation |
| `/legal/*` | Canonical | `/legal/*` | Public | Terms, Privacy, Consent, Cookies |
| `/welcome/*` | Canonical | `/welcome/*` | Authenticated | Goal-first progressive onboarding |
| `/today` | Redirect | `/home` | Normal, Doctor, Admin | 308 permanent redirect to `/home` |
| `/home` | Canonical | `/home` | Normal, Doctor, Admin | New consumer daily health home |
| `/chat` | Redirect (Consumer) | `/ask` | Normal | Consumer requests redirect to `/ask` |
| `/ask` | Canonical | `/ask` | Normal, Doctor, Admin | Simple multimodal consumer assistant |
| `/phr` | Redirect | `/health` | Normal, Doctor, Admin | 308 redirect to `/health` |
| `/lifemap` | Redirect | `/health/timeline` | Normal, Doctor, Admin | 308 redirect to `/health/timeline` |
| `/health` | Canonical | `/health` | Normal, Doctor, Admin | Unified health overview projection |
| `/health/timeline` | Canonical | `/health/timeline` | Normal, Doctor, Admin | Longitudinal timeline with filters |
| `/health/medications` | Canonical | `/health/medications` | Normal, Doctor, Admin | Unified medication hub |
| `/health/results` | Canonical | `/health/results` | Normal, Doctor, Admin | Results list, detail, and trend |
| `/health/measurements`| Canonical | `/health/measurements`| Normal, Doctor, Admin | Discrete vitals & device metrics |
| `/health/documents` | Canonical | `/health/documents` | Normal, Doctor, Admin | Uploaded & extracted documents |
| `/medicines` | Redirect | `/health/medications` | Normal, Doctor, Admin | 308 redirect to `/health/medications` |
| `/careguard` | Redirect | `/health/medications` | Normal, Doctor, Admin | Legacy route redirect |
| `/selfmed/*` | Redirect | `/health/medications` | Normal, Doctor, Admin | Legacy cabinet routes redirect |
| `/visits` | Redirect | `/care/visits` | Normal, Doctor, Admin | 308 redirect to `/care/visits` |
| `/care` | Canonical | `/care` | Normal, Doctor, Admin | Unified care hub |
| `/care/visits` | Canonical | `/care/visits` | Normal, Doctor, Admin | Appointments & visit prep |
| `/care/prepare` | Canonical | `/care/prepare` | Normal, Doctor, Admin | Visit preparation generator |
| `/care/check-symptoms`| Canonical | `/care/check-symptoms`| Normal, Doctor, Admin | Care navigation & triage |
| `/family` | Redirect | `/you/sharing` | Normal, Doctor, Admin | 308 redirect to `/you/sharing` |
| `/you` | Canonical | `/you` | Normal, Doctor, Admin | Account, profile & trust hub |
| `/you/profile` | Canonical | `/you/profile` | Normal, Doctor, Admin | Demographics & emergency card |
| `/you/sharing` | Canonical | `/you/sharing` | Normal, Doctor, Admin | Family circle & access grants |
| `/you/privacy` | Canonical | `/you/privacy` | Normal, Doctor, Admin | Consent, AI transparency, DSAR |
| `/you/integrations` | Canonical | `/you/integrations` | Normal, Doctor, Admin | Connected health sync status |
| `/you/notifications` | Canonical | `/you/notifications` | Normal, Doctor, Admin | Notification preferences |
| `/account/consent` | Redirect | `/you/privacy` | Normal, Doctor, Admin | 308 redirect to `/you/privacy` |
| `/account/data` | Redirect | `/you/privacy` | Normal, Doctor, Admin | 308 redirect to `/you/privacy` |
| `/council/*` | Professional | `/council/*` | Doctor, Admin | Multi-specialty clinical council |
| `/scribe/*` | Professional | `/scribe/*` | Doctor, Admin | Ambient clinical note assistant |
| `/research/*` | Professional | `/research/*` | Researcher, Doctor, Admin | Evidence synthesis & PICO search |
| `/dashboard` | Professional | `/dashboard` | Doctor, Researcher, Admin | Professional overview |
| `/admin/*` | Admin | `/admin/*` | Admin | Control tower, RAG, observability |

---

## 2. Mobile Destination Matrix

| Destination | Disposition | Target Screen | Roles |
| :--- | :--- | :--- | :--- |
| **Hôm nay (Home)** | Canonical | `HomeScreenV2` (Daily priority, schedule, recent changes) | All |
| **Sức khỏe (Health)**| Canonical | `HealthHubScreen` (Overview, timeline, medications, results) | All |
| **Ask CLARA** | Canonical | `AskScreen` (Center floating action, simple composer) | All |
| **Chăm sóc (Care)** | Canonical | `CareHubScreen` (Visits, prep, check-symptoms) | All |
| **Bạn (You)** | Canonical | `YouHubScreen` (Profile, sharing, privacy, integrations) | All |
| **Chuyên môn (Pro)** | Professional | `ProfessionalHubScreen` (Council, Scribe, Evidence) | Doctor, Admin |
