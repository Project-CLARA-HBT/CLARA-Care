# CLARA Care — Ruthless Remediation, Technical Design, Execution Plan, and A* Evidence Master Spec v6

> Tài liệu thực thi duy nhất cho vòng sửa sau audit commit mới nhất.

| Thuộc tính | Giá trị |
|---|---|
| Repository | Project-CLARA-HBT/CLARA-Care |
| Branch được audit | codex/commitloop-phase-a |
| Commit được audit | 5ffbe36244d8c2ebc9b5aa3e9d337e01c3df4e15 |
| Commit time | 2026-08-24T10:21:52+07:00 |
| Commit title | feat(ui): complete Spatial Editorial Health v5 across all 79 Web routes and Flutter Mobile surfaces |
| Parent | 270c16fee3d017bcdb3a99a4e27a0b2c549de190 |
| Ngày lập spec | 2026-08-24, Asia/Ho_Chi_Minh |
| Trạng thái GitHub tại thời điểm audit | Không có commit status; không có workflow run gắn với SHA |
| Quyết định release hiện tại | **BLOCK — DO NOT MERGE / DO NOT DEPLOY** |
| Đánh giá A* hiện tại | **Reject, xấp xỉ 4/10** |
| Mức độ tài liệu | Normative; các từ PHẢI, KHÔNG ĐƯỢC, CHỈ KHI là điều kiện bắt buộc |

---

# /goal

~~~text
/goal

Bạn là Principal Engineer, Clinical Safety Engineer, Security Incident Lead,
Research Lead và Release Captain của CLARA-Care.

MISSION
Biến repository Project-CLARA-HBT/CLARA-Care tại nhánh
codex/commitloop-phase-a, bắt đầu từ SHA
5ffbe36244d8c2ebc9b5aa3e9d337e01c3df4e15, thành một hệ thống:

1. không bịa dữ liệu lâm sàng, quản trị, vận hành hoặc bằng chứng;
2. không chứa credential trong source, test, image, compose hay lịch sử Git;
3. fail-closed tại mọi ranh giới an toàn và mọi mutation;
4. có backend authoritative cho mọi UI production;
5. có route, capability và layout coverage tính từ filesystem thực;
6. có test/CI/release evidence tái lập, gắn đúng SHA;
7. có GLHS formalism, implementation và evaluation đủ nghiêm để nộp A*;
8. chỉ tuyên bố vượt baseline khi dữ liệu sealed, preregistered và thống kê cho phép.

NON-NEGOTIABLE BLOCKERS
- Xử lý incident credential trước mọi feature work: revoke, rotate, scrub history,
  secret injection, scanner và evidence.
- Xóa toàn bộ production fallback tạo hồ sơ, nhóm máu, dị ứng, QR cấp cứu,
  patient roster, visit, SOAP, ICD-10, medication, lab, chữ ký, analytics,
  admin user, experiment và feedback giả.
- Không được biến lỗi network/API thành success cục bộ.
- Không được hiển thị Safe, Verified, Synced, Operational hoặc zero-PII nếu
  không có authoritative evidence mới, còn hạn và có provenance.
- Không được dùng fixture production để demo. Demo chỉ tồn tại trong build/tenant
  tách biệt, có watermark và không thể import từ production bundle.
- Thay checker 79/79 vòng tròn bằng inventory sinh từ toàn bộ page.tsx thực tế.
- Sửa test đang bảo vệ hành vi giả. Test phải chứng minh fail-closed.
- Pin Node 20.x đúng engines; không hợp thức hóa kết quả bằng runtime ngoài spec.
- Full Vitest phải exit 0 và không có unhandled error, act warning bị phân loại,
  timer leak hoặc false-positive teardown.

SCIENTIFIC INTEGRITY
- Không được sửa cohort, gold, prompt, endpoint hoặc SAP sau khi unblind.
- Không retry vô hạn. Mọi missing/malformed/timeout/wrong-model phải giữ trong
  denominator theo protocol.
- Không gọi synthetic là clinical validation.
- Không gọi bounded model checking là universal proof.
- Không gọi 79/79, 100%, verified, claim-eligible hoặc SOTA nếu denominator,
  artifact và receipt không chứng minh chính xác câu đó.
- Không tuyên bố “superior to all papers”. Chỉ được tuyên bố trên comparator,
  task, metric, model, dataset và confidence interval đã chạy trực tiếp.
- Bảo toàn mọi kết quả âm, mismatch, NOT_RUN và run bị mất.

WORKING METHOD
1. Đọc toàn bộ Master Spec v6 này.
2. Xác nhận HEAD, clean tree, toolchain và evidence baseline.
3. Thực hiện theo Phase và task dependency; không nhảy qua Gate 0.
4. Mỗi task phải tạo code + test + evidence receipt + doc update.
5. Mỗi PR chỉ đóng task khi acceptance criteria được máy kiểm chứng.
6. Không sửa test để che lỗi; thay hành vi nguy hiểm và thêm negative tests.
7. Nếu thiếu quyền, secret, dataset, human review hoặc external comparator,
   đánh dấu BLOCKED/NOT_RUN; không tự tạo bằng chứng thay thế.
8. Sau mỗi wave chạy focused tests, sau mỗi phase chạy full gate.
9. Không merge khi còn P0/P1, flaky test, unhandled error hoặc evidence gap.

REQUIRED OUTPUTS
- Incident report và secret-rotation receipts không lộ giá trị secret.
- Authoritative API endpoints, migrations, RBAC, CSRF, audit và contracts.
- Web/Mobile production clients không chứa clinical/admin seed fallback.
- Generated route registry phủ 100% filesystem route.
- Canonical design-token build không có override ngoài ý muốn.
- Unit, property, contract, integration, PostgreSQL, E2E, a11y, security,
  chaos, race, load và mobile widget tests.
- CI evidence manifest gắn commit SHA, run URL/ID, artifact SHA-256 và exit code.
- GLHS proof-obligation ledger, TLA+/model-check receipt và real PostgreSQL traces.
- Frozen confirmatory protocol/SAP/cohort/oracle/comparator implementations.
- Reproducibility package và claim ledger đồng bộ với manuscript.

DEFINITION OF DONE
Chỉ kết thúc khi toàn bộ tiêu chí tại mục “Definition of Done và 10/10 rubric”
đều PASS bằng evidence gắn cùng release SHA. Nếu một tiêu chí chưa có evidence,
kết luận phải là NOT DONE. Mục tiêu 10/10 là một gate có thể bác bỏ, không phải
một câu tự đánh giá.
~~~

---

# 0. Cách dùng và thứ tự ưu tiên

## 0.1 Tính chuẩn tắc

Tài liệu này kết hợp năm lớp công việc:

1. audit commit mới nhất;
2. product/system requirements;
3. technical design;
4. execution plan và work breakdown;
5. research/evaluation program để đạt ngưỡng A*.

Khi có xung đột, thứ tự ưu tiên là:

1. an toàn người dùng và nghĩa vụ pháp lý;
2. security incident containment;
3. data truth và auditability;
4. scientific integrity;
5. correctness và availability;
6. usability;
7. performance;
8. thẩm mỹ.

Không có yêu cầu UI nào được phép làm yếu RBAC, consent, FIDES, CSRF, emergency
fast-path, legal hard-guard hoặc no-PII telemetry.

## 0.2 Trạng thái requirement

| Trạng thái | Ý nghĩa |
|---|---|
| TODO | Chưa bắt đầu |
| IN_PROGRESS | Đang triển khai, chưa đủ acceptance evidence |
| BLOCKED | Thiếu authority, dependency, dataset, human review hoặc environment |
| IMPLEMENTED | Code đã có nhưng gate chưa hoàn tất |
| VERIFIED | Có test/evidence đúng SHA |
| REJECTED | Giải pháp không đáp ứng invariant |

Chỉ trạng thái VERIFIED mới được tính hoàn thành.

## 0.3 Chuẩn bằng chứng

Mọi receipt tối thiểu phải có:

- repository và branch;
- exact 40-character commit SHA;
- dirty-tree state;
- UTC start/end;
- toolchain/container digest;
- command nguyên văn;
- exit code;
- stdout/stderr artifact;
- test count và skipped/xfailed count;
- artifact SHA-256;
- CI run ID/URL nếu chạy CI;
- người hoặc automation thực thi;
- lý do cho mọi NOT_RUN.

Ảnh chụp màn hình, log cắt đoạn, câu “tests passed”, commit message và checklist
tự tick không phải bằng chứng release độc lập.

---

# 1. Ruthless review commit mới nhất

## 1.1 Tóm tắt hai câu

Commit 5ffbe362 thực hiện một đợt tái cấu trúc UI rất rộng cho Web và Flutter,
thêm Spatial Editorial primitives, nhiều route/page mới, admin/clinical surfaces
và một registry layout 79 mục. Tuy nhiên, commit đồng thời đưa dữ liệu giả và
false-success vào production paths, giữ credential trong repository, dùng một
denominator route vòng tròn và không tạo bất kỳ CI receipt nào; vì vậy độ rộng
giao diện không chuyển thành độ mới khoa học, độ đúng kỹ thuật hay release safety.

## 1.2 Fit score

**Tentative score: Reject, khoảng 4/10.**

Blunt justification:

- Đây chủ yếu là product/UI expansion, không phải đóng góp khoa học mới.
- P0 data fabrication trong hệ thống y tế đủ để chặn merge dù mọi UI test pass.
- Secret exposure đủ để mở security incident.
- Backend contracts cho nhiều admin feature không tồn tại, nhưng UI báo success.
- Claim 79/79 dùng denominator 79 do spec tự đặt, trong khi source có 114 route.
- Claim 100% test pass mâu thuẫn với full-suite exit 1 do unhandled teardown error.
- Không có status check hay workflow run gắn SHA trên GitHub.
- GLHS kernel, proof, comparator và confirmatory evidence không được cải thiện
  bởi commit này.

## 1.3 Những điểm tích cực, nhưng không đủ cứu bài

| Điểm tích cực | Giá trị thực | Vì sao chưa đủ |
|---|---|---|
| UI primitives có cấu trúc | Có thể giảm layout duplication | Không sửa data authority hoặc safety |
| Web và Mobile được mở rộng | Tăng surface coverage | Surface giả làm tăng clinical risk |
| Có nhiều unit/widget tests | Tăng khả năng regression lock | Một số test khóa chính hành vi nguy hiểm |
| Có route layout contract | Hướng đúng về governance | Checker không enumerate filesystem |
| Role-adaptive concepts | Có giá trị UX | RBAC/data source vẫn phải authoritative |
| Dense admin workbench | Tăng khả năng thao tác | Backend endpoint thiếu; mutation false-success |

## 1.4 Evidence snapshot tái xác minh

| Check | Kết quả | Nhận định |
|---|---|---|
| GitHub branch head | 5ffbe36244d8c2ebc9b5aa3e9d337e01c3df4e15 | SHA mới nhất tại thời điểm audit |
| Local HEAD vs origin | Trùng | Không có commit mới hơn |
| Working tree | Clean | Audit không bị nhiễu bởi local edits |
| GitHub commit statuses | 0 | Không có CI status evidence |
| GitHub workflow runs | 0 | Không có Actions receipt gắn SHA |
| page.tsx từ filesystem | 114 | Denominator thật hiện tại |
| route capability checker | 114/114 PASS | Checker này dùng filesystem |
| route layout checker | 79/79 PASS | Pass vòng tròn giữa spec 79 và registry 79 |
| registry size | 79 | Thiếu 35 page route |
| TypeScript same-SHA audit | PASS | Không chứng minh runtime/data truth |
| Next production build same-SHA audit | PASS | Buildability không đồng nghĩa safety |
| Full Vitest same-SHA audit | 192 files, 1447 assertions reported pass; process exit 1 | Unhandled document-is-not-defined teardown error; claim 100% false |
| Flutter | NOT_RUN | Flutter SDK không có trong audit environment |
| Python full suite | NOT_RUN | pytest/toolchain không có trong audit environment |
| Node runtime audit | 24.19.0 | Không khớp engines yêu cầu >=20 <21 |

## 1.5 P0/P1 finding register

### F-SEC-001 — Credential-shaped SMTP secret trong repository

**Severity:** P0 / incident.

Observed paths:

- services/api/src/clara_api/core/config.py;
- deploy/docker/docker-compose.app.yml;
- deploy/docker/docker-compose.deploy.yml;
- services/api/tests/test_auth_email_delivery.py.

Giá trị không được lặp lại trong tài liệu này; luôn biểu diễn là
**[REDACTED]**.

Tác động:

- credential có thể đã bị harvest từ Git history;
- xóa ở HEAD không đủ;
- test đang biến secret cụ thể thành contract;
- compose có thể phân phối secret sang môi trường ngoài dự kiến.

Release gate:

- revoke/rotate xong;
- xác minh credential cũ không còn dùng được;
- scrub toàn bộ reachable history theo scope đã phê duyệt;
- scanner ở working tree, history, image và artifact đều sạch;
- compose fail-fast nếu secret injection thiếu;
- incident timeline và owner sign-off được lưu.

### F-CLN-001 — Hồ sơ cá nhân và Emergency QR giả

**Severity:** P0 / clinical data integrity.

Observed behavior tại apps/web/app/(consumer)/you/page.tsx:

- catch API error rồi trả profile/blood type/allergies/emergency contact/consent/
  integration giả;
- query được resolve nên error UI không thể đạt;
- QR cấp cứu sử dụng dữ liệu default/fabricated.

Tác động:

- người dùng hoặc nhân viên y tế có thể hành động trên dữ liệu không thuộc bệnh nhân;
- UI không phân biệt unavailable với known-empty;
- provenance và freshness bị giả mạo.

Required correction:

- không có fallback object trong production module;
- fetch failure phải tạo AuthorityState=unavailable;
- QR chỉ sinh khi tất cả trường bắt buộc là authoritative, consent hợp lệ và
  provenance/freshness pass;
- known-empty hiển thị “chưa có dữ liệu”, không tự gán nhóm máu hoặc allergy.

### F-CLN-002 — Visit record, SOAP, ICD-10, medication, lab và signature giả

**Severity:** P0.

Observed behavior tại apps/web/app/visits/[visitId]/page.tsx:

- FALLBACK_VISIT_DETAILS chứa clinical record hoàn chỉnh;
- fallback được merge vào response thật hoặc partial;
- consent scribe toggle cục bộ khi API lỗi;
- create document thêm record local với status verified khi API lỗi;
- delete cục bộ khi API lỗi.

Observed test problem:

- apps/web/app/visits/visits-page.test.tsx để getVisit không mock;
- network failure kích hoạt fake record;
- test xác nhận doctor/SOAP/medication/lab giả.

Required correction:

- xóa fallback khỏi production;
- response partial không được lấp bằng fake;
- verified chỉ từ server-signed status;
- mutation UI chỉ commit sau authoritative 2xx/ETag receipt;
- negative tests chứng minh network error không thay đổi state.

### F-CLN-003 — Patient roster giả trên Web và Mobile

**Severity:** P0.

Observed behavior:

- apps/web/components/clinical/patient-roster.tsx khởi tạo bằng
  INITIAL_PATIENT_QUEUE có tên, MRN, vital, diagnosis, DDI giả và không fetch API;
- action route fake patient sang Council/Scribe và /clinical/intake không tồn tại;
- apps/mobile/lib/experience/unified/clinical_overview_surface.dart điền static
  patient queue sau khi fetch Council/Scribe.

Required correction:

- roster lấy từ clinical workbench API có RBAC doctor/admin;
- ID là opaque server ID; không dùng fake MRN trong production bundle;
- unavailable/empty/loading phân biệt;
- route target phải tồn tại và có capability contract;
- mobile/web dùng cùng OpenAPI schema và provenance fields.

### F-ADM-001 — Admin users false-success

**Severity:** P0 / access-control operations.

Observed behavior tại apps/web/lib/admin-users.ts:

- seed users trong memory;
- role/lock/unlock/revoke mutate memory trước;
- catch API error rồi vẫn trả success=true;
- backend không có /admin/users routes tương ứng.

Tác động:

- admin tin rằng role hoặc session đã thay đổi trong khi backend không đổi;
- thao tác bảo mật quan trọng trở thành theater;
- audit log không thể chứng minh transaction.

Required correction:

- xây backend authoritative endpoint trước;
- sử dụng optimistic concurrency;
- server thực thi RBAC/CSRF/audit;
- UI không mutate committed cache trước 2xx;
- error trả state cũ và correlation ID.

### F-ADM-002 — Experiments và feedback false-success

**Severity:** P0.

Observed behavior:

- apps/web/lib/experiments.ts dùng in-memory experiments;
- rollout/kill-switch catch API error rồi trả object đã cập nhật;
- apps/web/lib/clinical-feedback.ts trả seed data và fake update;
- backend không có /admin/experiments và /admin/feedback tương ứng;
- tests hiện bảo vệ offline mutation.

