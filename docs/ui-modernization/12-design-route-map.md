# Design-to-route map

This map is the implementation inventory for the supplied `design/` directory.
It distinguishes a visual reference from a route contract: visuals may change
presentation only; authorization, consent, provenance and safety boundaries
remain defined by the application and API.

| Design families in `design/` | Web route(s) | Delivery state |
|---|---|---|
| `the_clara_care_*`, `clara_precision_dark` | `/`, `/huong-dan`, public auth surfaces | shared dark tokens and landing shell; page-specific audit remains in UI-19 |
| `clara_care_h_m_nay_*` | `/today`, `/today/tasks/[id]` | real-data active, completed, caught-up and first-time states implemented |
| `h_i_clara_*` | `/chat`, `/chat/shares`, `/research` redirect | Chat V2 and legacy rollback retained; research is a Chat mode |
| `h_nh_tr_nh_s_c_kh_e_*` | `/lifemap`, `/lifemap/*` | existing data workflow retained; creation/detail visual migration is UI-09 |
| `clara_care_thu_c_*`, `clara_care_ki_m_tra_t_ng_t_c_*` | `/medicines`, `/medicines/cabinet/*` | list, cabinet and CareGuard interaction states are route-backed |
| `h_s_s_c_kh_e_*`, `stitch_clara_care_personal_health_companion` | `/phr`, `/phr/*` | record-derived overview, section states and BMI trend implemented |
| `ng_i_th_n_h_tr_*` | `/family`, `/family/invitations/[id]` | tabbed grants/log and review route implemented |
| `chu_n_b_bu_i_kh_m_*`, `t_o_bu_i_kh_m_m_i_review_step` | `/visits`, `/visits/new` | focused visit preparation stages implemented |
| `tham_kh_o_nhi_u_chuy_n_khoa_*` | `/council` | shared token/card hierarchy complete; case/result hierarchy remains UI-16 |
| `clara_scribe_*` | `/scribe` | canonical stages/consent wording implemented; final visual sweep is UI-17 |
| `living_evidence_*` | `/evidence`, `/research/source-hub` | shared shell/tokens complete; evidence/source steps remain UI-15 |
| `t_ng_quan_c_ng_vi_c_*`, `h_sinh_th_i_clara_*` | `/dashboard`, `/dashboard/*`, `/admin/*` | role-aware dashboard implemented; admin visual sweep is UI-19 |

## Shared reference rules

- Canonical palette, spacing and typography are `design/clara_health_system/DESIGN.md`.
- Desktop app navigation is 256px; desktop content is 1120px maximum with a
  48px outer gutter; mobile uses a 16px gutter.
- Cards use tonal elevation (`#1d2025` / `#272a30`) plus a low-contrast
  `#414751` outline, with no decorative drop shadow or gradient.
- The personal shell has no workspace picker. Clinical, research and admin
  workspaces retain it only as an access-preserving presentation control.
