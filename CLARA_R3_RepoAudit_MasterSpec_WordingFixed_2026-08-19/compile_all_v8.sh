#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

mkdir -p PDF_SUBMISSION_V8 PDF_VIETNAMESE_V8

echo "=== Compiling 11 English Manuscripts ==="

# 1. GLHS Journal
echo "--- 01_GLHS_Journal ---"
(cd SOURCE_SUBMISSION/JOURNAL/GLHS_Journal_Revision && pdflatex -interaction=nonstopmode main.tex && pdflatex -interaction=nonstopmode main.tex && cp main.pdf "$ROOT_DIR/PDF_SUBMISSION_V8/01_GLHS_Journal_v8.pdf")

# 2. GovRed RIVF
echo "--- 02_GovRed_RIVF ---"
(cd SOURCE_SUBMISSION/VN/RIVF2026_GovRed && pdflatex -interaction=nonstopmode main.tex && pdflatex -interaction=nonstopmode main.tex && cp main.pdf "$ROOT_DIR/PDF_SUBMISSION_V8/02_GovRed_RIVF_v8.pdf")

# 3. GovMut SOICT
echo "--- 03_GovMut_SOICT ---"
(cd SOURCE_SUBMISSION/VN/SOICT2026_GovMut && pdflatex -interaction=nonstopmode main.tex && pdflatex -interaction=nonstopmode main.tex && cp main.pdf "$ROOT_DIR/PDF_SUBMISSION_V8/03_GovMut_SOICT_v8.pdf")

# 4. FMC VI
echo "--- 04_FMC2026_VI ---"
(cd SOURCE_SUBMISSION/VN/FMC2026 && xelatex -interaction=nonstopmode abstract_vi.tex && xelatex -interaction=nonstopmode abstract_vi.tex && cp abstract_vi.pdf "$ROOT_DIR/PDF_SUBMISSION_V8/04_FMC2026_VI_v8.pdf")

# 5. FMC EN
echo "--- 05_FMC2026_EN ---"
(cd SOURCE_SUBMISSION/VN/FMC2026 && pdflatex -interaction=nonstopmode abstract_en.tex && pdflatex -interaction=nonstopmode abstract_en.tex && cp abstract_en.pdf "$ROOT_DIR/PDF_SUBMISSION_V8/05_FMC2026_EN_v8.pdf")

# 6. CareGuard VN
echo "--- 06_CareGuard_VN ---"
(cd SOURCE_SUBMISSION/VN/CareGuard_VN && pdflatex -interaction=nonstopmode main.tex && pdflatex -interaction=nonstopmode main.tex && cp main.pdf "$ROOT_DIR/PDF_SUBMISSION_V8/06_CareGuard_v8.pdf")

# 7. GLHS AMIA HSS
echo "--- 07_GLHS_AMIA_HSS ---"
(cd SOURCE_SUBMISSION/US/AMIA_HSS_2026_GLHS && pdflatex -interaction=nonstopmode GLHS_AMIA_HSS_2026_Extended_Abstract.tex && pdflatex -interaction=nonstopmode GLHS_AMIA_HSS_2026_Extended_Abstract.tex && cp GLHS_AMIA_HSS_2026_Extended_Abstract.pdf "$ROOT_DIR/PDF_SUBMISSION_V8/07_GLHS_AMIA_HSS_v8.pdf")

# 8. GovRed IEEE
echo "--- 08_GovRed_IEEE ---"
(cd SOURCE_SUBMISSION/US/IEEE_BigData_Healthcare_2026_GovRed && pdflatex -interaction=nonstopmode GovRed_Health_IEEE_BigData_Healthcare_2026.tex && pdflatex -interaction=nonstopmode GovRed_Health_IEEE_BigData_Healthcare_2026.tex && cp GovRed_Health_IEEE_BigData_Healthcare_2026.pdf "$ROOT_DIR/PDF_SUBMISSION_V8/08_GovRed_IEEE_v8.pdf")

# 9. CLARACare FHIR
echo "--- 09_CLARACare_FHIR ---"
(cd SOURCE_SUBMISSION/US/AMIA_FHIR_App_2026_CLARACare && pdflatex -interaction=nonstopmode CLARACare_AMIA_HL7_FHIR_App_Application.tex && pdflatex -interaction=nonstopmode CLARACare_AMIA_HL7_FHIR_App_Application.tex && cp CLARACare_AMIA_HL7_FHIR_App_Application.pdf "$ROOT_DIR/PDF_SUBMISSION_V8/09_CLARACare_FHIR_v8.pdf")

# 10. CLARACare Amplify
echo "--- 10_CLARACare_Amplify ---"
(cd SOURCE_SUBMISSION/US/AMIA_Amplify_2027_CLARACare_SystemDemo && pdflatex -interaction=nonstopmode CLARACare_AMIA_Amplify_2027_System_Demonstration.tex && pdflatex -interaction=nonstopmode CLARACare_AMIA_Amplify_2027_System_Demonstration.tex && cp CLARACare_AMIA_Amplify_2027_System_Demonstration.pdf "$ROOT_DIR/PDF_SUBMISSION_V8/10_CLARACare_Amplify_v8.pdf")

