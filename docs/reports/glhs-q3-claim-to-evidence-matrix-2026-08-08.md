# GLHS Q3 — ma trận claim–evidence và audit giới hạn

Ngày khóa artefact: 2026-08-08
Artefact: `artifacts/glhs-q3/2026-08-08-v2/`
Summary SHA-256: `8f200a8ffa0c1b3c7b6dacf48e85c679987d68991d7430e53d92e55904b9e81c`

Protocol v3 có thêm run MIMIC-IV Demo, MIMIC-IV-ED Demo và Synthea FHIR STU3 tách cohort; xem
[`glhs-q3-external-cohort-run-2026-08-08.md`](glhs-q3-external-cohort-run-2026-08-08.md).
Hai run này là development structural cohort và đều `final_score_released=false`;
chúng không thay thế hay nâng cấp artifact v2 thành external validation.

## Phạm vi

Đây là báo cáo về **conformance cấu trúc phần mềm** của GLHS trên lịch sử
synthetic có oracle do developer viết. Nó không phải validation lâm sàng, không
gọi LLM/provider, không dùng dữ liệu bệnh nhân, không có reviewer độc lập và
không chứng minh utility/độ an toàn trong vận hành. Mọi số dưới đây phải luôn
được đọc cùng `evidence-manifest.json` trong cùng thư mục artefact.

## Claim-to-evidence matrix

| Claim/Research question | Evidence hiện có | Kết luận được phép | Không được kết luận | Trạng thái manuscript |
|---|---|---|---|---|
| RQ1 — GLHS/GST xử lý lịch sử không theo “newest row wins” | 300 case/150 subject synthetic; six structural comparators; MIMIC Demo/ED và Synthea STU3 structural-development cohorts; case/outcome CSV; exact paired test | Các luật được mô hình hoá trong runner phân biệt được late evidence/conflict/direct write theo oracle khai báo trước. | GLHS chính xác lâm sàng, tốt hơn hệ thống PHR/RAG thực tế, hay giảm sai sót người dùng. | Chỉ Methods/Results structural, không dùng Abstract/Conclusion để claim clinical. |
| RQ2 — THSS tối thiểu hoá context khi giữ authorization cố định | 4 profile THSS, 250 authorized synthetic case; unauthorized disclosure `0/300` ở mỗi profile | Trong **mô hình synthetic này**, authorization giữ cố định và disclosure nonessential giảm theo budget; critical fact oracle vẫn được chọn. | Privacy thực tế, không rò rỉ PII ở production, hoặc không có trade-off utility. | Được báo là ablation structural, kèm denominator. |
| RQ3 — DDI/CareGuard | DrugBank runtime conformance riêng và fixture nội bộ; không có final independent DDI set | Có artifact/license/runtime conformance theo tài liệu DrugBank riêng. | Sensitivity, specificity, clinical DDI safety, coverage brand-name tiếng Việt. | `not measured` cho performance claim. |
| RQ4 — Retrieval/hybrid/rerank/GraphRAG/citation verification | Không có corpus/query/reference labels locked độc lập trong Q3 v2 | Có thể mô tả pipeline/guard được implement nếu source/test chứng minh. | Precision@k, nDCG, citation grounding, superiority. | `not measured`. |
| RQ5 — Council/Chat personalised intelligence | THSS compiler và consumer subset đã được audit; Council/Chat không được phép tự dùng PHR JSON | Boundary được thiết kế để personalisation tương lai phải qua THSS. | Advice quality, personalised benefit, safe reasoning, Việt ngữ generalisation. | `not measured`; mô tả architecture only. |
| RQ6 — Scribe/Visits/Families/Connected workflow | Contract/source tests, no participants or gold transcript | Một số state/provenance seam được implement và regression-test. Visit document/Scribe note được liên kết chỉ tạo evidence-availability assertion, không tự diễn giải transcript/SOAP thành clinical fact. | SOAP fidelity, WER, clinician time, cross-profile safety at scale, usability. | `not measured`. |
| RQ7 — rebuild/reconstruction/scalability | 50 pure-Python samples tại depths 10/50/100/250; raw `scalability.csv` | Đo operation timing của **mô phỏng Python** và oracle rebuild property. | PostgreSQL/Redis/Neo4j/Milvus/ES latency, browser/API latency, cost, LLM latency, capacity. | Có thể đưa Appendix structural; không gọi production benchmark. |

## Kết quả lịch sử có thể tái lập của Q3 v2 — không phải benchmark score