Required correction:

- authoritative DB tables/endpoints hoặc loại UI khỏi production;
- kill-switch bắt buộc server commit, audit ID và read-after-write;
- feedback mutation idempotent, role-gated, versioned;
- offline demo chỉ trong demo tenant/bundle.

### F-ANA-001 — Analytics và privacy verification giả

**Severity:** P0.

Observed behavior tại apps/web/lib/platform-analytics.ts:

- sinh query volume 42,850 khi DB empty;
- sinh daily trends, safety count, verdict/DDI distribution, latency, funnel,
  retention và role distribution;
- trả has_data=true;
- trả zero_pii_verified=true;
- trả last_audit_status=PASSED_STRICT_NO_PII_INVARIANT.

Required correction:

- DB empty phải trả has_data=false và metrics null/empty;
- zero-PII chỉ từ dedicated audit job receipt;
- mỗi metric có source, window, generated_at, freshness, sample size;
- synthetic analytics chỉ ở fixture module không thể vào production.

### F-ROUTE-001 — Route coverage denominator laundering

**Severity:** P1 / governance and claim integrity.

Filesystem có 114 page.tsx. Registry có 79. Checker layout:

1. parse đúng 79 hàng từ Section 5 của spec;
2. yêu cầu registry đúng 79;
3. so hai tập 79 với nhau;
4. không enumerate filesystem.

Ba mươi lăm route hiện không đăng ký:

1. /admin/audit
2. /admin/experiments
3. /admin/feedback
4. /admin/system
5. /admin/users
6. /ask
7. /auth/callback
8. /care
9. /care/check-symptoms
10. /care/prepare
11. /care/visits
12. /chat/[chatId]
13. /chat/share/[token]
14. /clinical
15. /clinical/overview
16. /clinical/patients
17. /health
18. /health/documents
19. /health/measurements
20. /health/medications
21. /health/results
22. /health/timeline
23. /home
24. /lifemap/timeline
25. /medicines/[id]
26. /medicines/cabinet
27. /onboarding
28. /visits/[visitId]
29. /you
30. /you/integrations
31. /you/notifications
32. /you/privacy
33. /you/profile
34. /you/settings
35. /you/sharing

Required correction:

- filesystem inventory là denominator;
- registry/spec là derived or validated against inventory;
- explicit exclusion chỉ cho framework artifacts không phải page route;
- fail nếu missing, extra, duplicate canonical, broken alias hoặc broken target;
- output report nêu numerator/denominator và danh sách exact.

### F-CLN-004 — Fail-open clinical status

**Severity:** P1, nâng lên P0 nếu dùng trong clinical workflow.

Observed behavior:

- clinical-overview-launchpad hardcode DrugBank v5.1.10 Verified;
- error có thể biến alert thành empty;
- panel dưới hiển thị Safe, fully operational, Synced;
- expiring null bị chuyển thành 0.

Required correction:

- safety state là tri-state hoặc richer authority state;
- unavailable không map sang safe;
- version/status lấy từ readiness API signed/authoritative;
- stale status hiển thị timestamp và chặn action phụ thuộc.

### F-TOK-001 — Design token không phải single source

**Severity:** P1.

Observed behavior:

- globals.css import generated tokens trước rồi legacy tokens;
- legacy import sau override 19 biến trùng;
- commit v5 không sửa pipeline này.

Required correction:

- một canonical token graph;
- generated CSS là import duy nhất cho semantic tokens;
- legacy mapping chỉ alias, không định nghĩa lại;
- CI so hash và fail trên duplicate declarations trái phép.

### F-QA-001 — Claim 100% test pass không đúng

**Severity:** P1.

Same-SHA full run:

- Vitest báo 192 files và 1447 assertions pass;
- process exit 1 vì unhandled ReferenceError: document is not defined;
- source liên quan apps/web/app/chat/_v2/ChatShell.tsx;
- isolated test có thể pass, cho thấy cross-test lifecycle/timer leak;
- có network, act và jsdom navigation warnings.

Required correction:

- clear mọi timeout/listener/subscription;
- không truy cập document sau environment teardown;
- full suite lặp ít nhất ba lần trên clean Node 20 container;
- unhandled error count phải bằng 0;
- warning allowlist phải explicit và có owner/expiry.

### F-RES-001 — Commit UI không nâng A* evidence

**Severity:** P1 cho mục tiêu publication.

Commit không sửa đáng kể:

- GLHS formal definition;
- proof obligations;
- concurrent PostgreSQL evidence;
- direct faithful competitor implementation;
- fresh confirmatory holdout;
- clinical adjudication;
- false-stale/scaling gates;
- manuscript/reproducibility package.

Kết luận: UI breadth không được tính là novelty, theorem, baseline hoặc experimental
evidence.

---

# 2. Outcome model và 10/10 không thể tự phong

## 2.1 North-star outcomes

| ID | Outcome | Cách đo | Gate |
|---|---|---|---|
| OUT-01 | Không fabricated production data | Static rule + fault-injection E2E | 0 violation |
| OUT-02 | Không false-success mutation | Contract tests + chaos proxy | 0 violation |
| OUT-03 | Không reachable secret | working tree/history/image/artifact scans | 0 verified secret |
| OUT-04 | Route truth | filesystem-derived inventory | 100% actual pages |
| OUT-05 | Clinical fail-closed | state-machine/property tests | 100% forbidden transitions blocked |
| OUT-06 | Admin authority | server receipts/read-after-write | 100% critical mutations authoritative |
| OUT-07 | Reproducible release | clean container replay | all mandatory gates exit 0 |
| OUT-08 | A* novelty | closest-work delta + formal construct | independent PC defensibility |
| OUT-09 | A* technical depth | theorem/proof/model-check/DB evidence | all proof obligations closed or scoped |
| OUT-10 | A* evaluation | preregistered, direct baselines, statistics | claim-specific pass |

## 2.2 Score semantics

| Score | Nghĩa |
|---:|---|
| 0–3 | Prototype/claim theater; severe gaps |
| 4 | Current state: substantial code, reject-level integrity/safety gaps |
| 5 | Major blockers removed, research still weak |
| 6 | Release candidate but paper incremental |
| 7 | Solid system paper, evaluation incomplete |
| 8 | Credible A* submission with remaining rebuttal risk |
| 9 | Strong accept territory, independent reproduction and direct baselines |
| 10 | Không có blocker theo rubric; vẫn không bảo đảm acceptance |

Không agent, tác giả hay CI job nào được ghi 10/10 dựa trên số test pass. Điểm 10
chỉ là shorthand khi toàn bộ rubric cuối tài liệu có evidence độc lập.

---

# 3. Phạm vi

## 3.1 In scope

- Web Next.js production routes và shared libraries.
- Flutter Mobile production surfaces.
- FastAPI API authoritative endpoints và PostgreSQL schema.
- ML gateway interactions ảnh hưởng clinical safety.
- Auth, RBAC, consent, CSRF, session invalidation, audit.
- Analytics provenance và no-PII verification.
- Route/capability/layout governance.
- Design tokens.
- CI, release evidence, observability, incident response.
- GLHS kernel, formalism, benchmarking và paper positioning.
- Research integrity, sealed artifacts và reproducibility.

## 3.2 Out of scope, trừ khi được phê duyệt riêng

- dùng dữ liệu bệnh nhân thật cho benchmark;
- crawling nguồn có điều khoản sử dụng chưa rõ;
- gửi paper hoặc liên hệ reviewer/venue;
- production deployment;
- đổi legal basis hoặc consent text mà không có legal review;
- mua provider credits hoặc chạy paid evaluation không có approval;
- tuyên bố clinical efficacy;
- history rewrite trên remote trước khi incident owner phê duyệt.

## 3.3 Không phải mục tiêu

- làm mọi màn hình nhiều hiệu ứng hơn;
- giữ demo đẹp bằng cách chèn seed;
- tối đa hóa số test bằng assertion yếu;
- tối đa hóa số paper;
- tối ưu benchmark sau khi nhìn final labels;
- đạt một con số accuracy bằng retry/cherry-pick.

---

# 4. Thuật ngữ chuẩn

| Thuật ngữ | Định nghĩa |
|---|---|
| Authoritative | Dữ liệu từ service được cấp quyền, có contract, provenance và freshness |
| Known-empty | Truy vấn thành công và nguồn xác nhận không có record |
| Unavailable | Không thể xác định do network/service/auth/dependency |
| Degraded | Có dữ liệu một phần nhưng không đủ cho một hoặc nhiều capability |
| Stale | Dữ liệu quá freshness budget |
| Verified | Trạng thái do verifier authoritative phát hành, còn hiệu lực |
| Fixture | Dữ liệu test tĩnh chỉ dùng trong test/demo isolation |
| False-success | UI/client báo thành công khi server không commit |
| Receipt | Bằng chứng machine-readable gắn transaction/run/SHA |
| THSS | Temporal Health State Snapshot theo định nghĩa GLHS của repo |
| GST | Governance State Transition/commit gate |
| GLHS | Cơ chế binding disclosure/inference context với commit-time state |
| Scientific N | Subject/schedule độc lập theo protocol, không phải retry |
| Claim-eligible | Đủ freeze, execution, seal, analysis và scope để support claim |
| A* | Chuẩn top-tier về novelty, depth, baselines, rigor; không phải nhãn tự cấp |

---

# 5. Invariants toàn hệ thống

## 5.1 Data-truth invariants

**INV-DATA-001:** Production code KHÔNG ĐƯỢC tạo giá trị clinical record để thay
thế lỗi fetch.

**INV-DATA-002:** known-empty, unavailable, unauthorized, degraded và stale phải
là các trạng thái khác nhau.

**INV-DATA-003:** Partial response không được merge với fixture/default có ý nghĩa
lâm sàng.

**INV-DATA-004:** verified/safe/synced/operational chỉ hiển thị khi receipt đáp ứng
issuer, subject, scope, issued_at, expires_at và signature/integrity.

**INV-DATA-005:** Không có patient name, MRN, diagnosis, vital, medication,
allergy, blood type, lab hoặc signature hardcode trong production client bundle.

**INV-DATA-006:** Analytics không có data phải trả has_data=false; không sinh
trend giả.

## 5.2 Mutation invariants

**INV-MUT-001:** Client không được cập nhật committed state trước server receipt
cho role, lock, session revoke, consent, clinical document verification,
experiment kill-switch hoặc delete.

**INV-MUT-002:** Mọi critical mutation có idempotency key.

**INV-MUT-003:** Mọi critical mutation dùng optimistic concurrency hoặc
transactional precondition.

**INV-MUT-004:** 4xx/5xx/timeout/network error giữ nguyên committed state.

**INV-MUT-005:** Success response chứa resource version và audit_event_id.

**INV-MUT-006:** Read-after-write hoặc event-driven reconciliation phải chứng minh
server state.

## 5.3 Security invariants

**INV-SEC-001:** Không credential literal trong source, test, docs, example,
compose, image layer, log hoặc artifact.

**INV-SEC-002:** Secret bắt buộc phải đến từ approved secret provider hoặc
runtime injection.

**INV-SEC-003:** Cookie-authenticated mutation phải qua CSRF.

**INV-SEC-004:** Server, không phải navigation/UI, thực thi RBAC.

**INV-SEC-005:** Session revoke có hiệu lực server-side và có bounded propagation.

**INV-SEC-006:** Audit event không chứa secret/PHI/free-text query.

## 5.4 Clinical safety invariants

**INV-CLN-001:** Emergency fast-path không bị trì hoãn bởi LLM diagnostic reasoning.

**INV-CLN-002:** Failed CRITICAL FIDES claim block response.

**INV-CLN-003:** Legal hard-guard chặn prescribing/diagnosis/personal dosage
intent theo vi/en.

**INV-CLN-004:** QR cấp cứu không sinh nếu subject binding, consent, required fields
hoặc freshness không pass.

**INV-CLN-005:** Unavailable medication knowledge base không hiển thị “Safe”.

**INV-CLN-006:** Clinical action luôn giữ subject context; cross-subject write bị chặn.

## 5.5 Research integrity invariants

**INV-RES-001:** Freeze trước provider call.

**INV-RES-002:** Missing/malformed/failed/wrong-model được giữ và tính đúng SAP.

**INV-RES-003:** Retry không tăng N.

**INV-RES-004:** Negative/null/mismatch/NOT_RUN không bị xóa hoặc đổi nhãn.

**INV-RES-005:** Direct superiority chỉ áp dụng comparator đã chạy cùng task/budget.

**INV-RES-006:** Synthetic evidence không được gọi là clinical validation.

---

# 6. Kiến trúc đích

## 6.1 Source-of-truth architecture

~~~mermaid
flowchart TD
    UI[Web hoặc Mobile] --> C[Typed client]
    C --> G[API Gateway]
    G --> A[Auth RBAC Consent CSRF]
    A --> S[Domain service]
    S --> DB[(PostgreSQL)]
    S --> E[Audit outbox]
    DB --> R[Authoritative envelope]
    R --> C
    C --> V[Truthful state renderer]
~~~

Fixture không nằm trong graph production. Demo sử dụng deployment/tenant khác,
không phải catch branch trong typed client.

## 6.2 Authority envelope

~~~typescript
export type AuthorityState =
  | "authoritative"
  | "known_empty"
  | "unavailable"
  | "degraded"
  | "stale";

export interface ProvenanceRef {
  sourceSystem: string;
  sourceRecordId?: string;
  observedAt?: string;
  generatedAt: string;
  policyVersion: string;
  consentVersion?: string;
  integrityDigest?: string;
}

export interface DataEnvelope<T> {
  state: AuthorityState;
  data: T | null;
  resourceVersion?: string;
  generatedAt: string;
  expiresAt?: string;
  provenance: ProvenanceRef[];
  missingCapabilities: string[];
  correlationId: string;
}
~~~

Rules:

- authoritative yêu cầu data khác null;
- known_empty yêu cầu data null hoặc collection rỗng và HTTP success;
- unavailable không được mang data giả;
- degraded phải nêu missingCapabilities;
- stale giữ data chỉ nếu UI cho phép read-only và gắn stale warning;
- clinical action capability tự quyết định trạng thái nào được phép.

## 6.3 Mutation flow

~~~mermaid
sequenceDiagram
    participant U as User
    participant W as Web Mobile
    participant A as API
    participant D as Database
    participant O as Audit Outbox
    U->>W: Confirm action
    W->>A: Mutation plus idempotency and version
    A->>A: Auth RBAC Consent CSRF
    A->>D: Transaction and precondition
    D-->>A: Committed version
    A->>O: Durable audit event in transaction
    A-->>W: 2xx receipt
    W->>A: Revalidate or read-after-write
    A-->>W: Authoritative envelope
    W-->>U: Success
~~~

Nếu bất kỳ bước server nào fail, UI hiển thị error và giữ state trước mutation.

## 6.4 Domain boundaries

| Boundary | Owner | Authoritative data |
|---|---|---|
| Identity/session | API auth/session service | User, role, session state |
| Consent | API consent ledger | Active version, scope, revocation |
| PHR | API PHR service | Clinical/personal record + provenance |
| Visits | API visit service | Visit, document, verification state |
| Clinical roster | API clinical workbench | Assigned patients/cases |
| Admin users | API admin identity | Role/lock/session operations |
| Experiments | API experiment control | Allocation/rollout/kill status |
| Feedback | API clinical feedback | Feedback lifecycle |
| Analytics | Analytics aggregation service | Metric windows and provenance |
| Safety readiness | API/ML readiness aggregator | KB/verifier status |
| GLHS | API GLHS kernel | bindings, proposals, transitions, audit |

---

# 7. Cross-cutting requirements

## 7.1 Requirement record format

Mỗi implementation issue phải chứa:

- Requirement ID;
- priority;
- threat/failure scenario;
- preconditions;
- normative behavior;
- negative behavior;
- acceptance test;
- evidence artifact;
- owner;
- dependencies;
- rollout/rollback notes.

## 7.2 General requirements

### GEN-001 — Exact baseline

Hệ thống PHẢI ghi exact HEAD SHA và dirty state trước build/test/eval.

Acceptance:

- receipt có 40-char SHA;
- dirty tree làm release gate fail, trừ generated evidence được allowlist;
- compare base/head được lưu.

### GEN-002 — Deterministic clocks

Business logic PHẢI dùng injectable UTC clock.

Acceptance:

- không test phụ thuộc wall clock;
- timezone-aware datetime xuyên API/DB;
- naive datetime rejected.

### GEN-003 — Correlation

Mọi request PHẢI có correlation ID xuyên Web/Mobile/API/ML/audit.

Acceptance:

- ID không chứa PII;
- error UI hiển thị copyable support ID;
- log join được nhưng không lộ payload clinical.

### GEN-004 — Schema compatibility

OpenAPI là contract authoritative cho clients.

Acceptance:

