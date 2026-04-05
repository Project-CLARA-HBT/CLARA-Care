# Medical Safety Corpus Pack

Mục tiêu:
- Mở rộng corpus RAG theo hướng thực dụng cho câu hỏi an toàn thuốc, DDI, nhãn thuốc, cảnh báo hậu mãi và guideline chính thống.
- Chỉ đụng `docs/research/data`.
- Không thay đổi retrieval/ranking logic hiện tại.

## 1. Thành phần pack

### 1.1 Catalog nguồn
- `docs/research/data/medical-safety-corpus-sources-2026-03-31.csv`

Catalog này gom 2 nhóm nguồn:
- Việt Nam:
  - Cục Quản lý Dược
  - Trung tâm DI & ADR Quốc gia
  - Cục Quản lý Khám chữa bệnh
  - Bộ Y tế / kho tệp chuyên môn
  - Dược thư Quốc gia
- Quốc tế:
  - PubMed
  - DailyMed
  - FDA Drug Safety Communications / MedWatch
  - MedlinePlus
  - WHO Essential Medicines
  - EMA
  - MHRA
  - NHS Medicines

### 1.2 Query set cho PubMed safety
- `docs/research/data/medical-safety-pubmed-queries-2026-03-31.csv`

Query set tập trung vào:
- DDI nguy cơ cao
- Polypharmacy ở người lớn tuổi
- Tác dụng bất lợi nghiêm trọng
- Deprescribing
- Adherence liên quan safety

### 1.3 Manifest và seed artifacts
- `data/rag_seed/manifests/medical_safety_corpus_manifest.json`
- `data/rag_seed/manifests/medical_safety_registry_seed.json`
- `data/rag_seed/manifests/medical_safety_vn_pdf_catalog.csv`

## 2. Tư duy indexing

Pack này không ép tất cả nguồn thành full-text ngay.

Thay vào đó chia thành 3 lớp:
- `fulltext_seed`:
  - nguồn PDF chính thống có thể tải tương đối ổn định
  - ví dụ: KCB PDFs, DI&ADR bulletin, WHO technical PDF
- `registry_seed`:
  - nguồn cực uy tín nhưng nên index metadata/registry trước
  - ví dụ: DAV DVC tables, DailyMed, FDA safety page, EMA referrals
- `query_seed`:
  - nguồn literature dựa theo curated query set
  - hiện dùng cho PubMed

Lợi ích:
- Không cần sửa engine retrieval hiện tại.
- Có thể tăng coverage corpus ngay bằng registry seed.
- Khi crawler/fulltext ổn định hơn thì chỉ cần mở rộng ingest, không đổi contract.

## 3. Script build pack

Wrapper:
- `scripts/build_medical_safety_corpus_pack.py`

Core module:
- `scripts/rag_seed/build_medical_safety_corpus_pack.py`

### 3.1 Chế độ offline an toàn

Sinh manifest + registry seed + catalog VN tương thích script seed cũ:

```bash
python scripts/build_medical_safety_corpus_pack.py \
  --include-default-existing-seeds
```

Kết quả:
- manifest corpus pack
- registry seed docs cho toàn bộ source catalog
- filtered VN PDF catalog để dùng lại `scripts/rag_seed.py`

### 3.2 Build combined seed không đụng retrieval logic

```bash
python scripts/build_medical_safety_corpus_pack.py \
  --include-default-existing-seeds \
  --build-combined-seed
```

Script sẽ merge:
- registry seed docs mới
- `vn_medical_seed.json`
- `pubmed_authoritative_seed.json`

để tạo một combined seed artifact phục vụ indexing/offline bootstrap.

### 3.3 Build live PubMed

```bash
python scripts/build_medical_safety_corpus_pack.py \
  --build-pubmed-live \
  --pubmed-per-query 12 \
  --build-combined-seed
```

### 3.4 Build live VN PDF

```bash
python scripts/build_medical_safety_corpus_pack.py \
  --build-vn-live \
  --max-vn-docs-per-source 2 \
  --max-vn-candidate-urls-per-source 10 \
  --build-combined-seed
```

## 4. Vì sao chọn các nguồn này

### Việt Nam
- Ưu tiên nguồn quản lý và chuyên môn chính thống:
  - Bộ Y tế
  - Cục Quản lý Dược
  - Cục Quản lý Khám chữa bệnh
  - Trung tâm DI & ADR Quốc gia
- Đây là các nguồn phù hợp nhất cho:
  - cảnh báo thuốc giả / chất lượng
  - trạng thái lưu hành / OTC
  - thông tin an toàn thuốc tại Việt Nam
  - guideline lâm sàng chính thống

### Quốc tế
- Ưu tiên nguồn có provenance mạnh:
  - WHO cho normative / essential medicines
  - FDA / EMA / MHRA cho safety alert hậu mãi
  - DailyMed cho label chính thức
  - PubMed cho evidence literature
  - MedlinePlus / NHS cho lớp giải thích dễ hiểu

## 5. Nguyên tắc pháp lý và bản quyền

- Không crawl bypass auth.
- Không ingest nguồn restricted access như full-text đóng.
- Với nguồn license/availability chưa rõ:
  - seed bằng metadata/registry trước
  - chỉ full-text khi terms rõ ràng hoặc file PDF public trực tiếp
- Không coi portal form/report cá nhân là corpus ingest.

## 6. Phạm vi không làm trong pack này

- Không sửa retriever.
- Không sửa reranker.
- Không sửa scoring.
- Không sửa router.
- Không sửa prompt synthesis.

Pack này chỉ làm:
- chọn nguồn
- chuẩn hóa manifest
- chuẩn hóa query set
- tạo artifact để indexing/bootstrap corpus