# 11. GovMut IEEE
echo "--- 11_GovMut_IEEE ---"
(cd SOURCE_SUBMISSION/US/IEEE_BigData_ML_2026_GovMut && pdflatex -interaction=nonstopmode GovMut_Health_IEEE_BigData_ML_2026.tex && pdflatex -interaction=nonstopmode GovMut_Health_IEEE_BigData_ML_2026.tex && cp GovMut_Health_IEEE_BigData_ML_2026.pdf "$ROOT_DIR/PDF_SUBMISSION_V8/11_GovMut_IEEE_v8.pdf")


echo "=== Compiling 11 Vietnamese Companion Manuscripts ==="

# 1. VI GLHS Journal
echo "--- VI 01_GLHS_Journal ---"
(cd SOURCE_VIETNAMESE/01_GLHS_Journal && xelatex -interaction=nonstopmode main_vi.tex && xelatex -interaction=nonstopmode main_vi.tex && cp main_vi.pdf "$ROOT_DIR/PDF_VIETNAMESE_V8/01_GLHS_Journal_VI_v8.pdf")

# 2. VI GovRed RIVF
echo "--- VI 02_GovRed_RIVF ---"
(cd SOURCE_VIETNAMESE/02_GovRed_RIVF && xelatex -interaction=nonstopmode main_vi.tex && xelatex -interaction=nonstopmode main_vi.tex && cp main_vi.pdf "$ROOT_DIR/PDF_VIETNAMESE_V8/02_GovRed_RIVF_VI_v8.pdf")

# 3. VI GovMut SOICT
echo "--- VI 03_GovMut_SOICT ---"
(cd SOURCE_VIETNAMESE/03_GovMut_SOICT && xelatex -interaction=nonstopmode main_vi.tex && xelatex -interaction=nonstopmode main_vi.tex && cp main_vi.pdf "$ROOT_DIR/PDF_VIETNAMESE_V8/03_GovMut_SOICT_VI_v8.pdf")

# 4. VI FMC VI Companion
echo "--- VI 04_FMC_VI ---"
(cd SOURCE_VIETNAMESE/04_FMC_VI && xelatex -interaction=nonstopmode main_vi.tex && xelatex -interaction=nonstopmode main_vi.tex && cp main_vi.pdf "$ROOT_DIR/PDF_VIETNAMESE_V8/04_FMC2026_VI_Companion_v8.pdf")

# 5. VI FMC EN Companion
echo "--- VI 05_FMC_EN_VI ---"
(cd SOURCE_VIETNAMESE/05_FMC_EN_VI && xelatex -interaction=nonstopmode main_vi.tex && xelatex -interaction=nonstopmode main_vi.tex && cp main_vi.pdf "$ROOT_DIR/PDF_VIETNAMESE_V8/05_FMC2026_EN_VI_Companion_v8.pdf")

# 6. VI CareGuard VN
echo "--- VI 06_CareGuard_VN ---"
(cd SOURCE_VIETNAMESE/06_CareGuard_VN && xelatex -interaction=nonstopmode main_vi.tex && xelatex -interaction=nonstopmode main_vi.tex && cp main_vi.pdf "$ROOT_DIR/PDF_VIETNAMESE_V8/06_CareGuard_VI_v8.pdf")

# 7. VI GLHS AMIA HSS
echo "--- VI 07_GLHS_AMIA_HSS ---"
(cd SOURCE_VIETNAMESE/07_GLHS_AMIA_HSS && xelatex -interaction=nonstopmode main_vi.tex && xelatex -interaction=nonstopmode main_vi.tex && cp main_vi.pdf "$ROOT_DIR/PDF_VIETNAMESE_V8/07_GLHS_AMIA_HSS_VI_v8.pdf")

# 8. VI GovRed IEEE
echo "--- VI 08_GovRed_IEEE ---"
(cd SOURCE_VIETNAMESE/08_GovRed_IEEE && xelatex -interaction=nonstopmode main_vi.tex && xelatex -interaction=nonstopmode main_vi.tex && cp main_vi.pdf "$ROOT_DIR/PDF_VIETNAMESE_V8/08_GovRed_IEEE_VI_v8.pdf")

# 9. VI CLARACare FHIR
echo "--- VI 09_CLARACare_FHIR ---"
(cd SOURCE_VIETNAMESE/09_CLARACare_FHIR && xelatex -interaction=nonstopmode main_vi.tex && xelatex -interaction=nonstopmode main_vi.tex && cp main_vi.pdf "$ROOT_DIR/PDF_VIETNAMESE_V8/09_CLARACare_FHIR_VI_v8.pdf")

# 10. VI CLARACare Amplify
echo "--- VI 10_CLARACare_Amplify ---"
(cd SOURCE_VIETNAMESE/10_CLARACare_Amplify && xelatex -interaction=nonstopmode main_vi.tex && xelatex -interaction=nonstopmode main_vi.tex && cp main_vi.pdf "$ROOT_DIR/PDF_VIETNAMESE_V8/10_CLARACare_Amplify_VI_v8.pdf")

# 11. VI GovMut IEEE
echo "--- VI 11_GovMut_IEEE ---"
(cd SOURCE_VIETNAMESE/11_GovMut_IEEE && xelatex -interaction=nonstopmode main_vi.tex && xelatex -interaction=nonstopmode main_vi.tex && cp main_vi.pdf "$ROOT_DIR/PDF_VIETNAMESE_V8/11_GovMut_IEEE_VI_v8.pdf")

echo "=== All 22 Manuscripts Compiled Successfully ==="