- generated clients hoặc contract tests;
- breaking change yêu cầu version/migration;
- unknown enum xử lý fail-safe.

### GEN-005 — No hidden fallback

Production client PHẢI fail build nếu import fixture/seed/demo module.

Acceptance:

- ESLint/custom dependency rule;
- bundle scan;
- adversarial renamed-import test.

### GEN-006 — Localization parity

Mọi safety/error/unknown state có vi/en parity.

Acceptance:

- i18n checker;
- không internal telemetry/raw upstream error ở End_User UI;
- clinical terms qua terminology contract.

### GEN-007 — Accessibility

WCAG 2.2 AA cho mandatory flows.

Acceptance:

- automated axe;
- keyboard only;
- screen reader labels;
- focus restore;
- reduced motion;
- color-independent status.

### GEN-008 — Observability truth

Health/readiness endpoint không được chuyển dependency unknown thành healthy.

Acceptance:

- per-dependency status;
- timestamp/freshness;
- partial/degraded aggregate;
- chaos tests.

### GEN-009 — No silent catch

Catch production error phải:

1. map typed error;
2. emit privacy-safe telemetry;
3. preserve authoritative state;
4. expose appropriate UI recovery.

Empty catch hoặc catch-return-seed bị cấm.

### GEN-010 — Claims as code

Mọi claim định lượng trong docs/release/manuscript PHẢI có claim ledger entry
trỏ đến artifact và analysis.

---

# 8. Security incident và secret-management design

## 8.1 Incident phases

### SEC-IR-001 — Containment

- xác định secret owner/provider/scope;
- revoke credential hiện tại;
- tạo credential mới qua approved secret manager;
- dừng deployment dùng credential cũ;
- kiểm tra audit logs cho use bất thường;
- không post giá trị vào issue/PR/chat/log.

Acceptance:

- provider receipt hoặc operator attestation;
- credential cũ fail authentication;
- owner/time/impact window được ghi.

### SEC-IR-002 — Eradication

- thay literal bằng required environment reference;
- loại exact-value assertions khỏi tests;
- scrub Git history theo approved plan;
- force-update remote chỉ sau coordination;
- scan fork/tag/release artifact/container.

Acceptance:

- gitleaks/trufflehog-equivalent scan clean trên all refs trong scope;
- image history scan clean;
- no matching digest trong reachable artifacts;
- collaborators nhận migration instructions.

### SEC-IR-003 — Recovery

- deploy bằng rotated secret;
- smoke test email qua nonproduction recipient;
- monitor auth failure/abuse;
- close incident với retrospective.

## 8.2 Configuration contract

### SEC-CFG-001

Production startup PHẢI fail nếu required SMTP secret không được inject.

~~~python
class Settings(BaseSettings):
    smtp_password: SecretStr

    @model_validator(mode="after")
    def reject_placeholder_or_literal_default(self):
        # no default; reject blank, known placeholder, or test-only marker
        return self
~~~

### SEC-CFG-002

Compose PHẢI dùng required variable syntax hoặc secrets mount, không default.

### SEC-CFG-003

Tests PHẢI sinh ephemeral fake credential trong fixture, không assert shared value.

### SEC-CFG-004

Logging PHẢI redact SecretStr và authorization headers.

### SEC-CFG-005

CI PHẢI chạy secret scan trên:

- diff;
- working tree;
- reachable Git history;
- built Docker layers;
- uploaded artifacts.

## 8.3 Threat model

| Threat | Control | Test |
|---|---|---|
| Secret committed | pre-commit + CI history scan | planted canary fixture must be detected |
| Secret in test snapshot | snapshot scanner | failing negative fixture |
| Secret in Docker layer | image scan | build with canary then expect block |
| Secret in exception | structured redaction | property test |
| Old secret still valid | provider revoke | explicit auth failure receipt |
| History rewrite breaks clones | coordinated migration | dry-run and recovery tag |

---

# 9. Production/demo/test data isolation

## 9.1 Build modes

| Mode | Production data path | Fixture allowed | Watermark | Network |
|---|---|---|---|---|
| production | Authoritative only | No | No | approved endpoints |
| staging | Authoritative staging tenant | No production fixture | Environment badge | staging only |
| demo | Dedicated demo tenant | Yes, server-seeded | Persistent DEMO watermark | demo endpoints |
| test | In-process fixture/mocks | Yes | N/A | blocked unless explicit |

## 9.2 DEMO requirements

### DEMO-001

Demo records PHẢI nằm trong dedicated tenant/database namespace.

### DEMO-002

Production bundle PHẢI không chứa demo patient names/MRN/clinical narratives.

### DEMO-003

Demo UI PHẢI có watermark không thể tắt bằng client preference.

### DEMO-004

Demo account không được gọi production clinical endpoints.

### DEMO-005

Export/share/emergency QR bị disable hoặc tạo artifact có DEMO marker.

## 9.3 Static enforcement

Forbidden production import patterns:

- test/fakes;
- fixtures;
- seed-data;
- demo-data;
- mock-service;
- FALLBACK_VISIT_DETAILS;
- INITIAL_PATIENT_QUEUE.

Checker phải parse dependency graph, không chỉ grep tên file.

---

# 10. Authoritative API design

## 10.1 Common response conventions

### API-COM-001

Read response:

~~~json
{
  "state": "authoritative",
  "data": {},
  "resource_version": "opaque-version",
  "generated_at": "2026-08-24T03:00:00Z",
  "expires_at": "2026-08-24T03:05:00Z",
  "provenance": [],
  "missing_capabilities": [],
  "correlation_id": "opaque"
}
~~~

### API-COM-002

Mutation receipt:

~~~json
{
  "status": "committed",
  "resource_id": "opaque",
  "resource_version": "new-opaque-version",
  "audit_event_id": "opaque",
  "idempotency_key": "client-generated-uuid",
  "committed_at": "2026-08-24T03:00:00Z",
  "correlation_id": "opaque"
}
~~~

### API-COM-003

Error:

~~~json
{
  "error": {
    "code": "VERSION_CONFLICT",
    "safe_message_key": "errors.versionConflict",
    "retryable": false,
    "correlation_id": "opaque",
    "details": {
      "current_resource_version": "opaque"
    }
  }
}
~~~

Không trả raw traceback, SQL, upstream secret hoặc PHI trong error.

## 10.2 Admin users

### Endpoint set

| Method | Path | Purpose | Role |
|---|---|---|---|
| GET | /api/v1/admin/users | Search/page users | admin |
| GET | /api/v1/admin/users/{user_id} | Detail | admin |
| PATCH | /api/v1/admin/users/{user_id}/role | Change role | admin |
| POST | /api/v1/admin/users/{user_id}/lock | Lock account | admin |
| POST | /api/v1/admin/users/{user_id}/unlock | Unlock account | admin |
| POST | /api/v1/admin/users/{user_id}/sessions/revoke | Revoke sessions | admin |

### ADM-API-001 — Search

Query supports cursor, limit, status, role, normalized search. Response excludes
unneeded PII. Limit max 100.

### ADM-API-002 — Role mutation

Request:

~~~json
{
  "target_role": "doctor",
  "expected_resource_version": "opaque",
  "reason_code": "approved-role-change"
}
~~~

Server requirements:

- require_roles(admin);
- CSRF for cookie auth;
- prohibit self-demotion if it removes last admin;
- prohibit last-active-admin lock;
- validate role-transition policy;
- transactionally update role and invalidate affected sessions;
- emit audit event;
- return receipt.

### ADM-API-003 — Lock/unlock

Lock must invalidate or constrain sessions according to policy. Unlock does not
silently restore revoked sessions.

### ADM-API-004 — Session revoke

Receipt includes revoked count computed server-side. Client-provided count ignored.

## 10.3 Experiments

### Schema

~~~typescript
interface Experiment {
  id: string;
  key: string;
  status: "draft" | "running" | "paused" | "killed" | "completed";
  rolloutBasisPoints: number;
  targetRules: TargetRule[];
  safetyOwner: string;
  resourceVersion: string;
  createdAt: string;
  updatedAt: string;
}
~~~

### Endpoints

| Method | Path | Semantics |
|---|---|---|
| GET | /api/v1/admin/experiments | authoritative list |
| POST | /api/v1/admin/experiments | create draft |
| PATCH | /api/v1/admin/experiments/{id}/rollout | OCC update |
| POST | /api/v1/admin/experiments/{id}/kill | fail-closed kill |
| GET | /api/v1/admin/experiments/{id}/audit | immutable history |

### EXP-API-001

Kill-switch is server-authoritative, idempotent and monotonic unless explicit
two-person reactivation policy passes.

### EXP-API-002

Medical safety guardrails không được experiment-disable.

### EXP-API-003

Rollout không vượt policy cap cho clinical features.

## 10.4 Clinical feedback

Endpoints:

- GET /api/v1/admin/feedback;
- GET /api/v1/admin/feedback/{id};
- PATCH /api/v1/admin/feedback/{id}/status;
- POST /api/v1/admin/feedback/{id}/assign;
- POST /api/v1/admin/feedback/{id}/resolution.

Requirements:

- separate free text from analytics telemetry;
- field-level access and redaction;
- immutable status history;
- idempotent resolution;
- no seed fallback;
- pagination and retention policy.

## 10.5 Clinical patient roster

### Endpoint

GET /api/v1/clinical/workbench/patients

Filter:

- assigned_to_me;
- urgency;
- status;
- cursor;
- limit;
- updated_since.

Response item:

~~~json
{
  "patient_id": "opaque",
  "display_label": "policy-controlled",
  "assignment": {
    "team_id": "opaque",
    "relationship": "treating_clinician"
  },
  "attention": {
    "level": "unknown",
    "reasons": []
  },
  "capabilities": [
    "open_record"
  ],
  "resource_version": "opaque",
  "generated_at": "2026-08-24T03:00:00Z",
  "provenance": []
}
~~~

Rules:

- server checks assignment/role/scope;
- no bulk clinical detail beyond minimum necessary;
- unknown attention never displayed green;
- route actions derive from capabilities;
- audit patient-record access.

## 10.6 Visit detail

### Endpoint set

| Method | Path | Purpose |
|---|---|---|
| GET | /api/v1/visits/{visit_id} | authoritative visit |
| POST | /api/v1/visits/{visit_id}/documents | create document |
| DELETE | /api/v1/visits/{visit_id}/documents/{document_id} | delete |
| PATCH | /api/v1/visits/{visit_id}/scribe-consent | update consent |
| POST | /api/v1/visits/{visit_id}/verify | authorized verification |

### VIS-API-001

GET không lấp field thiếu. Mỗi document có source, author, status, signature
metadata, created_at và resource_version.

### VIS-API-002

Client không gửi status=verified khi create. Server gán draft/pending; verify là
endpoint riêng có policy.

### VIS-API-003

Delete dùng If-Match hoặc expected version, audit event và tombstone policy.

### VIS-API-004

Scribe consent update có consent version, actor, scope, timestamp và revocation
semantics.

## 10.7 Personal “You” và Emergency Card

Endpoint:

- GET /api/v2/you;
- GET /api/v1/phr/emergency-card/eligibility;
- POST /api/v1/phr/emergency-card;
- POST /api/v1/phr/emergency-card/revoke.

Eligibility:

~~~json
{
  "eligible": false,
  "reasons": [
    "MISSING_BLOOD_TYPE_AUTHORITY"
  ],
  "required_fields": [],
  "consent_version": "opaque",
  "subject_binding": "opaque",
  "generated_at": "2026-08-24T03:00:00Z",
  "expires_at": "2026-08-24T03:05:00Z"
}
~~~

QR payload must be:

- short-lived or revocable;
- scope-minimized;
- signed;
- bound to subject and consent;
- auditable;
- never generated from UI defaults.

## 10.8 Platform analytics

Endpoint:

GET /api/v1/admin/analytics/platform?window=...

Metric:

~~~typescript
interface MetricPoint {
  metricId: string;
  value: number | null;
  unit: string;
  numerator?: number;
  denominator?: number;
  sampleSize: number;
  windowStart: string;
  windowEnd: string;
  generatedAt: string;
  source: string;
  freshnessState: "fresh" | "stale" | "unavailable";
}
~~~

Privacy audit status must come from a separate signed job receipt:

~~~typescript
interface PrivacyAuditReceipt {
  auditId: string;
  scannerVersion: string;
  scopeDigest: string;
  result: "pass" | "fail" | "incomplete";
  findingCount: number;
  executedAt: string;
  artifactDigest: string;
}
~~~

No receipt means incomplete, never pass.

---

# 11. Web technical design

## 11.1 Query state pattern

Every production query uses an explicit adapter:

~~~typescript
type ViewState<T> =
  | { kind: "loading" }
  | { kind: "ready"; data: T; provenance: ProvenanceRef[] }
  | { kind: "empty" }
  | { kind: "degraded"; data: T | null; missing: string[] }
  | { kind: "stale"; data: T; generatedAt: string }
  | { kind: "unavailable"; correlationId: string }
  | { kind: "forbidden" };
~~~

No default object is allowed in toViewState.

## 11.2 Mutation controller

~~~typescript
interface MutationSnapshot<T> {
  committed: T;
  pending: boolean;
  error?: SafeClientError;
}

async function authoritativeMutation<T>(
  request: MutationRequest,
  current: T
): Promise<MutationSnapshot<T>> {
  // keep current committed state while pending
  // require a valid server receipt
  // revalidate/read after write
  // return current unchanged on any error
}
~~~

Critical mutations do not use optimistic visual success. A temporary “request
being processed” indicator is allowed, but role/status/data remains old until receipt.

## 11.3 Error taxonomy

| Code | UI state | Retry |
|---|---|---|
| NETWORK_UNAVAILABLE | unavailable | user retry |
| UNAUTHORIZED | auth recovery | after re-auth |
| FORBIDDEN | forbidden | no blind retry |
| VERSION_CONFLICT | conflict dialog | reload/compare |
| VALIDATION_FAILED | field errors | after edit |
| DEPENDENCY_DEGRADED | degraded | bounded retry |
| INTEGRITY_FAILED | block + support ID | no |
| RATE_LIMITED | wait state | Retry-After |

## 11.4 Required refactors

### WEB-YOU-001

Delete catch-return-fake from apps/web/app/(consumer)/you/page.tsx.

Acceptance:

- MSW network failure renders unavailable;
- no blood type/allergy/emergency contact appears;
- emergency QR CTA disabled with reasons;
- source scan finds no production clinical defaults.

### WEB-VIS-001

Delete FALLBACK_VISIT_DETAILS and merge behavior.

Acceptance:

- partial server visit renders only fields present;
- missing SOAP/ICD/med/lab stays absent/unknown;
- verification label requires server status;
- network fail does not render any fake doctor/record.

### WEB-VIS-002

Replace local consent/document mutation fallback.

Acceptance:

- injected 500/timeout leaves UI unchanged;
- 409 surfaces version conflict;
- 2xx receipt then revalidation updates UI;
- audit ID accessible in diagnostic detail.

### WEB-CLN-001

Replace INITIAL_PATIENT_QUEUE with typed query.

Acceptance:

- loading/empty/unavailable/ready snapshots;
- no fixture in production chunk;
- capability-filtered actions;
- no link to nonexistent /clinical/intake.

### WEB-ADM-001

Delete in-memory authoritative state from admin-users.ts.

Acceptance:

- all reads/mutations use endpoints;
- failure returns success=false/throws typed error;
- no state mutation on error;
- role/lock/session E2E uses real test DB.

### WEB-ADM-002

Do same for experiments.ts and clinical-feedback.ts.

### WEB-ANA-001

Delete synthesized platform metrics and privacy pass.

Acceptance:

- empty DB snapshot shows no-data;
- missing audit receipt shows incomplete;
- metric denominators visible;
- property test disallows has_data=true with zero authoritative rows unless
  explicitly defined zero-valued metric.

### WEB-CLN-002

Clinical overview readiness comes from authoritative endpoint.

Acceptance:

- dependency down => unavailable/degraded;
- no green Safe;
- version and freshness visible;
- action requiring KB is disabled.

## 11.5 Cache policy

- Query keys include subject/tenant/scope, never raw PII.
- Logout clears all protected caches.
- Role change invalidates permission-sensitive caches.
- Consent revocation invalidates derived clinical caches.
- StaleTime is domain-specific and documented.
- Persisted client cache is encrypted or disabled for PHI per threat model.
- Cross-account cache reuse property test is mandatory.

## 11.6 SSR and hydration

- Server-rendered protected data must enforce same auth context.
- No fixture to avoid hydration mismatch.
- Serialized state excludes secrets and unnecessary PHI.
- Hydration errors fail E2E gate.
- Browser timers/listeners cleaned on unmount and teardown.

---

# 12. Flutter Mobile technical design

## 12.1 Shared contract

Flutter consumes generated or hand-verified OpenAPI DTOs matching AuthorityState.

