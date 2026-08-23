# Route capability matrix

This manifest is the pre-M2 reachability gate. Every `apps/web/app/**/page.tsx` route is classified exactly once. `Primary`, `More`, `Context`, `Alias`, `Public`, and `Utility` describe presentation only; `Access` remains enforced by the server and the route registry.

| Route | Access | Workspace | Presentation/disposition | Redirect or test |
|---|---|---|---|---|
| `/` | public | — | Public landing | public E2E |
| `/login` | public | — | Public auth | public E2E |
| `/register` | public | — | Public auth | public E2E |
| `/forgot-password` | public | — | Public auth | public E2E |
| `/reset-password` | public | — | Public auth | public E2E |
| `/verify-email` | public | — | Public auth | public E2E |
| `/legal` | public | — | Public legal | public E2E |
| `/legal/consent` | public | — | Public legal | public E2E |
| `/legal/cookies` | public | — | Public legal | public E2E |
| `/legal/privacy` | public | — | Public legal | public E2E |
| `/legal/terms` | public | — | Public legal | public E2E |
| `/share/[token]` | public capability | — | Public share; shell-free | public-share E2E |
| `/phr/shared/[token]` | public capability | — | Public PHR share; shell-free | public-share E2E |
| `/today` | authenticated all roles | personal | Primary Personal; professional direct/context | role E2E |
| `/today/tasks/[taskId]` | authenticated owner/profile | personal | Context from Today | task E2E |
| `/lifemap` | authenticated owner/profile | personal | Primary Personal | personal E2E |
| `/lifemap/new` | authenticated owner/profile | personal | Context/create entry | flow E2E |
| `/lifemap/new/[draftId]/[step]` | authenticated owner/profile | personal | Guided step; server draft | flow/deep-link E2E |
| `/lifemap/visit-prep` | authenticated owner/profile | personal | Compatibility/context to Visit | compatibility E2E |
| `/visits` | authenticated owner/profile | personal | More Personal | visit E2E |
| `/visits/new` | authenticated owner/profile | personal | Context/guided create | visit E2E |
| `/family` | authenticated owner/profile | personal | More Personal | family E2E |
| `/family/invite` | authenticated owner/profile | personal | Context/guided share | family E2E |
| `/family/accept` | authenticated recipient capability | personal | Context/preview then accept | family E2E |
| `/phr` | authenticated permitted profile | personal/clinical context | Primary Personal; More Clinical | PHR E2E |
| `/phr/[section]` | authenticated permitted profile | personal/clinical context | Context focused form | PHR E2E |
| `/medicines` | authenticated owner/profile | personal | Primary Personal | medicines E2E |
| `/medicines/add` | authenticated owner/profile + consent | personal | Context guided add | medicines E2E |
| `/medicines/cabinet/add` | authenticated owner/profile + consent | personal | Context shared cabinet add | medicines E2E |
| `/selfmed` | authenticated owner/profile + consent | personal | Alias only | redirect → medicines cabinet |
| `/selfmed/add` | authenticated owner/profile + consent | personal | Alias/shared component | redirect/shared flow |
| `/selfmed/ddi` | authenticated owner/profile + consent | personal | Alias only | redirect → medicines safety |
| `/careguard` | authenticated owner/profile + consent | personal | Alias only | redirect → medicines safety |
| `/chat` | authenticated all roles | personal/research/clinical | Primary in all permitted workspaces | Chat E2E |
| `/chat/shares` | authenticated owner | research/personal context | More Chat | share E2E |
| `/evidence` | authenticated permitted role | research | Primary Research; More Clinical | evidence E2E |
| `/research` | authenticated permitted role | research | Alias only | redirect → Chat |
| `/research/analyze` | authenticated permitted role | research | Alias only | redirect → Chat |
| `/research/citations` | authenticated permitted role | research | Alias only | redirect → Chat |
| `/research/deepdive` | authenticated permitted role | research | Alias only | redirect → Chat |
| `/research/details` | authenticated permitted role | research | Alias only | redirect → Chat |
| `/research/source-hub` | authenticated researcher/doctor/admin | research | Primary Research; More Admin | source E2E |
| `/council` | authenticated doctor/admin | clinical | Primary Clinical | council E2E |
| `/council/new` | authenticated doctor/admin | clinical | Context/guided create | council E2E |
| `/council/new/intake` | authenticated doctor/admin | clinical | Guided step | council E2E |
| `/council/new/specialists` | authenticated doctor/admin | clinical | Guided step | council E2E |
| `/council/new/review` | authenticated doctor/admin | clinical | Guided review/run | council E2E |
| `/council/result` | authenticated doctor/admin + owner/access | clinical | Context result | council E2E |
| `/council/analyze` | authenticated doctor/admin + owner/access | clinical | Result detail/compatibility | council E2E |
| `/council/citations` | authenticated doctor/admin + owner/access | clinical | Result detail/compatibility | council E2E |
| `/council/deepdive` | authenticated doctor/admin + owner/access | clinical | Expert detail/compatibility | council E2E |
| `/council/details` | authenticated doctor/admin + owner/access | clinical | Expert detail/compatibility | council E2E |
| `/council/research` | authenticated doctor/admin + owner/access | clinical/research | Result evidence detail | council E2E |
| `/scribe` | authenticated doctor/admin | clinical | Primary Clinical | scribe E2E |
| `/clinical` | authenticated doctor/admin | clinical | Primary Clinical | clinical E2E |
| `/clinical/overview` | authenticated doctor/admin | clinical | More Clinical | clinical E2E |
| `/dashboard` | authenticated researcher/doctor/admin (client may allow legacy; server authoritative) | clinical/admin/research context | Primary Clinical/Admin home by role | role E2E |
| `/dashboard/control-tower` | authenticated admin | admin | More Admin | admin E2E |
| `/dashboard/ecosystem` | authenticated admin | admin | More Admin | admin E2E |
| `/admin` | authenticated admin | admin | Alias only | redirect → admin/overview |
| `/admin/overview` | authenticated admin | admin | Primary Admin | admin E2E |
| `/admin/knowledge-sources` | authenticated admin | admin | Primary Admin | admin E2E |
| `/admin/answer-flow` | authenticated admin | admin | Primary Admin | admin E2E |
| `/admin/observability` | authenticated admin | admin | Primary Admin | admin E2E |
| `/admin/analytics` | authenticated admin | admin | Primary Admin | admin E2E |
| `/admin/analytics/clinical` | authenticated admin | admin | More Admin | admin E2E |
| `/admin/community-moderation` | authenticated admin + social flag | admin | More Admin | admin E2E |
| `/admin/dsar` | authenticated admin + compliance flag | admin | More Admin | admin E2E |
| `/admin/audit-log` | authenticated admin | admin | More Admin | admin E2E |
| `/admin/rag-eval` | authenticated admin | admin | More Admin | admin E2E |
| `/admin/rag-ingestion` | authenticated admin + flag | admin | More Admin | admin E2E |
| `/admin/rag-sources` | authenticated admin | admin | Alias only | redirect → knowledge sources |
| `/admin/source-hub` | authenticated admin | admin | Alias only | redirect → knowledge sources |
| `/community` | authenticated all + social flag | personal | More Personal | flag-off/role E2E |
| `/huong-dan` | authenticated all | personal/support | More/support | support E2E |
| `/welcome` | authenticated utility | — | Onboarding utility, not nav | onboarding E2E |
| `/welcome/[step]` | authenticated utility | — | Onboarding step | onboarding E2E |
| `/onboarding` | authenticated utility | — | Onboarding utility, not nav | onboarding E2E |
| `/role-select` | authenticated utility/compatibility | — | Redirect utility, not nav | redirect E2E |
| `/account/consent` | authenticated all + compliance | personal/support | More/profile | account E2E |
| `/account/data` | authenticated all + compliance | personal/support | More/profile | account E2E |
| `/account/data/delete/[step]` | authenticated owner + explicit confirmation | personal/support | Focused destructive flow | account safety E2E |
| `/ask` | authenticated all roles | personal | Rebuild consumer ask | ask E2E |
| `/care` | authenticated owner/profile | personal | Rebuild consumer care | care E2E |
| `/care/check-symptoms` | authenticated all roles | personal | Rebuild symptom checker | symptom check E2E |
| `/care/prepare` | authenticated owner/profile | personal | Rebuild consumer visit prep | visit prep E2E |
| `/care/visits` | authenticated owner/profile | personal | Rebuild consumer visits | visit E2E |
| `/health` | authenticated permitted profile | personal | Rebuild consumer health | health E2E |
| `/health/documents` | authenticated permitted profile | personal | Rebuild consumer health documents | documents E2E |
| `/health/measurements` | authenticated permitted profile | personal | Rebuild consumer health measurements | measurements E2E |
| `/health/medications` | authenticated owner/profile | personal | Rebuild consumer medications | medications E2E |
| `/health/results` | authenticated permitted profile | personal | Rebuild consumer health results | results E2E |
| `/health/timeline` | authenticated permitted profile | personal | Rebuild consumer health timeline | timeline E2E |
| `/home` | authenticated all roles | personal | Rebuild consumer home | home E2E |
| `/you` | authenticated owner/profile | personal | Rebuild consumer you | you E2E |
| `/you/integrations` | authenticated owner/profile | personal | Rebuild consumer integrations | integrations E2E |
| `/you/notifications` | authenticated owner/profile | personal | Rebuild consumer notifications | notifications E2E |
| `/you/privacy` | authenticated owner/profile | personal | Rebuild consumer privacy | privacy E2E |
| `/you/profile` | authenticated owner/profile | personal | Rebuild consumer profile | profile E2E |
| `/you/sharing` | authenticated owner/profile | personal | Rebuild consumer sharing | sharing E2E |

## Gate rules

1. A generator/test compares this manifest to the page-route scan; missing or duplicate classification fails.
2. Every non-alias route has one access policy and canonical workspace.
3. An alias has one canonical target and a redirect test.
4. A More/context route is no more than two interactions from its workspace.
5. Forbidden direct links produce an explicit unauthorized state; they do not fall back to a different user’s data.
6. Public share routes mount no authenticated shell or analytics.