Artifact v2 bên dưới được giữ nguyên để bảo toàn traceability, nhưng không còn
được phép dùng làm “điểm benchmark” hay bằng chứng superiority. `glhs_full`
là reference-policy cùng luật đã dùng để tạo oracle developer; vì vậy 300/300
là conformance mong đợi của mô hình tham chiếu, không phải kết quả đánh giá một
triển khai độc lập. Protocol v3 bổ sung baseline temporal/provenance, cohort
tách riêng và gate sealed holdout trước khi bất cứ final score nào được phát
hành.

| System model | State correct | Wilson 95% CI | Diễn giải hợp lệ |
|---|---:|---:|---|
| `lww` | 100/300 | 0.282–0.388 | Mô hình last-write-wins khai báo trước trong runner. |
| `naive_rag` | 100/300 | 0.282–0.388 | Mô hình retrieval-recency khai báo trước trong runner. |
| `glhs_full` | 300/300 | 0.987–1.000 | Full structural rule implementation model khớp oracle developer-authored. |
| `glhs_no_thss` | 300/300 | 0.987–1.000 | State selection không thay đổi; THSS ablation đo minimisation riêng. |
| `glhs_no_gst` | 100/300 | 0.282–0.388 | Mô hình direct mutation khai báo trước trong runner. |

Paired `glhs_full` vs LWW/naive-RAG/no-GST có 200 discordant case và McNemar
exact raw `p=1.2446e-60`, Holm-adjusted `p=4.9784e-60`; vs `glhs_no_thss` có
0 discordant case và adjusted `p=1.0`. Đây là suy luận nội bộ trên **oracle và
output do cùng protocol quy định**, không phải bằng chứng superiority độc lập.

## Điều kiện tái lập

```bash
services/api/.venv/bin/python -m pytest -q evaluation/glhs_q3/test_run.py
services/api/.venv/bin/ruff check evaluation/glhs_q3/run.py evaluation/glhs_q3/test_run.py
python3 -m evaluation.glhs_q3.run --output artifacts/glhs-q3/2026-08-08-v2
```

Runner ghi code revision, SHA-256 runner/gateway/adapter/model/migration,
environment chuẩn thư viện Python và artifact list trong `evidence-manifest.json`.
Không thay `latest/` cho một output frozen đã được trích dẫn.

## Hạn chế chưa được giải quyết trước journal submission

1. Không có test set external/independent, patient cohort, prospective,
   multi-institutional, clinician-led hoặc usability evaluation.
2. Oracle, comparator outcome và case source đều developer-authored; không có
   blind adjudication hay leakage audit độc lập.
3. Các cohort de-identified/structural-development đã được chạy, gồm MIMIC-IV
   Demo, MIMIC-IV-ED Demo và Synthea FHIR STU3; không cohort nào là sealed
   holdout hoặc external clinical validation. Runner v3 nhận riêng MIMIC-IV
   Demo, MIMIC-IV-ED Demo, MIMIC-IV on FHIR Demo hoặc Synthea FHIR R4/STU3 qua
   manifest checksum-locked; một final score đòi hỏi
   `partition=sealed_holdout`, oracle/development hash, freeze metadata và
   curator independence attestation. Nó không thể tự xác thực độc lập claim
   của curator, nên còn cần governance review. Full MIMIC credentialed không
   được runner tự truy cập.
4. Không có retrieval/citation/DDI/Scribe gold set độc lập, subgroup tiếng Việt,
   calibration, cost, provider/model trace hay repeated stochastic model run.
5. Timing chỉ là pure-Python simulation; không bao gồm database, queue,
   rebuild backend, external dependency, network, browser hay LLM.
6. Các contract tests không thay thế penetration test, prompt-injection test,
   privacy leakage test tại scale hay independent security/clinical review.
7. Chưa được phép kết luận clinical efficacy, diagnostic improvement, reduced
   adverse events, time/cost savings, operational readiness hoặc scalability.

## Bảng báo cáo cho IEEE

Nếu dùng artifact này trong manuscript, đặt nó trong mục “software structural
evaluation” hoặc appendix, giữ nguyên nhãn `synthetic/developer-authored`, và
liệt kê raw numerator/denominator. Abstract, title, conclusion và future-work
không được biến các kết quả này thành claim clinical/real-world. Các RQ không
có evidence độc lập phải ghi rõ **not measured**, không thay bằng phần trăm từ
unit test hay fixture integrity.