~~~dart
sealed class AuthorityViewState<T> {}
final class Loading<T> extends AuthorityViewState<T> {}
final class Ready<T> extends AuthorityViewState<T> {
  final T data;
}
final class KnownEmpty<T> extends AuthorityViewState<T> {}
final class Unavailable<T> extends AuthorityViewState<T> {
  final String correlationId;
}
final class Degraded<T> extends AuthorityViewState<T> {
  final T? data;
  final List<String> missingCapabilities;
}
~~~

## 12.2 MOB-CLN-001 — Remove static roster

clinical_overview_surface.dart PHẢI:

- không fill patient queue sau Council/Scribe fetch;
- gọi clinical roster endpoint;
- render state machine;
- clear protected state on logout/role change;
- prevent stale async result from overwriting new session.

Tests:

- network offline;
- 401 then token refresh;
- 403;
- empty;
- partial/degraded;
- account switch during request;
- widget disposed before response;
- no fake name/MRN in golden.

## 12.3 MOB-SAFE-001 — Readiness

Hardcoded Verified label bị cấm. Version, state và freshness từ server.

## 12.4 MOB-DATA-001 — Secure storage

- access token storage theo platform secure store;
- PHI cache policy explicit;
- screenshots/background app switch threat reviewed;
- clipboard export minimized;
- logs redacted.

## 12.5 MOB-QA-001

Flutter gate:

- flutter analyze;
- dart format --set-exit-if-changed;
- flutter test;
- widget tests;
- integration tests on supported Android/iOS matrix;
- golden tests for truthful states;
- no skipped mandatory test.

---

# 13. Route inventory và layout governance

## 13.1 Correct denominator

### ROUTE-001

Inventory generator PHẢI recursively enumerate apps/web/app/**/page.tsx.

Normalization:

- remove route group segments such as (consumer);
- retain dynamic segments such as [visitId];
- normalize root to /;
- reject duplicate normalized paths;
- include newly added page automatically.

### ROUTE-002

Registry PHẢI có exactly one record cho mỗi normalized page.

### ROUTE-003

Alias target PHẢI:

- tồn tại;
- không tạo cycle;
- giữ query/context theo explicit contract;
- có auth/capability semantics tương thích.

### ROUTE-004

Mọi navigation href PHẢI resolve tới page hoặc allowed external target.

### ROUTE-005

Report machine-readable:

~~~json
{
  "filesystem_routes": 114,
  "registered_routes": 114,
  "covered_routes": 114,
  "missing": [],
  "extra": [],
  "broken_targets": [],
  "duplicate_canonicals": []
}
~~~

Số 114 chỉ là baseline tại SHA audit, không được hardcode. Khi thêm route, denominator
tự tăng.

## 13.2 Proposed implementation

Files:

- apps/web/scripts/lib/discover-app-routes.mjs;
- apps/web/scripts/generate-route-inventory.mjs;
- apps/web/scripts/check-route-layout-registry.mjs;
- apps/web/generated/route-inventory.json;
- apps/web/lib/route-layout.registry.ts.

Flow:

~~~mermaid
flowchart TD
    F[Filesystem page.tsx] --> D[Discover normalize]
    D --> I[Generated inventory]
    I --> V[Validate registry]
    R[Layout registry] --> V
    N[Navigation manifests] --> L[Link validation]
    I --> L
    V --> G[CI gate]
    L --> G
~~~

## 13.3 Route migration requirement

Mỗi trong 35 missing route phải được:

1. phân loại public/personal/clinical/research/admin/utility;
2. gán roles;
3. gán canonical experience;
4. gán shell mode/layout archetype;
5. xác định canonical/alias;
6. kiểm tra auth middleware;
7. kiểm tra mobile/desktop layout;
8. có empty/loading/error/populated contracts;
9. có reachability test;
10. có accessibility test.

---

# 14. Design token architecture

## 14.1 Canonical graph

Source:

- tokens/core.json: raw palette/space/type/motion;
- tokens/semantic.json: surface/text/border/status;
- tokens/component.json: component aliases;
- generated Web CSS và Flutter Dart.

Dependency direction:

core → semantic → component → platform output.

Legacy tokens chỉ được map tới semantic alias trong migration file và có expiry.

## 14.2 Token requirements

### TOK-001

globals.css chỉ import một generated semantic output cho token declarations.

### TOK-002

Không duplicate custom property với khác value ngoài allowlist documented.

### TOK-003

Generated files có source hash header và CI regeneration check.

### TOK-004

Web/Flutter semantic token parity test.

### TOK-005

Clinical status color không là kênh thông tin duy nhất.

### TOK-006

Contrast pass WCAG 2.2 AA ở light/dark/high-contrast.

### TOK-007

Motion respects prefers-reduced-motion và Flutter equivalent.

---

# 15. Clinical safety design

## 15.1 Capability gate

Clinical capability is computed from evidence, not from route presence:

~~~typescript
interface CapabilityDecision {
  capability: string;
  allowed: boolean;
  reasons: string[];
  evidenceRefs: string[];
  policyVersion: string;
  evaluatedAt: string;
  expiresAt: string;
}
~~~

Examples:

- generate_emergency_card;
- verify_visit_document;
- launch_ddi_check;
- open_patient_record;
- start_scribe;
- commit_clinical_proposal.

## 15.2 Safety readiness aggregation

Aggregate rule:

- healthy only if all critical dependencies healthy and fresh;
- degraded if noncritical dependency unavailable or capability subset missing;
- unavailable if critical state cannot be determined;
- unsafe/block if integrity or policy verification fails.

Unknown never maps to healthy.

## 15.3 Emergency QR threat model

Threats:

- wrong subject;
- fabricated default;
- revoked consent;
- stale clinical field;
- replayed QR;
- over-disclosure;
- screenshot leakage;
- forged payload.

Controls:

- signed opaque token;
- short TTL;
- revocation lookup;
- minimum necessary fields;
- source provenance;
- explicit user confirmation;
- audit;
- no client-side clinical payload construction.

## 15.4 Visit verification model

States:

~~~text
draft -> submitted -> verified
  |          |
  v          v
deleted    rejected
~~~

Rules:

- create always draft unless trusted ingestion policy says otherwise;
- only authorized verifier transitions submitted to verified;
- signature metadata server-generated;
- edit after verify creates new version and invalidates/archives prior verification;
- delete preserves audit/tombstone.

## 15.5 Clinical copy rules

Prohibited without receipt:

- “Đã xác minh”;
- “An toàn”;
- “Đồng bộ”;
- “Hoạt động hoàn toàn”;
- “Không có tương tác”;
- “Không có dị ứng”;
- “Nhóm máu O+” hoặc bất kỳ default cụ thể.

Allowed truthful alternatives:

- “Không thể xác minh lúc này”;
- “Chưa có dữ liệu được xác nhận”;
- “Nguồn đang không khả dụng”;
- “Dữ liệu có thể đã cũ”;
- “Cần kiểm tra lại trước khi hành động”.

---

# 16. Admin correctness design

## 16.1 Command classification

| Class | Example | Optimistic UI | Approval | Audit |
|---|---|---|---|---|
| Read-only | list users | N/A | no | access log |
| Reversible low-risk | label feedback | no committed optimistic | one admin | yes |
| Security critical | role/lock/revoke | prohibited | policy-dependent | mandatory |
| Safety critical | experiment kill/reactivate | prohibited | kill one; reactivate two-person | mandatory |
| Destructive | delete/retention action | prohibited | confirmation + policy | mandatory |

## 16.2 Last-admin invariant

Server transaction PHẢI prevent:

- demote last active admin;
- lock last active admin;
- revoke all recovery paths;
- concurrent pair of mutations that jointly violates invariant.

Test with two concurrent transactions on real PostgreSQL.

## 16.3 Kill-switch invariant

Kill is idempotent and takes effect within target propagation SLO. Client success
only after server receipt. Evaluation:

- 100 concurrent reads during kill;
- no new treatment allocation after effective_at;
- caches observe invalidation;
- audit ordering reconstructable.

## 16.4 Admin preview

Admin experience preview:

- changes presentation only;
- does not impersonate user;
- cannot bypass authorization;
- banner always visible;
- protected actions evaluated with admin’s real role and preview policy;
- audit preview activation.

---

# 17. Analytics và privacy evidence

## 17.1 Metric registry

Every metric definition contains:

- metric_id/version;
- owner;
- SQL/query artifact hash;
- source tables;
- inclusion/exclusion;
- numerator/denominator;
- time window/timezone;
- privacy classification;
- minimum sample threshold;
- freshness SLO;
- validation tests.

## 17.2 Empty and sparse behavior

- no rows => has_data=false;
- zero numerator with positive denominator => value 0;
- denominator 0 => value null, not 0%;
- below privacy threshold => suppressed;
- stale window => stale;
- aggregation error => unavailable.

## 17.3 No-PII audit

No-PII pass is not inferred from schema names. Dedicated job:

1. freeze scope;
2. scan telemetry schemas and sampled payload structure;
3. run detectors;
4. record findings;
5. human review high-risk fields;
6. sign artifact digest;
7. publish receipt.

The UI may display pass only while receipt is valid for current scope digest.

---

# 18. Test strategy và CI architecture

## 18.1 Test pyramid with mandatory negative tests

| Layer | Purpose | Mandatory examples |
|---|---|---|
| Static | forbidden imports/secrets/routes/tokens | seed import, duplicate token |
| Unit | pure mapping/state | unavailable never safe |
| Property | invariants over generated inputs | partial data never filled |
| Contract | OpenAPI client/server | enum/error/schema |
| Integration | API + PostgreSQL | RBAC/OCC/audit atomicity |
| Component | truthful UI states | loading/empty/error/stale |
| E2E | user workflow | network fault, role change |
| Security | threat controls | CSRF, IDOR, session revoke |
| Chaos | dependency failure | timeout/500/partial |
| Race | concurrency correctness | last-admin, GLHS |
| Performance | SLO/budget | p50/p95/p99, throughput |
| Accessibility | WCAG | axe/keyboard/screen reader |
| Reproducibility | clean replay | container from lockfiles |

## 18.2 Toolchain pinning

### QA-ENV-001

Web CI uses Node 20.x matching engines and npm lock.

### QA-ENV-002

Python uses locked uv environment and declared Python version.

### QA-ENV-003

Flutter version pinned via tool config/container.

### QA-ENV-004

PostgreSQL version pinned for race/integration tests.

### QA-ENV-005

Locale/timezone fixed and recorded; additional timezone matrix runs separately.

## 18.3 Web gates

Mandatory sequence:

~~~bash
npm ci
npm run consumer-terminology:check
npm run i18n:check
npm run route-matrix:check
npm run route-layout:check
npm run type-check
npm run lint
npm run test
npm run build
npm run test:a11y
npm run test:e2e
npm run bundle:check
~~~

Requirements:

- every command exit 0;
- zero unhandled errors/rejections;
- zero leaked handles/timers;
- no mandatory skipped test;
- no unexpected console error;
- warnings governed by allowlist with owner/expiry.

## 18.4 Fix ChatShell teardown

Likely class: timeout or callback survives jsdom environment.

Required approach:

- inventory setTimeout/setInterval/requestAnimationFrame/listeners;
- store handles in refs;
- cleanup in useEffect return;
- guard document/window only for SSR, not to hide lifecycle bug;
- use fake timers carefully and restore after each;
- assert no pending timers;
- run full suite in randomized/sharded order;
- repeat full suite three times.

Acceptance:

- isolated test pass;
- full suite pass;
- reverse-order/shuffle pass;
- no document-is-not-defined after teardown.

## 18.5 Backend gates

~~~bash
make lint
make type-check
make test
make docs-check
~~~

Additional:

- Alembic upgrade from supported baseline;
- downgrade test where safe;
- clean PostgreSQL integration;
- API schema diff;
- security scanners;
- migration concurrency/read compatibility.

## 18.6 Evidence manifest

~~~json
{
  "schema_version": "clara.release-evidence.v1",
  "repository": "Project-CLARA-HBT/CLARA-Care",
  "commit_sha": "40-char-sha",
  "dirty": false,
  "environment": {
    "container_digest": "sha256:...",
    "node": "20.x",
    "python": "3.11.x",
    "flutter": "pinned",
    "postgres": "pinned"
  },
  "checks": [
    {
      "id": "web-full-test",
      "command": "npm run test",
      "exit_code": 0,
      "started_at": "UTC",
      "ended_at": "UTC",
      "stdout_sha256": "sha256",
      "stderr_sha256": "sha256",
      "tests": 0,
      "failed": 0,
      "skipped": 0,
      "unhandled_errors": 0
    }
  ]
}
~~~

---

# 19. GLHS technical and formal design

## 19.1 Research thesis

Candidate contribution must be stated narrowly and falsifiably:

> GLHS is a disclosure-to-commit integrity protocol for longitudinal health AI
> that binds the exact bitemporal, consent-scoped inference context to a durable
> clinical proposal and revalidates entity-scoped state/policy predicates under
> ordered database locks at commit time.

This is potentially publishable only if the paper proves or demonstrates a delta
over transactional memory, policy-state authorization, bitemporal reasoning,
provenance standards and prompt-only arbitration. A bundle of known components
is not automatically novel.

## 19.2 State model

Let:

- u be subject;
- e be entity partition;
- V(u,e) be current partition version;
- C(u,s) be consent version for scope s;
- P be policy epoch;
- H be canonical disclosure manifest hash;
- B be binding;
- Q be proposal;
- D(Q) be dependency partitions.

Binding:

~~~text
B = Hash(
  subject_id,
  snapshot_id,
  canonical_manifest_digest,
  evidence_root,
  partition_version_vector,
  consent_version,
  policy_epoch,
  actor_role,
  purpose,
  task,
  model_manifest_id,
  issued_at,
  expires_at
)
~~~

Commit admission:

~~~text
Admit(Q) iff
  BindingExists(Q.binding_id)
  and RootLineageMatches(Q)
  and SubjectMatches(Q, B)
  and ActorAuthorizedNow(Q)
  and ConsentNow(Q.scope) = B.consent_version
  and PolicyNow = B.policy_epoch
  and CurrentTime < B.expires_at
  and for every e in D(Q): V_now(u,e) = V_bound(u,e)
  and ClinicalPredicates(Q, StateNow) = PASS
  and EvidenceIntegrity(B) = PASS
~~~

## 19.3 Canonicalization

### GLHS-CAN-001

Canonical JSON must specify:

- UTF-8;
- object key ordering;
- number representation;
- duplicate-key rejection;
- Unicode normalization decision;
- timezone normalization;
- null/absent semantics;
- arrays ordering semantics;
- NaN/Infinity rejection;
- schema version domain separation.

Cross-language golden vectors required for Python, TypeScript and any other
implementation.

### GLHS-CAN-002

Hash input includes schema/version prefix to prevent cross-protocol collision.

### GLHS-CAN-003

Evidence root construction and leaf ordering are unambiguous.

## 19.4 Entity-partitioned version vector

Requirements:

- dependency extractor is deterministic;
- unknown dependency expands conservatively;
- locks acquired in canonical total order;
- partition rows created without race;
- version vector stored in binding;
- commit re-reads after lock;
- only affected partitions increment;
- global policy/consent epochs remain checked.

Safety versus liveness:

- coarse fallback may reduce liveness but must preserve safety;
- fine partitions must not miss semantic conflict;
- false-stale and false-acceptance measured separately.

## 19.5 Lock protocol

Order:

1. subject/global security epoch if required;
2. consent scope rows ordered by key;
3. policy epoch row;
4. entity partitions sorted lexicographically;
5. proposal/binding row;
6. transition append.

Document and test all other writers that touch these tables. A proof for one
gateway is irrelevant if another writer bypasses it.

## 19.6 Proof obligations

### PO-01 — No stale dependent commit

If any partition in D(Q) changes after disclosure and before commit, Q cannot
commit under the unchanged binding.

Evidence:

- formal argument under declared DB isolation;
- TLA+/model check;
- real PostgreSQL interleaving traces.

### PO-02 — No revoked-consent commit

If relevant consent is revoked before linearization point, proposal does not
commit.

### PO-03 — No policy-epoch drift commit

Policy change before commit invalidates old binding when policy scope applies.

### PO-04 — No cross-subject binding

Proposal for subject u2 cannot use binding of u1.

### PO-05 — No lineage laundering

Derived/reviewed proposal cannot detach from root disclosure binding.

### PO-06 — Atomic audit

Every committed transition has reconstructable audit/outbox record; no audit
record claims commit when transaction rolled back.

### PO-07 — Idempotency

Retry of same idempotency key yields at most one state transition.

### PO-08 — Deadlock freedom or bounded recovery

Canonical lock order prevents protocol-internal cycles; external cycles are
detected and safely retried according to bounded policy.

### PO-09 — Noninterference of independent partitions

Writes to disjoint, correctly classified dependency sets need not invalidate
one another.

### PO-10 — Conservative dependency soundness

If dependency extractor is uncertain, it cannot omit a partition whose change
could alter admission.

### PO-11 — Expiry

Expired binding cannot commit despite clock skew within declared bound.

### PO-12 — Canonical hash consistency

All conforming implementations compute identical digest for valid inputs and
reject invalid inputs identically.

## 19.7 TLA+/model specification

Model variables:

- partitions;
- versions;
- consentEpoch;
- policyEpoch;
- bindings;
- proposals;
- transitions;
- auditEvents;
- locks;
- time;
- actors.

Actions:

- Disclose;
- ChangePartition;
- RevokeConsent;
- ChangePolicy;
- Propose;
- Review;
- AcquireLocks;
- Commit;
- Abort;
- Retry;
- Expire;
- CrashBeforeCommit;
- CrashAfterCommitBeforeResponse.

Invariants:

- NoInvalidCommit;
- SubjectIsolation;
- BindingImmutability;
- AuditCommitEquivalence;
- IdempotentTransition;
- MonotonicVersion;
- NoVerifiedWithoutVerifier.

Model-check matrix:

- subjects 2;
- partitions 2–4;
- actors 2;
- proposals 2;
- interleavings all within bound;
- crash points;
- clock steps;
- consent/policy races.

Report states/transitions and scope; never call bounded exploration a universal proof.

## 19.8 Real PostgreSQL validation

Required schedules:

- read then concurrent dependent write then commit;
- read then independent write then commit;
- consent revoke race;
- policy update race;
- cross-subject binding;
- replay;
- expiry;
- concurrent proposal retries;
- crash after DB commit before HTTP response;
- deadlock injection;
- replica lag/read source mismatch if applicable.

Concurrency levels:

- 1, 2, 4, 8, 16, 32, optionally 64 writers;
- hot single partition;
- uniform disjoint partitions;
- Zipf mixed workload;
- policy/consent churn.

Metrics:

- invalid commit acceptance;
- valid commit acceptance;
- false-stale rejection;
- p50/p95/p99 latency;
- throughput;
- deadlock/retry rate;
- lock wait;
- audit reconstruction completeness;
- storage overhead;
- binding size;
- CPU/DB IO.

## 19.9 Bypass audit

Enumerate every writer of:

- PHR state;
- visit/document state;
- consent;
- policy;
- GLHS proposal/transition;
- derived cache.

Each writer must:

- use gateway;
- be proven read-only;
- or be explicitly outside governed claim.

Static call graph plus runtime SQL audit required.

---

# 20. A* evaluation program

## 20.1 Research questions

**RQ1 — Integrity:** Does GLHS reduce invalid stale/unauthorized clinical commits
versus prespecified comparators?

**RQ2 — Utility:** Does the integrity gain preserve valid-operation acceptance
and task utility within prespecified noninferiority margins?

**RQ3 — Concurrency:** Does entity partitioning reduce false-stale and scale
better than profile-global locking without increasing invalid commits?

**RQ4 — Auditability:** Can every accepted/rejected operation be reconstructed
from immutable evidence?

**RQ5 — LLM robustness:** Does exact bound context improve lifecycle/evidence/
timeliness resolution across model families without selective retry?

**RQ6 — Cost:** What latency, token, storage and operational overhead does GLHS add?

## 20.2 Comparator tiers

### Tier A — Required implemented baselines

- unbound/full authorized history;
- state-version only;
- snapshot-bound state only;
- global profile lock GLHS;
- GLHS without predicate engine;
- GLHS without bitemporal knowledge time;
- GLHS without exact binding;
- last-write-wins;
- naive RAG/full context;
- deterministic bitemporal/provenance resolver.

### Tier B — Closest external systems

Identify through a fresh primary-source literature review before freeze.
Repository names such as MemTX, CommitGuard, Provenact and BTSA are hypotheses,
not accepted citations until bibliographic identity, code availability and task
equivalence are verified.

For each:

- exact citation/DOI/venue/version;
- public artifact/license;
- problem definition;
- same/different assumptions;
- faithful adapter plan;
- asset-gated status;
- author-contact policy if needed;
- no reimplementation labeled faithful without validation.

### Tier C — Standards/context

- HL7 FHIR provenance/consent;
- openEHR archetypes/versioning;
- W3C PROV;
- database isolation/OCC/MVCC;
- information-flow/provenance systems.

Standards are context, not necessarily performance baselines.

## 20.3 Dataset/cohort design

Requirements:

- synthetic or properly authorized data only;
- independent subject IDs;
- source/template disjoint splits;
- deterministic gold not authored by evaluated model;
- stratify conflict type, chronology, consent/policy race, dependency topology;
- freeze generator seed and exact outputs;
- detect duplicates/leakage;
- retain all subjects.

Primary v5 confirmatory plan currently says 384 subjects, 48 per stratum, primary
model claude-sonnet-4.6 and secondary gemini-3.6-flash-high. It remains
DRAFT_NOT_FROZEN and must not be described as completed.

## 20.4 Statistical plan

Primary endpoint:

- subject-level all-axes exact match, if retained after independent review.

Primary contrast:

- one prespecified comparison.

Tests:

- paired exact sign/McNemar as appropriate;
- effect size;
- 95% subject-bootstrap CI;
- alpha 0.05;
- multiplicity control for confirmatory secondary claims.

Noninferiority:

- prespecify valid-operation acceptance margin;
- prespecify task utility margin;
- CI lower bound must exceed negative margin;
- integrity improvement alone is insufficient.

Concurrency:

- repeated trials estimate performance variance but not inflate scientific N;
- mixed-effects or cluster-aware analysis if schedules cluster by subject/template;
- survival/time-to-completion if censored runs occur, prespecified.

Report:

- denominators;
- wins/losses/ties;
- all errors;
- NOT_RUN;
- model/version/provider;
- token/cost/latency;
- raw paired table;
- confidence intervals;
- exact p-values, never 0 due underflow.

## 20.5 Ablations

| Ablation | Question |
|---|---|
| No exact binding | Is binding causal? |
| Global version only | Does partitioning improve liveness? |
| No consent epoch | Is dynamic consent gate necessary? |
| No policy epoch | Is policy drift caught? |
| No predicate engine | Value of deterministic clinical predicates |
| No knowledge time | Value of bitemporal knowledge time |
| No provenance root | Value of lineage integrity |
| Prompt-only arbitration | Kernel vs LLM-only reasoning |
| Full history | Bound minimal context vs brute force |
| Dependency oracle vs inferred | Cost of dependency errors |

## 20.6 Adversarial evaluation

- tampered digest;
- duplicate JSON key;
- Unicode normalization;
- NaN/float ambiguity;
- replayed binding;
- expired binding;
- wrong subject;
- role drift;
- consent revoke;
- policy update;
- evidence deletion/retraction;
- derived proposal laundering;
- cache reuse after revocation;
- partial DB failure;
- response loss after commit;
- concurrent stale write;
- deadlock;
- model malformed output;
- provider wrong-model fallback;
- prompt injection in evidence.

## 20.7 Human/clinical review

Human adjudication must specify:

- qualifications;
- conflicts;
- blinded materials;
- rubric;
- independent reviewers;
- disagreement resolution;
- inter-rater reliability;
- no post-hoc relabeling;
- compensation/ethics;
- no claim of independent review before completion.

## 20.8 Reproducibility package

Must include:

- code SHA and archive;
- lockfiles/container digests;
- protocol/SAP;
- frozen cohorts/oracle/prompts;
- comparator adapters;
- raw outputs or privacy-preserving permissible form;
- error ledger;
- analysis scripts;
- environment manifest;
- seal/checksums;
- claim ledger;
- one-command offline verification;
- instructions for provider-dependent rerun;
- license/data-use documentation.

---

# 21. Literature positioning và manuscript design

## 21.1 Context gaps to close

Related work must cover, with verified primary sources:

1. transactional memory for AI agents;
2. database serializability, OCC, MVCC and TOCTOU;
3. policy-state authorization and continuous authorization;
4. bitemporal databases and temporal EHR;
5. clinical provenance, FHIR Consent/Provenance and openEHR versioning;
6. agent action safety and irreversible side-effect gates;
7. tamper-evident logs and Merkle transparency;
8. LLM context/provenance binding;
9. clinical decision support safety;
10. benchmark leakage and reproducible LLM evaluation.

## 21.2 Closest-competitor audit template

| Field | Competitor A | Competitor B | GLHS |
|---|---|---|---|
| Exact citation | verify | verify | repository |
| Core object |  |  | disclosure binding |
| Threat model |  |  | stale/unauthorized commit |
| Bitemporal |  |  | explicit |
| Dynamic consent |  |  | commit-time |
| Policy epoch |  |  | commit-time |
| Content-state binding |  |  | manifest hash |
| Entity partitions |  |  | version vector |
| Clinical predicates |  |  | deterministic gate |
| Persistent write gate |  |  | PostgreSQL transaction |
| Formal guarantee |  |  | scoped proof obligations |
| Direct code baseline | status | status | full |
| Same-task result | status | status | pending |

## 21.3 Strong positioning paragraph outline

> Existing work addresses subsets of the problem: transactional agent memory
> protects memory operations, policy-state systems revalidate authority, temporal
> health models reconstruct evolving facts, and provenance standards describe
> lineage. None of those differences may be asserted by name until verified.
> GLHS targets the composition gap between the exact health state disclosed to
> an inference and the later persistent clinical write. It commits only when a
> durable binding over bitemporal evidence, entity-version dependencies,
> consent, policy, actor, purpose and task remains valid after ordered database
> locks and deterministic clinical predicates. The contribution is therefore
> not “more context” or a UI feature; it is a scoped disclosure-to-commit
> integrity contract. We evaluate that contract against faithful same-task
> baselines on invalid-write prevention, valid-operation noninferiority,
> false-stale burden, audit reconstruction and systems overhead.

## 21.4 Claims prohibited until evidence exists

- “first”;
- “only”;
- “universally safe”;
- “clinically validated”;
- “zero hallucination”;
- “100% secure”;
- “superior to all SOTA”;
- “79/79 routes” when denominator is not filesystem;
- “100% tests pass” with nonzero exit/unhandled errors;
- “verified” without verifier receipt.

## 21.5 Paper structure

1. Problem and motivating race.
2. Threat/assumption model.
3. Formal state and desired properties.
4. GLHS protocol.
5. Implementation in PostgreSQL/API.
6. Proof sketch and bounded model checking.
7. Experimental methodology.
8. Integrity results.
9. Utility/noninferiority.
10. Concurrency/performance.
11. Auditability/security.
12. Related work.
13. Limitations and external validity.
14. Ethics/data governance.
15. Reproducibility.

---

# 22. Execution plan and phase gates

## Phase 0 — Freeze, containment, truthful baseline

Goal:

- stop security/data-integrity risk;
- freeze exact baseline;
- make claims truthful.

Exit gate:

- credential revoked/rotated;
- dangerous production fallbacks feature-disabled or removed;
- release banner/flag prevents deployment;
- evidence inventory captured;
- no old claim overwritten.

## Phase 1 — Authoritative backend foundations

Goal:

- migrations and endpoints for admin users, experiments, feedback, roster, visits,
  analytics/readiness.

Exit gate:

- OpenAPI contract;
- RBAC/CSRF/OCC/audit tests;
- PostgreSQL integration;
- migrations upgrade/downgrade;
- no client migration yet depends on unavailable API.

## Phase 2 — Web data-truth remediation

Goal:

- remove all fake/false-success client paths.

Exit gate:

- static fixture isolation;
- fault-injection component/E2E pass;
- critical mutation receipts;
- no fake clinical/admin values in production chunks.

## Phase 3 — Mobile parity

Goal:

- remove static clinical queue/readiness;
- consume authoritative envelopes.

Exit gate:

- analyze/test/integration/golden pass;
- account-switch and offline safety pass.

## Phase 4 — Route/token/test governance

Goal:

- correct denominator;
- canonical tokens;
- clean full suite.

Exit gate:

- filesystem route coverage 100%;
- broken links 0;
- duplicate token overrides 0;
- Node 20 full run exit 0, zero unhandled errors.

## Phase 5 — GLHS kernel/formal closure

Goal:

- close proof obligations;
- remove bypasses;
- validate real PostgreSQL schedules.

Exit gate:

- formal spec/model report;
- real DB race traces;
- canonicalization vectors;
- false-stale/scaling measurements;
- audit reconstruction.

## Phase 6 — Frozen A* evaluation

Goal:

- direct baselines;
- preregistered confirmatory execution;
- independent review.

Exit gate:

- frozen/sealed inputs;
- authorized one-shot run;
- complete denominators/errors;
- statistical report;
- reproducibility package.

## Phase 7 — Manuscript and release

Goal:

- synchronize claims;
- release only supported system.

Exit gate:

- claim ledger exact;
- independent reproduction;
- security/clinical/legal sign-off;
- release evidence same SHA;
- 10/10 rubric pass or honest lower score.

---

# 23. Prioritized top five actions

1. **P0 incident + data containment:** revoke/rotate/scrub secret and remove/disable
   every production clinical/admin/analytics fake path.
2. **Build authoritative backend and mutation semantics:** admin users,
   experiments, feedback, roster, visits, analytics/readiness with RBAC, CSRF,
   OCC, idempotency and atomic audit.
3. **Replace clients and tests with fail-closed state machines:** Web/Mobile,
   negative network/timeout/partial/403/409 tests, production bundle fixture scan.
4. **Repair governance and evidence:** filesystem-derived 114+ route inventory,
   token single source, Node 20 clean full suite, GitHub CI receipts.
5. **Earn—not assert—A* superiority:** formalize GLHS, run real PostgreSQL
   concurrency, implement faithful direct comparators, freeze a confirmatory
   study, preserve all errors/nulls and publish a reproducibility package.

---

# 24. Work breakdown structure

The task catalog below is normative. Priority order is P0 → P1 → P2. Dependency
IDs must be honored unless a written architecture decision explains otherwise.

## 24.1 Phase 0 tasks — Incident and containment

| ID | P | Task | Dependency | Acceptance evidence |
|---|---:|---|---|---|
| T0001 | P0 | Record exact baseline SHA, parent, branch and dirty state | none | baseline receipt |
| T0002 | P0 | Open restricted credential incident | T0001 | incident ID/owner |
| T0003 | P0 | Identify provider/account/scope without copying secret | T0002 | redacted scope note |
| T0004 | P0 | Revoke exposed SMTP credential | T0003 | old auth fails |
| T0005 | P0 | Rotate to new secret via approved manager | T0004 | provider receipt |
| T0006 | P0 | Audit suspicious use during exposure window | T0003 | audit summary |
| T0007 | P0 | Remove secret default from API config | T0005 | config test |
| T0008 | P0 | Remove secret from app compose | T0005 | compose config test |
| T0009 | P0 | Remove secret from deploy compose | T0005 | compose config test |
| T0010 | P0 | Replace exact-value email test | T0007 | ephemeral fixture test |
| T0011 | P0 | Scan working tree | T0007-T0010 | scanner JSON |
| T0012 | P0 | Plan approved Git history rewrite | T0002 | signed plan |
| T0013 | P0 | Dry-run history scrub on mirror | T0012 | before/after scan |
| T0014 | P0 | Coordinate remote rewrite and clone recovery | T0013 | comms/rollback plan |
| T0015 | P0 | Execute approved history scrub | T0014 | all-ref scan |
| T0016 | P0 | Scan Docker layers and release artifacts | T0015 | image scan |
| T0017 | P0 | Add pre-commit secret scanner | T0011 | planted canary test |
| T0018 | P0 | Add CI diff/history/image secret gates | T0016 | CI receipt |
| T0019 | P0 | Add runtime secret redaction test | T0007 | log snapshot |
| T0020 | P0 | Close incident retrospective | T0004-T0019 | sign-off |
| T0021 | P0 | Add temporary deployment block for SHA lineage | T0001 | release gate test |
| T0022 | P0 | Inventory all production fixture/seed paths | T0001 | machine list |
| T0023 | P0 | Feature-disable Emergency QR if authority absent | T0022 | E2E fault test |
| T0024 | P0 | Feature-disable false admin mutations | T0022 | 5xx test |
| T0025 | P0 | Mark fake analytics unavailable | T0022 | empty DB UI |
| T0026 | P0 | Preserve old audit artifacts read-only | T0001 | checksum inventory |
| T0027 | P0 | Correct release claim from 100% tests | T0001 | claim diff |
| T0028 | P0 | Correct route claim denominator | T0001 | claim diff |
| T0029 | P0 | Create blocker dashboard from evidence, not manual checkboxes | T0001 | generated report |
| T0030 | P0 | Obtain security owner acceptance of containment gate | T0020 | approval receipt |

## 24.2 Phase 1 tasks — API and database foundation

| ID | P | Task | Dependency | Acceptance evidence |
|---|---:|---|---|---|
| T0101 | P0 | Define shared authority envelope in OpenAPI | T0001 | schema diff |
| T0102 | P0 | Define shared error envelope | T0101 | contract tests |
| T0103 | P0 | Define mutation receipt | T0101 | contract tests |
| T0104 | P0 | Implement idempotency middleware/store | T0103 | retry property test |
| T0105 | P0 | Implement resource-version/OCC helper | T0103 | concurrent test |
| T0106 | P0 | Implement audit outbox atomic helper | T0103 | rollback test |
| T0107 | P0 | Add correlation ID propagation | T0102 | trace integration |
| T0108 | P0 | Add safe error mapper/redactor | T0102 | security tests |
| T0109 | P0 | Generate/update typed Web client | T0101-T0108 | contract build |
| T0110 | P0 | Generate/update Flutter DTOs | T0101-T0108 | Dart contract test |
| T0111 | P0 | Design admin user migration/schema indexes | T0105 | migration review |
| T0112 | P0 | Implement admin users GET list/detail | T0111 | DB integration |
| T0113 | P0 | Implement role transition endpoint | T0112 | RBAC/OCC tests |
| T0114 | P0 | Implement lock endpoint | T0112 | session test |
| T0115 | P0 | Implement unlock endpoint | T0112 | state test |
| T0116 | P0 | Implement session revoke endpoint | T0112 | propagation test |
| T0117 | P0 | Enforce last-active-admin invariant | T0113-T0115 | race test |
| T0118 | P0 | Audit all admin user mutations | T0106,T0113-T0116 | reconstruction |
| T0119 | P0 | Design experiments schema | T0105 | ADR/migration |
| T0120 | P0 | Implement experiment list/detail/create | T0119 | integration |
| T0121 | P0 | Implement rollout mutation with caps | T0120 | policy tests |
| T0122 | P0 | Implement idempotent kill-switch | T0120 | concurrency test |
| T0123 | P0 | Implement two-person reactivation if required | T0122 | approval test |
| T0124 | P0 | Audit experiment changes | T0106,T0121-T0123 | ledger test |
| T0125 | P0 | Design clinical feedback schema/retention | T0105 | migration/ADR |
| T0126 | P0 | Implement feedback list/detail | T0125 | access tests |
| T0127 | P0 | Implement feedback status/assignment/resolution | T0126 | OCC/idempotency |
| T0128 | P0 | Implement feedback redaction/field access | T0126 | privacy test |
| T0129 | P0 | Design clinical roster query | T0101 | OpenAPI review |
| T0130 | P0 | Implement assignment-scoped roster endpoint | T0129 | IDOR/RBAC tests |
| T0131 | P0 | Implement roster capability decisions | T0130 | policy tests |
| T0132 | P0 | Audit patient record access | T0130 | audit test |
| T0133 | P0 | Review visit schema/versioning | T0105 | ADR |
| T0134 | P0 | Implement authoritative visit detail | T0133 | partial-data tests |
| T0135 | P0 | Implement document create as draft | T0134 | status test |
| T0136 | P0 | Implement document delete/tombstone | T0134 | audit/OCC |
| T0137 | P0 | Implement explicit verify transition | T0135 | role/signature test |
| T0138 | P0 | Implement scribe consent transition | T0134 | consent ledger test |
| T0139 | P0 | Design emergency-card eligibility | T0101 | threat review |
| T0140 | P0 | Implement eligibility endpoint | T0139 | missing field tests |
| T0141 | P0 | Implement signed/revocable QR token | T0140 | replay/revoke test |
| T0142 | P0 | Implement emergency-card audit | T0141 | audit reconstruction |
| T0143 | P0 | Build metric registry schema | T0101 | schema tests |
| T0144 | P0 | Implement platform analytics aggregation | T0143 | known-empty tests |
| T0145 | P0 | Implement privacy audit receipt model | T0143 | signature/digest tests |
| T0146 | P0 | Implement readiness dependency model | T0101 | chaos tests |
| T0147 | P0 | Implement aggregate fail-closed readiness | T0146 | property tests |
| T0148 | P1 | Add cursor pagination consistency tests | T0112,T0126,T0130 | property tests |
| T0149 | P1 | Add rate limits per admin/clinical endpoint | endpoints | load/security |
| T0150 | P0 | Run clean PostgreSQL migration matrix | T0111-T0147 | receipts |
| T0151 | P0 | Run OpenAPI backward compatibility gate | T0101-T0147 | diff artifact |
| T0152 | P0 | Threat-model all new endpoints | T0112-T0147 | signed review |
| T0153 | P0 | Verify CSRF on cookie mutations | T0113-T0142 | security suite |
| T0154 | P0 | Verify bearer behavior and scopes | T0113-T0142 | security suite |
| T0155 | P0 | Verify no PII in audit/telemetry | T0106-T0147 | privacy receipt |
| T0156 | P1 | Document SLO/freshness per endpoint | endpoints | docs check |
| T0157 | P1 | Add dependency timeout budgets | endpoints | chaos receipt |
| T0158 | P1 | Add read-after-write consistency contract | mutations | integration |
| T0159 | P0 | Prohibit seed routes in production | T0120,T0126,T0130 | route scan |
| T0160 | P0 | Obtain backend/security/clinical design sign-off | T0150-T0159 | approvals |

## 24.3 Phase 2 tasks — Web remediation

| ID | P | Task | Dependency | Acceptance evidence |
|---|---:|---|---|---|
| T0201 | P0 | Introduce AuthorityState/ViewState adapter | T0109 | unit/property |
| T0202 | P0 | Introduce authoritative mutation controller | T0109 | fault tests |
| T0203 | P0 | Add forbidden fixture import rule | T0022 | canary |
| T0204 | P0 | Add production bundle seed scanner | T0022 | bundle receipt |
| T0205 | P0 | Remove fake You profile fallback | T0201,T0140 | component/E2E |
| T0206 | P0 | Separate You empty/unavailable/degraded states | T0205 | snapshots |
| T0207 | P0 | Gate Emergency QR on eligibility | T0140,T0205 | safety E2E |
| T0208 | P0 | Remove blood/allergy defaults | T0205 | static scan |
| T0209 | P0 | Remove FALLBACK_VISIT_DETAILS | T0134,T0201 | component tests |
| T0210 | P0 | Stop merging partial visit with fake fields | T0209 | partial contract |
| T0211 | P0 | Replace scribe consent local success | T0138,T0202 | 500/409 tests |
| T0212 | P0 | Replace document create fake verified | T0135,T0202 | status tests |
| T0213 | P0 | Replace document delete local success | T0136,T0202 | timeout tests |
| T0214 | P0 | Rewrite visits-page test that enshrines fallback | T0209-T0213 | negative tests |
| T0215 | P0 | Remove INITIAL_PATIENT_QUEUE | T0130,T0201 | bundle scan |
| T0216 | P0 | Fetch authoritative roster | T0215 | state tests |
| T0217 | P0 | Route roster actions by capabilities | T0131,T0216 | link/policy tests |
| T0218 | P0 | Remove /clinical/intake broken link | T0217 | link checker |
| T0219 | P0 | Remove in-memory admin-users authority | T0112-T0116,T0202 | E2E |
| T0220 | P0 | Implement role mutation UI receipt flow | T0113,T0219 | chaos E2E |
| T0221 | P0 | Implement lock/unlock UI receipt flow | T0114,T0115,T0219 | chaos E2E |
| T0222 | P0 | Implement revoke-sessions receipt flow | T0116,T0219 | propagation E2E |
| T0223 | P0 | Rewrite admin-users offline-success tests | T0219-T0222 | negative tests |
| T0224 | P0 | Remove in-memory experiment authority | T0120-T0123,T0202 | E2E |
| T0225 | P0 | Implement rollout conflict/error UI | T0121,T0224 | 409/500 tests |
| T0226 | P0 | Implement kill-switch authoritative UI | T0122,T0224 | latency/receipt |
| T0227 | P0 | Rewrite experiments fallback tests | T0224-T0226 | negative tests |
| T0228 | P0 | Remove feedback seed fallback | T0126,T0201 | bundle scan |
| T0229 | P0 | Implement feedback mutations | T0127,T0202 | E2E |
| T0230 | P0 | Rewrite feedback offline-success tests | T0228,T0229 | negative tests |
| T0231 | P0 | Remove synthetic analytics generators | T0144,T0201 | static scan |
| T0232 | P0 | Render honest no-data analytics | T0231 | empty DB E2E |
| T0233 | P0 | Render metric provenance/denominator | T0144,T0231 | UI contract |
| T0234 | P0 | Remove fabricated privacy pass | T0145,T0231 | missing receipt |
| T0235 | P0 | Render privacy audit incomplete/fail/pass | T0145,T0234 | state tests |
| T0236 | P0 | Remove hardcoded DrugBank Verified | T0146,T0201 | static scan |
| T0237 | P0 | Implement readiness state UI | T0147,T0236 | chaos E2E |
| T0238 | P0 | Disable dependent actions on unavailable | T0237 | safety E2E |
| T0239 | P1 | Add freshness/provenance disclosure component | T0201 | a11y tests |
| T0240 | P1 | Ensure all errors have correlation ID | T0107,T0201 | E2E |
| T0241 | P1 | Clear protected query cache on logout | T0201 | account-switch |
| T0242 | P1 | Invalidate cache on role change | T0220 | policy E2E |
| T0243 | P1 | Invalidate cache on consent revoke | T0211 | consent E2E |
| T0244 | P1 | Audit persisted browser cache policy | T0201 | threat report |
| T0245 | P1 | Remove raw upstream errors from End_User | T0201 | i18n/security |
| T0246 | P1 | Add vi/en parity for authority states | T0201 | i18n check |
| T0247 | P1 | Add axe tests to all changed surfaces | T0205-T0238 | a11y receipt |
| T0248 | P1 | Add keyboard/focus tests | T0205-T0238 | component/E2E |
| T0249 | P0 | Run production bundle fixture scan | T0203-T0238 | artifact |
| T0250 | P0 | Run Web full gate on Node 20 | T0205-T0249 | CI receipt |
| T0251 | P0 | Review clinical copy for unsupported certainty | T0205-T0238 | clinical sign-off |
| T0252 | P0 | Review admin action truth | T0219-T0230 | security sign-off |
| T0253 | P1 | Add error recovery UX without fake defaults | T0201 | usability tests |
| T0254 | P1 | Add stale-state read-only UX | T0201 | component tests |
| T0255 | P1 | Add conflict compare/reload UX | T0202 | 409 E2E |
| T0256 | P0 | Verify no catch-return-seed remains | T0205-T0238 | AST scan |
| T0257 | P0 | Verify no success=true after catch | T0219-T0230 | AST/property |
| T0258 | P0 | Verify verified status only server-derived | T0209-T0238 | taint test |
| T0259 | P1 | Document file-level decisions | T0205-T0238 | ADR/docs |
| T0260 | P0 | Obtain Web/clinical/security exit approval | T0250-T0259 | approvals |

## 24.4 Phase 3 tasks — Mobile

| ID | P | Task | Dependency | Acceptance evidence |
|---|---:|---|---|---|
| T0301 | P0 | Add AuthorityViewState DTO/mapping | T0110 | Dart unit tests |
| T0302 | P0 | Remove static patient queue | T0130,T0301 | static scan |
| T0303 | P0 | Fetch roster with assignment scope | T0302 | widget/integration |
| T0304 | P0 | Render loading/empty/unavailable/degraded | T0303 | goldens |
| T0305 | P0 | Route actions from capabilities | T0131,T0303 | widget tests |
| T0306 | P0 | Remove hardcoded Verified readiness | T0146,T0301 | static scan |
| T0307 | P0 | Render authoritative readiness/freshness | T0306 | chaos tests |
| T0308 | P0 | Disable safety-dependent actions | T0307 | widget tests |
| T0309 | P0 | Prevent old request after account switch | T0303 | race test |
| T0310 | P0 | Clear protected state on logout | T0303 | integration |
| T0311 | P1 | Audit secure storage/cache | T0301 | threat report |
| T0312 | P1 | Redact mobile logs | T0301 | log tests |
| T0313 | P1 | Add background/screenshot privacy policy | T0311 | platform tests |
| T0314 | P1 | Add offline UX without fixture | T0304 | offline tests |
| T0315 | P1 | Add vi/en parity | T0304,T0307 | localization |
| T0316 | P1 | Add accessibility semantics | T0304,T0307 | widget audit |
| T0317 | P0 | Run dart format gate | changes | receipt |
| T0318 | P0 | Run flutter analyze | changes | receipt |
| T0319 | P0 | Run full flutter test | changes | receipt |
| T0320 | P0 | Run Android integration matrix | T0319 | CI artifact |
| T0321 | P0 | Run iOS integration matrix | T0319 | CI artifact |
| T0322 | P0 | Scan production app for fixture strings | T0302-T0308 | binary scan |
| T0323 | P1 | Verify deep links/capabilities | T0305 | link tests |
| T0324 | P0 | Clinical safety review mobile states | T0304-T0308 | approval |
| T0325 | P0 | Mobile phase exit | T0317-T0324 | evidence bundle |

## 24.5 Phase 4 tasks — Routes, tokens, QA and CI

| ID | P | Task | Dependency | Acceptance evidence |
|---|---:|---|---|---|
| T0401 | P1 | Extract filesystem route discovery module | none | unit tests |
| T0402 | P1 | Normalize route groups/dynamic segments | T0401 | property tests |
| T0403 | P1 | Detect normalized duplicates | T0402 | negative test |
| T0404 | P1 | Generate route inventory JSON | T0402 | deterministic diff |
| T0405 | P1 | Replace fixed 79 checker denominator | T0404 | canary new route |
| T0406 | P1 | Add missing-route failure | T0405 | negative test |
| T0407 | P1 | Add extra-registry failure | T0405 | negative test |
| T0408 | P1 | Add alias target/cycle validation | T0405 | graph tests |
| T0409 | P1 | Add navigation href validation | T0404 | link report |
| T0410 | P1 | Classify /admin/audit | T0405 | registry test |
| T0411 | P1 | Classify /admin/experiments | T0405 | registry test |
| T0412 | P1 | Classify /admin/feedback | T0405 | registry test |
| T0413 | P1 | Classify /admin/system | T0405 | registry test |
| T0414 | P1 | Classify /admin/users | T0405 | registry test |
| T0415 | P1 | Classify /ask | T0405 | registry test |
| T0416 | P1 | Classify /auth/callback | T0405 | registry test |
| T0417 | P1 | Classify all /care routes | T0405 | registry test |
| T0418 | P1 | Classify /chat/[chatId] and share token | T0405 | registry test |
| T0419 | P1 | Classify all /clinical routes | T0405 | registry test |
| T0420 | P1 | Classify all /health routes | T0405 | registry test |
| T0421 | P1 | Classify /home and /onboarding | T0405 | registry test |
| T0422 | P1 | Classify /lifemap/timeline | T0405 | registry test |
| T0423 | P1 | Classify medicine detail/cabinet | T0405 | registry test |
| T0424 | P1 | Classify visit detail | T0405 | registry test |
| T0425 | P1 | Classify all /you routes | T0405 | registry test |
| T0426 | P1 | Update layout spec from actual inventory | T0410-T0425 | generated matrix |
| T0427 | P1 | Add route coverage JSON receipt | T0426 | CI artifact |
| T0428 | P1 | Inventory current token sources/overrides | none | graph report |
| T0429 | P1 | Choose canonical token source via ADR | T0428 | approved ADR |
| T0430 | P1 | Generate Web semantic CSS | T0429 | hash check |
| T0431 | P1 | Generate Flutter semantic Dart | T0429 | parity check |
| T0432 | P1 | Remove legacy override import | T0430 | computed-style tests |
| T0433 | P1 | Add duplicate token detector | T0430 | canary |
| T0434 | P1 | Add contrast matrix | T0430,T0431 | WCAG report |
| T0435 | P1 | Pin Node 20 CI image | none | version receipt |
| T0436 | P1 | Reproduce ChatShell teardown error | T0435 | failing test |
| T0437 | P1 | Inventory timers/listeners/subscriptions | T0436 | checklist |
| T0438 | P1 | Add cleanup and lifecycle tests | T0437 | focused pass |
| T0439 | P1 | Run shuffled/reversed test order | T0438 | receipts |
| T0440 | P1 | Run full Vitest three times | T0438 | 3x exit 0 |
| T0441 | P1 | Eliminate/triage act warnings | T0440 | warning report |
| T0442 | P1 | Eliminate unexpected network calls in unit tests | T0440 | network-block run |
| T0443 | P1 | Eliminate jsdom navigation warnings | T0440 | warning report |
| T0444 | P1 | Add unhandled rejection/error hard gate | T0440 | canary |
| T0445 | P1 | Create GitHub required checks | T0250,T0325,T0427-T0444 | branch policy |
| T0446 | P1 | Upload signed evidence manifests | T0445 | artifacts |
| T0447 | P1 | Make release job require same-SHA checks | T0445 | negative test |
| T0448 | P1 | Add stale-check rejection | T0447 | simulated old SHA |
| T0449 | P1 | Add clean-tree/container replay job | T0445 | replay receipt |
| T0450 | P1 | Phase exit audit | T0401-T0449 | independent report |

## 24.6 Phase 5 tasks — GLHS kernel and formal evidence

| ID | P | Task | Dependency | Acceptance evidence |
|---|---:|---|---|---|
| T0501 | P1 | Freeze exact GLHS threat/assumption model | Phase 4 | reviewed spec |
| T0502 | P1 | Define linearization points | T0501 | formal doc |
| T0503 | P1 | Define partition dependency semantics | T0501 | spec/vectors |
| T0504 | P1 | Audit all governed DB writers | T0501 | call graph/SQL |
| T0505 | P1 | Close or scope every bypass | T0504 | tests/claim limits |
| T0506 | P1 | Specify canonical JSON | T0501 | normative spec |
| T0507 | P1 | Build cross-language golden vectors | T0506 | Python/TS pass |
| T0508 | P1 | Reject duplicate keys/nonfinite values | T0506 | adversarial tests |
| T0509 | P1 | Domain-separate hashes | T0506 | vector tests |
| T0510 | P1 | Design entity partition schema | T0503 | ADR/migration |
| T0511 | P1 | Implement additive migration | T0510 | upgrade/downgrade |
| T0512 | P1 | Implement deterministic dependency extractor | T0503 | property tests |
| T0513 | P1 | Implement conservative unknown fallback | T0512 | safety tests |
| T0514 | P1 | Implement canonical lock order | T0510,T0512 | race tests |
| T0515 | P1 | Store version vector in binding | T0510 | DB test |
| T0516 | P1 | Re-read binding/epochs after locks | T0514,T0515 | interleavings |
| T0517 | P1 | Increment only affected partitions | T0514 | disjoint test |
| T0518 | P1 | Ensure global consent/policy invalidation | T0516 | race tests |
| T0519 | P1 | Preserve root lineage through review | T0515 | laundering tests |
| T0520 | P1 | Ensure atomic transition/audit outbox | T0106,T0516 | crash tests |
| T0521 | P1 | Ensure idempotent retry after lost response | T0104,T0520 | crash tests |
| T0522 | P1 | Define all proof obligations PO-01–PO-12 | T0501-T0521 | ledger |
| T0523 | P1 | Update TLA+ spec variables/actions | T0522 | spec review |
| T0524 | P1 | Model-check bounded matrix | T0523 | states/transitions |
| T0525 | P1 | Preserve counterexample traces | T0524 | artifacts |
| T0526 | P1 | Reconcile prior TOCTOU mismatches | T0522 | new frozen run |
| T0527 | P1 | Build isolated PostgreSQL harness | T0511-T0521 | reproducible env |
| T0528 | P1 | Run dependent-write schedule | T0527 | trace |
| T0529 | P1 | Run disjoint-write schedule | T0527 | trace |
| T0530 | P1 | Run consent revoke race | T0527 | trace |
| T0531 | P1 | Run policy update race | T0527 | trace |
| T0532 | P1 | Run cross-subject/replay/expiry attacks | T0527 | traces |
| T0533 | P1 | Run crash-point matrix | T0527 | reconstruction |
| T0534 | P1 | Run writer levels 1/2/4/8/16/32 | T0527 | performance table |
| T0535 | P1 | Run hot/disjoint/Zipf workloads | T0534 | table/traces |
| T0536 | P1 | Measure false-stale burden | T0534,T0535 | CI/effect |
| T0537 | P1 | Measure valid-operation acceptance | T0534,T0535 | noninferiority input |
| T0538 | P1 | Measure latency/throughput/locks/IO | T0534,T0535 | profiles |
| T0539 | P1 | Verify audit reconstruction completeness | T0527-T0535 | denominator report |
| T0540 | P1 | Independent formal/security review | T0522-T0539 | review report |
| T0541 | P1 | Fix findings without rewriting historical evidence | T0540 | new version ledger |
| T0542 | P1 | Seal GLHS formal/system evidence bundle | T0541 | checksums |
| T0543 | P1 | Update claim ledger with scoped claims | T0542 | ledger validation |
| T0544 | P1 | Document limitations/unproven properties | T0542 | manuscript section |
| T0545 | P1 | Phase exit gate | T0501-T0544 | independent approval |

## 24.7 Phase 6 tasks — A* evaluation

| ID | P | Task | Dependency | Acceptance evidence |
|---|---:|---|---|---|
| T0601 | P1 | Run fresh primary-source literature search | T0545 | search log |
| T0602 | P1 | Verify bibliographic identity of closest work | T0601 | citation ledger |
| T0603 | P1 | Audit comparator code/license/assets | T0602 | asset matrix |
| T0604 | P1 | Select top two faithful closest competitors | T0603 | rationale |
| T0605 | P1 | Define same-task adapter contracts | T0604 | adapter spec |
| T0606 | P1 | Implement unbound/full-history baseline | T0545 | conformance |
| T0607 | P1 | Implement state-version baseline | T0545 | conformance |
| T0608 | P1 | Implement snapshot-bound baseline | T0545 | conformance |
| T0609 | P1 | Implement global-lock GLHS baseline | T0545 | conformance |
| T0610 | P1 | Implement LWW/naive RAG/resolver baselines | T0545 | conformance |
| T0611 | P1 | Implement GLHS ablations | T0545 | conformance |
| T0612 | P1 | Implement external comparator A if assets permit | T0605 | fidelity review |
| T0613 | P1 | Implement external comparator B if assets permit | T0605 | fidelity review |
| T0614 | P1 | Label unavailable comparator ASSET_GATED | T0603 | honest matrix |
| T0615 | P1 | Independently review research question | T0604-T0614 | review |
| T0616 | P1 | Finalize subject/template generator | T0615 | generator tests |
| T0617 | P1 | Freeze disjoint train/dev/final strata | T0616 | leakage report |
| T0618 | P1 | Freeze deterministic gold/oracle | T0616 | oracle review |
| T0619 | P1 | Freeze model/provider mapping | T0615 | manifest |
| T0620 | P1 | Freeze prompts and output schema | T0615 | hashes |
| T0621 | P1 | Freeze retry/error policy | T0615 | SAP |
| T0622 | P1 | Freeze primary endpoint/contrast | T0615 | SAP |
| T0623 | P1 | Prespecify noninferiority margins | T0615 | rationale |
| T0624 | P1 | Prespecify multiplicity | T0615 | SAP |
| T0625 | P1 | Prespecify cost/latency analysis | T0615 | SAP |
| T0626 | P1 | Prespecify exclusion/invalidation rules | T0615 | SAP |
| T0627 | P1 | Validate power/sample-size assumptions | T0622-T0624 | analysis |
| T0628 | P1 | Create frozen manifest and SHA-256 seal | T0617-T0627 | seal |
| T0629 | P1 | Run offline no-network preflight | T0628 | receipt |
| T0630 | P1 | Obtain explicit provider-cost approval | T0629 | authority |
| T0631 | P1 | Execute one-shot confirmatory run | T0630 | append-only raw |
| T0632 | P1 | Retain all failures/wrong-model/malformed | T0631 | error ledger |
| T0633 | P1 | Verify model identity and no fallback | T0631 | provider receipts |
| T0634 | P1 | Verify denominator and no duplicate N | T0631 | audit |
| T0635 | P1 | Run locked primary analysis | T0631-T0634 | report |
| T0636 | P1 | Run locked secondary/ablation analyses | T0635 | corrected report |
| T0637 | P1 | Run concurrency/performance analysis | T0534-T0538 | report |
| T0638 | P1 | Conduct blinded human adjudication | approvals | IRR/report |
| T0639 | P1 | Run reproducibility replay by independent operator | T0635 | replay |
| T0640 | P1 | Seal raw/analysis/report artifacts | T0635-T0639 | checksums |
| T0641 | P1 | Update claim ledger mechanically | T0640 | validator |
| T0642 | P1 | Draft results including nulls/limitations | T0641 | manuscript |
| T0643 | P1 | Ruthless mock PC review | T0642 | review |
| T0644 | P1 | Address review without post-hoc claim inflation | T0643 | response log |
| T0645 | P1 | Phase exit or honest inconclusive decision | T0601-T0644 | signed decision |

## 24.8 Phase 7 tasks — Release/manuscript

| ID | P | Task | Dependency | Acceptance evidence |
|---|---:|---|---|---|
| T0701 | P1 | Synchronize README/docs/release claims | T0645 | claim validator |
| T0702 | P1 | Build manuscript source/PDF | T0645 | build receipt |
| T0703 | P1 | Render and visually inspect PDF | T0702 | page audit |
| T0704 | P1 | Verify citations and URLs | T0702 | citation audit |
| T0705 | P1 | Verify artifact anonymity policy | T0702 | venue checklist |
| T0706 | P1 | Verify ethics/data/license statements | T0702 | approvals |
| T0707 | P1 | Run final clean clone build | T0701 | receipt |
| T0708 | P1 | Run full Web gate | T0707 | same-SHA receipt |
| T0709 | P1 | Run full Mobile gate | T0707 | same-SHA receipt |
| T0710 | P1 | Run full API/ML gate | T0707 | same-SHA receipt |
| T0711 | P1 | Run security/secret/image scans | T0707 | same-SHA receipt |
| T0712 | P1 | Run route/token/a11y/E2E gates | T0707 | same-SHA receipt |
| T0713 | P1 | Run GLHS formal/DB regression | T0707 | same-SHA receipt |
| T0714 | P1 | Validate evidence manifest/checksums | T0708-T0713 | validator |
| T0715 | P1 | Verify no P0/P1 open | T0714 | issue query |
| T0716 | P1 | Security sign-off | T0711,T0715 | approval |
| T0717 | P1 | Clinical safety sign-off | T0708-T0715 | approval |
| T0718 | P1 | Privacy/legal sign-off | T0706,T0711 | approval |
| T0719 | P1 | Research integrity sign-off | T0645,T0702 | approval |
| T0720 | P1 | Release captain go/no-go | T0714-T0719 | decision |
| T0721 | P2 | Deploy canary only after GO | T0720 | canary metrics |
| T0722 | P2 | Verify canary truthful states | T0721 | synthetic probes |
| T0723 | P2 | Verify rollback | T0721 | rollback drill |
| T0724 | P2 | Progressive rollout | T0722,T0723 | staged receipts |
| T0725 | P2 | Post-release monitoring | T0724 | SLO report |

---

# 25. File-by-file implementation map

| File/area | Required change | Primary tasks |
|---|---|---|
| services/api/src/clara_api/core/config.py | remove literal/default secret; required SecretStr | T0007 |
| deploy/docker/docker-compose.app.yml | secret injection only | T0008 |
| deploy/docker/docker-compose.deploy.yml | secret injection only | T0009 |
| services/api/tests/test_auth_email_delivery.py | ephemeral fixture; no exact secret | T0010 |
| apps/web/app/(consumer)/you/page.tsx | remove fabricated profile; gate QR | T0205-T0208 |
| apps/web/app/visits/[visitId]/page.tsx | remove fallback and local false-success | T0209-T0213 |
| apps/web/app/visits/visits-page.test.tsx | assert fail-closed | T0214 |
| apps/web/components/clinical/patient-roster.tsx | API roster, no INITIAL queue | T0215-T0218 |
| apps/mobile/lib/experience/unified/clinical_overview_surface.dart | API roster/readiness | T0302-T0308 |
| apps/web/lib/admin-users.ts | authoritative endpoints only | T0219-T0222 |
| apps/web/lib/admin-users.test.ts | fault/OCC/RBAC tests | T0223 |
| apps/web/lib/experiments.ts | authoritative endpoints only | T0224-T0226 |
| apps/web/lib/experiments.test.ts | remove offline fake expectations | T0227 |
| apps/web/lib/clinical-feedback.ts | authoritative feedback | T0228-T0229 |
| apps/web/lib/platform-analytics.ts | real metrics/no-data/incomplete audit | T0231-T0235 |
| apps/web/components/clinical/clinical-overview-launchpad.tsx | no hardcoded Verified/Safe | T0236-T0238 |
| apps/web/scripts/check-route-layout-registry.mjs | filesystem denominator | T0401-T0409 |
| apps/web/lib/route-layout.registry.ts | cover all actual routes | T0410-T0426 |
| CLARA_Care_All_Pages_UIUX_Master_Spec_v5.md | correct denominator/derived matrix | T0426 |
| apps/web/styles/globals.css | single generated token import | T0432 |
| token sources | canonical graph/generation | T0428-T0434 |
| apps/web/app/chat/_v2/ChatShell.tsx | timer/listener teardown | T0436-T0444 |
| services/api/src/clara_api/api/v1/endpoints | add admin/clinical/analytics APIs | T0112-T0147 |
| services/api/src/clara_api/db/models.py | authoritative schema/versioning | T0111-T0145 |
| services/api/alembic/versions | additive migrations | T0111-T0150 |
| services/api/src/clara_api/glhs | formalized binding/partition/commit | T0501-T0545 |
| evaluation and protocols | frozen comparators/study | T0601-T0645 |
| research/claim_ledger.csv | evidence-linked claims | T0543,T0641,T0701 |

---

# 26. Acceptance scenarios

## 26.1 Scenario A — You API offline

Given:

- authenticated user;
- /api/v2/you times out.

Then:

- page renders unavailable;
- no blood type/allergy/emergency contact fabricated;
- QR cannot be generated;
- correlation ID shown;
- retry available;
- no protected old-account cache displayed.

## 26.2 Scenario B — Partial visit

Given:

- server returns visit header only;
- SOAP/meds/labs omitted.

Then:

- only header renders;
- sections say not available/not recorded;
- no fallback merge;
- verified badge absent;
- provenance matches returned fields.

## 26.3 Scenario C — Document create returns 500

Then:

- local list unchanged;
- no verified document appears;
- pending state ends;
- safe error/correlation ID shown;
- retry with same idempotency key is safe.

## 26.4 Scenario D — Admin role conflict

Given:

- page holds version v1;
- another admin updates to v2;
- first admin submits expected v1.

Then:

- server returns 409;
- client does not claim success;
- current v2 can be reviewed;
- no audit event claims rejected role change committed.

## 26.5 Scenario E — Last admin concurrency

Two admins concurrently attempt to demote/lock each other such that no active
admin would remain.

Then:

- at most one compatible mutation commits;
- invariant preserved;
- loser receives typed conflict;
- audit ordering reconstructable.

## 26.6 Scenario F — Empty analytics database

Then:

- has_data=false;
- all undefined KPIs null/empty;
- no generated trends;
- no zero-PII pass absent receipt;
- UI explains no data, not zero activity.

## 26.7 Scenario G — Readiness dependency down

When medication KB check times out:

- aggregate is unavailable/degraded;
- Safe/Verified/Synced not shown;
- DDI-dependent action blocked;
- last known value, if displayed, is stale/read-only with timestamp.

## 26.8 Scenario H — Route added

Developer adds apps/web/app/new-surface/page.tsx without registry entry.

Then:

- route layout CI fails;
- denominator auto-increments;
- report lists /new-surface;
- no hardcoded count update can bypass.

## 26.9 Scenario I — GLHS dependent race

Proposal binds medication partition version 7. Another transaction changes it to
8 before commit.

Then:

- commit locks and re-reads;
- proposal aborts stale;
- no clinical transition;
- rejection audit exists;
- retry requires new disclosure/binding.

## 26.10 Scenario J — GLHS independent race

Proposal depends only on allergy partition. Concurrent measurement write changes
measurement partition.

Then:

- valid proposal may commit if all other predicates pass;
- no false-stale from global version;
- audit records both orders.

---

# 27. Observability, SLO and alerting

## 27.1 Suggested SLOs requiring final approval

| Capability | Indicator | Initial target |
|---|---|---|
| Critical mutation correctness | false-success rate | 0 |
| Clinical fabricated data | detected occurrence | 0 |
| Emergency-card invalid issuance | count | 0 |
| Session revoke propagation | p99 | defined by security policy |
| Admin mutation API | availability | 99.9% excluding planned |
| Roster read | p95 latency | measured before target freeze |
| GLHS invalid commit | acceptance | 0 in covered model |
| GLHS valid operation | noninferiority | prespecified margin |
| Audit reconstruction | eligible committed ops | 100% |
| Route coverage | actual pages | 100% |

Do not freeze arbitrary latency values until baseline is measured.

## 27.2 Alerts

Immediate P0 alerts:

- verified status without receipt;
- emergency QR issued with failed eligibility;
- role mutation response without audit_event_id;
- success UI telemetry paired with server failure;
- secret scanner hit;
- GLHS invalid commit;
- audit/commit mismatch.

P1 alerts:

- readiness stale beyond budget;
- route inventory drift;
- token generation drift;
- unhandled frontend error;
- test flake above zero for mandatory gates.

## 27.3 Privacy

Metrics use opaque IDs/counts. Never log:

- names/emails;
- MRNs;
- raw clinical narratives;
- queries;
- drug lists;
- QR payloads;
- access/refresh tokens;
- secrets.

---

# 28. Rollout and rollback

## 28.1 Deployment waves

1. infrastructure/schema additive migration;
2. backend endpoints dark-launched;
3. shadow/read validation with synthetic non-PHI;
4. Web internal staging;
5. Mobile internal staging;
6. canary tenant;
7. limited percentage;
8. full rollout.

## 28.2 Feature flags

Allowed:

- route UI migration;
- new admin workbench read views;
- new analytics rendering.

Not allowed to disable:

- RBAC;
- consent;
- CSRF;
- FIDES critical block;
- emergency fast-path;
- legal hard-guard;
- GLHS required binding on governed path;
- audit.

## 28.3 Rollback

Rollback plan includes:

- backward-compatible DB migration;
- old client compatibility window;
- ability to turn off new UI without enabling fake fallback;
- no rollback to exposed credential;
- preserve audit/event ordering;
- replay-safe idempotency;
- mobile version skew.

Rollback drill must be executed in staging and captured.

---

# 29. Risk register / FMEA

| ID | Failure mode | Sev | Likelihood | Detectability | Mitigation |
|---|---:|---:|---:|---:|---|
| R-01 | Fake clinical fallback survives renamed | 10 | 5 | 4 | AST/dependency/bundle scan |
| R-02 | Secret remains in old ref/image | 10 | 6 | 5 | all-ref/layer scan + revoke |
| R-03 | UI reports admin success on timeout | 9 | 6 | 4 | mutation controller + chaos |
| R-04 | Last admin invariant race | 9 | 3 | 6 | DB transaction/concurrency test |
| R-05 | Route checker keeps circular denominator | 6 | 7 | 3 | filesystem generator/canary |
| R-06 | Unknown readiness shown safe | 10 | 5 | 4 | typed state/property tests |
| R-07 | Partial API response gets default merge | 9 | 5 | 5 | schema/state negative tests |
| R-08 | Mobile stale response crosses account | 10 | 3 | 7 | cancellation/session generation |
| R-09 | Token legacy override reappears | 5 | 5 | 3 | duplicate/hash CI |
| R-10 | Full test false-positive | 7 | 6 | 4 | exit/unhandled hard gate |
| R-11 | GLHS dependency set omits conflict | 10 | 4 | 8 | conservative fallback/proof |
| R-12 | GLHS deadlock | 8 | 4 | 5 | total lock order/load tests |
| R-13 | Retry double-commits | 9 | 4 | 6 | idempotency/crash tests |
| R-14 | Comparator not faithful | 8 | 6 | 7 | artifact/fidelity review |
| R-15 | Final holdout leakage | 9 | 3 | 8 | source/template disjoint audit |
| R-16 | Provider fallback wrong model | 7 | 5 | 6 | identity receipt, retain failure |
| R-17 | Synthetic result called clinical | 8 | 5 | 3 | claim ledger validator |
| R-18 | Bounded proof marketed universal | 7 | 5 | 3 | scope text validator/review |
| R-19 | Independent review falsely claimed | 8 | 3 | 5 | reviewer receipts |
| R-20 | Paid eval run without approval | 6 | 3 | 3 | explicit authority gate |

Risk score and owner must be maintained in machine-readable registry.

---

# 30. Architecture decision records required

| ADR | Decision |
|---|---|
| ADR-001 | Authority envelope and state semantics |
| ADR-002 | Production/demo/test isolation |
| ADR-003 | Critical mutation pessimistic display semantics |
| ADR-004 | Admin user domain and last-admin invariant |
| ADR-005 | Experiment kill/reactivation governance |
| ADR-006 | Visit verification lifecycle |
| ADR-007 | Emergency QR signing/revocation |
| ADR-008 | Analytics metric provenance |
| ADR-009 | Route filesystem denominator |
| ADR-010 | Canonical design-token source |
| ADR-011 | GLHS partition dependency model |
| ADR-012 | GLHS lock order/isolation level |
| ADR-013 | Canonical JSON/hash domain separation |
| ADR-014 | Audit outbox atomicity |
| ADR-015 | Evaluation comparator fidelity |
| ADR-016 | Confirmatory freeze/invalidation |

Each ADR includes context, alternatives, threat tradeoffs, decision, consequences,
migration, rollback and review date.

---

# 31. Definition of Done

## 31.1 Security

- [ ] Exposed credential revoked.
- [ ] Rotated secret stored/injected correctly.
- [ ] Old credential confirmed unusable.
- [ ] Working tree scan clean.
- [ ] Reachable history scan clean in approved scope.
- [ ] Docker/artifact scan clean.
- [ ] No secret value in tests/docs/logs.
- [ ] Incident review signed.

## 31.2 Data truth

- [ ] No production clinical fixture fallback.
- [ ] No production admin seed authority.
- [ ] No synthetic analytics fallback.
- [ ] No success-after-catch.
- [ ] No verified/safe/synced without receipt.
- [ ] Empty/unavailable/degraded/stale distinct.
- [ ] Production bundle fixture scan clean.

## 31.3 Backend

- [ ] Required authoritative endpoints exist.
- [ ] Migrations pass clean upgrade.
- [ ] RBAC/CSRF/consent enforced.
- [ ] OCC and idempotency pass races/retries.
- [ ] Audit outbox atomic.
- [ ] Read-after-write/reconciliation verified.
- [ ] OpenAPI compatibility pass.

## 31.4 Web

- [ ] You/Emergency QR fail-closed.
- [ ] Visit detail/mutations authoritative.
- [ ] Patient roster authoritative.
- [ ] Admin users/experiments/feedback authoritative.
- [ ] Analytics/readiness truthful.
- [ ] Node 20 toolchain.
- [ ] Full test exit 0.
- [ ] Unhandled errors 0.
- [ ] Build/lint/type/E2E/a11y pass.

## 31.5 Mobile

- [ ] Static queue removed.
- [ ] Hardcoded Verified removed.
- [ ] Offline/account-switch states safe.
- [ ] Flutter analyze/test/integration pass.
- [ ] Production binary fixture scan clean.

## 31.6 Governance

- [ ] Route denominator generated from filesystem.
- [ ] Every actual route registered.
- [ ] Broken links/aliases 0.
- [ ] Canonical token graph.
- [ ] Duplicate semantic override 0.
- [ ] Evidence manifests same release SHA.
- [ ] GitHub required checks present and green.

## 31.7 GLHS

- [ ] Threat/assumption model frozen.
- [ ] Canonicalization specified/tested cross-language.
- [ ] All writers audited.
- [ ] Proof obligations scoped and addressed.
- [ ] TLA+/bounded model result sealed.
- [ ] Real PostgreSQL race schedules sealed.
- [ ] False-stale/scaling measured.
- [ ] Audit reconstruction complete for eligible denominator.
- [ ] Limitations explicit.

## 31.8 Research

- [ ] Closest work verified from primary sources.
- [ ] Two top competitors identified or honestly asset-gated.
- [ ] Required internal baselines implemented.
- [ ] Protocol/SAP/cohort/oracle/prompts sealed before run.
- [ ] Provider-cost authority obtained.
- [ ] All 384 subjects retained if that design is frozen.
- [ ] Errors/malformed/wrong-model retained.
- [ ] Primary and noninferiority analyses locked.
- [ ] Human review actually completed before claim.
- [ ] Independent replay completed.
- [ ] Claim ledger/manuscript/release synchronized.

## 31.9 Release

- [ ] P0 open count = 0.
- [ ] P1 open count = 0.
- [ ] No mandatory NOT_RUN.
- [ ] No flaky mandatory gate.
- [ ] Security sign-off.
- [ ] Clinical sign-off.
- [ ] Privacy/legal sign-off.
- [ ] Research integrity sign-off.
- [ ] Rollback drill pass.
- [ ] Release captain GO.

---

# 32. 10/10 rubric

| Dimension | Weight | 10/10 condition |
|---|---:|---|
| Security | 10 | secret incident closed; scans/revocation proven |
| Clinical data truth | 15 | zero fabricated/fail-open paths under fault injection |
| Backend correctness | 10 | authoritative APIs, transactions, audit, race tests |
| Web/Mobile correctness | 10 | full gates clean, no false-success |
| Route/design governance | 5 | actual denominator 100%, canonical tokens |
| GLHS novelty | 10 | independently defensible delta over verified closest work |
| Formal depth | 10 | scoped proof obligations + model/DB evidence |
| Baselines | 10 | faithful direct same-task comparisons |
| Experimental rigor | 10 | frozen one-shot study, stats, noninferiority, full errors |
| Reproducibility/claims | 10 | independent replay and exact claim ledger |

Hard cap rules:

- open P0 => maximum 3/10;
- fabricated clinical data => maximum 2/10;
- active secret exposure => maximum 2/10;
- false-success security mutation => maximum 3/10;
- no direct baseline => novelty/evaluation dimension maximum 4/10;
- no fresh sealed confirmatory run => overall maximum 7/10 for A* readiness;
- synthetic-only evidence => no clinical efficacy claim;
- any denominator laundering => reproducibility/claims maximum 2/10.

Acceptance at a conference is never guaranteed by rubric score.

---

# Appendix A — Pull request template

~~~markdown
## Requirement IDs

## Threat/failure scenario

## Implementation

## Negative behavior removed

## Tests run

| Command | Exit | Artifact |
|---|---:|---|

## Evidence

- Commit SHA:
- Dirty:
- Environment digest:
- CI run:
- Artifact hashes:
- Unhandled errors:
- Skips/NOT_RUN:

## Data/clinical/security review

## Rollout

## Rollback

## Claim impact

No claim changes / exact claim ledger entries:
~~~

---

# Appendix B — Evidence receipt schema

~~~json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CLARA Evidence Receipt",
  "type": "object",
  "required": [
    "id",
    "requirement_ids",
    "commit_sha",
    "dirty",
    "command",
    "exit_code",
    "started_at",
    "ended_at",
    "environment_digest",
    "artifacts"
  ],
  "properties": {
    "id": { "type": "string" },
    "requirement_ids": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 1
    },
    "commit_sha": {
      "type": "string",
      "pattern": "^[0-9a-f]{40}$"
    },
    "dirty": { "type": "boolean", "const": false },
    "command": { "type": "string" },
    "exit_code": { "type": "integer", "const": 0 },
    "started_at": { "type": "string", "format": "date-time" },
    "ended_at": { "type": "string", "format": "date-time" },
    "environment_digest": { "type": "string" },
    "ci_run_url": { "type": ["string", "null"] },
    "counts": {
      "type": "object",
      "properties": {
        "passed": { "type": "integer", "minimum": 0 },
        "failed": { "type": "integer", "const": 0 },
        "skipped": { "type": "integer", "minimum": 0 },
        "unhandled_errors": { "type": "integer", "const": 0 }
      }
    },
    "artifacts": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["path", "sha256"],
        "properties": {
          "path": { "type": "string" },
          "sha256": {
            "type": "string",
            "pattern": "^[0-9a-f]{64}$"
          }
        }
      }
    },
    "not_run": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["gate", "reason"],
        "properties": {
          "gate": { "type": "string" },
          "reason": { "type": "string" },
          "authority_needed": { "type": ["string", "null"] }
        }
      }
    }
  }
}
~~~

---

# Appendix C — Claim ledger schema

| Field | Meaning |
|---|---|
| claim_id | stable ID |
| exact_text | exact public/manuscript claim |
| scope | task/dataset/model/comparator |
| claim_type | descriptive/exploratory/confirmatory/clinical |
| denominator | exact N and unit |
| evidence_ids | sealed receipts |
| analysis_id | immutable analysis |
| status | supported/partial/not_run/contradicted |
| limitations | mandatory |
| first_supported_sha | exact SHA |
| current_sha_verified | exact SHA |
| owner | responsible author |

Validator rules:

- no supported claim without evidence;
- no “all” unless exhaustive set defined;
- no percentage without numerator/denominator;
- no model claim without exact model/provider identity;
- no clinical label for synthetic-only evidence;
- no 100% if failures/skips/unhandled are outside stated scope.

---

# Appendix D — Review checklists

## D.1 Security reviewer

- Is any secret value present in diff/history/artifact?
- Does server enforce RBAC, not UI?
- Does CSRF cover cookie mutation?
- Can attacker perform IDOR/cross-subject access?
- Are sessions invalidated after role/lock/revoke?
- Can retry double-commit?
- Does audit avoid PHI/secret?
- Can last admin be removed through race?

## D.2 Clinical safety reviewer

- Can missing data appear known?
- Can unavailable appear safe?
- Can partial data be filled from default?
- Can QR be issued for wrong/stale subject?
- Can document become verified without verifier?
- Are emergency and FIDES invariants preserved?
- Does copy overstate certainty?
- Are provenance/freshness visible where needed?

## D.3 A* PC mock reviewer

- What is the one novel technical object?
- Which closest papers already solve most of it?
- Is this just known DB transactions + Merkle hash + consent?
- What theorem is new and nontrivial?
- Are assumptions realistic?
- Does every writer pass through the gate?
- Are baselines faithful and current?
- Are tasks/budgets identical?
- Is N independent?
- Were errors retained?
- Is noninferiority shown?
- Are results synthetic only?
- Can artifacts be reproduced?
- Are nulls and mismatches preserved?

---

# Appendix E — Required negative tests catalog

## E.1 Data truth

1. You fetch timeout produces no profile.
2. You 500 produces no blood type.
3. You partial response does not add allergy.
4. Old cached account does not display after login switch.
5. Emergency QR missing consent is blocked.
6. Emergency QR stale field is blocked.
7. Visit 404 produces no default visit.
8. Visit 500 produces no SOAP.
9. Partial visit produces no medications not returned.
10. Partial visit produces no verified badge.
11. Roster offline produces no patients.
12. Mobile roster offline produces no patients.
13. Readiness timeout produces no Safe label.
14. Missing privacy receipt produces no pass label.
15. Empty DB produces no synthetic trend.

## E.2 Mutation truth

1. Role change 500 leaves role unchanged.
2. Role change timeout leaves role unchanged.
3. Role change 409 shows conflict.
4. Lock 500 leaves lock state unchanged.
5. Revoke 500 does not claim sessions revoked.
6. Experiment rollout 500 leaves rollout unchanged.
7. Kill timeout does not render killed until reconciliation.
8. Feedback update 500 leaves status unchanged.
9. Scribe consent 500 leaves consent unchanged.
10. Document create 500 adds no local record.
11. Document delete 500 keeps record.
12. Duplicate idempotency key commits once.
13. Lost response after commit reconciles without duplicate.

## E.3 Security

1. Non-admin gets 403 for every admin endpoint.
2. Doctor cannot mutate admin users.
3. Admin preview cannot impersonate.
4. Cookie mutation without CSRF fails.
5. Bearer scope mismatch fails.
6. Cross-tenant user ID fails.
7. Cross-subject patient ID fails.
8. Last admin demotion fails.
9. Concurrent last-admin operations preserve one active admin.
10. Logs redact planted secret.
11. Built image containing planted secret fails CI.
12. Old revoked session cannot act.

## E.4 GLHS

1. Dependent version change aborts.
2. Consent revoke aborts.
3. Policy change aborts.
4. Expired binding aborts.
5. Wrong subject aborts.
6. Wrong actor/purpose/task aborts.
7. Tampered manifest aborts.
8. Duplicate JSON key rejected.
9. Root lineage laundering rejected.
10. Derived cache after revocation rejected.
11. Independent partition write does not false-reject.
12. Same idempotency retry commits once.
13. Crash before commit creates no commit audit.
14. Crash after commit reconstructs committed result.
15. Deadlock retry does not bypass predicates.

---

# Appendix F — Final ruthless verdict

At SHA 5ffbe362, CLARA-Care is not release-ready and not A*-ready. The core issue
is not thiếu polish; it is a mismatch between presentation and authority:
production surfaces fabricate clinical/admin/analytics state, security-critical
mutations can report false success, a credential remains embedded, and evidence
claims use incomplete or circular denominators.

The path to a credible top-tier result is therefore:

1. restore truth and security first;
2. make server transactions authoritative;
3. prove fail-closed behavior under faults and races;
4. repair route/test/release evidence;
5. formalize GLHS as a scoped protocol;
6. compare it fairly against verified closest work;
7. accept whatever the frozen data says.

If the final experiment does not show superiority, the correct outcome is an
honest negative or scoped systems paper—not tuning until 10/10. That constraint
is part of the technical design, not an optional publication preference.
