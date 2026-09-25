# CHECKPOINTS: DAY 10 - DATA PIPELINE & DATA OBSERVABILITY

> **Tổng thời lượng thực chiến:** 240 phút (4 giờ)  
> **Hình thức:** Làm việc theo nhóm (Teamwork)  
> **Bộ dữ liệu chuẩn:** Crossref Metadata API (hoặc Local Snapshot `data/raw/crossref_response.json`)  
> **Mục tiêu cốt lõi:** Xây dựng Data Pipeline hoàn chỉnh cho hệ thống RAG Agent, tích hợp Data Observability (Great Expectations 1.x + Freshness SLA), đo lường mức độ suy giảm khi dữ liệu bị lỗi (Data Corruption) và chứng minh năng lực tự phục hồi (Self-healing / Repair).

---

## Bảng Phân Bổ Thời Gian & Mục Tiêu Từng Checkpoint

| Checkpoint | Nội dung trọng tâm | Thời lượng gợi ý | Deliverables (Sản phẩm bàn giao) | Tín hiệu hoàn thành (Self-Verification) |
| :--- | :--- | :--- | :--- | :--- |
| **CP0** | Khởi tạo môi trường, cấu hình `.env`, Ingestion raw data | 0 - 30m (30') | Môi trường venv kích hoạt, file `.env` hợp lệ, 2 raw JSON artifacts | Console in `Môi trường sẵn sàng`, tải đủ 24 bài báo |
| **CP1** | Data Cleaning & Data Observability với Great Expectations 1.x & Freshness | 30m - 65m (35') | `src/ingestion/cleaning.py`, `src/observability/quality.py`, cleaned dataframe & GX suite | Clean dataframe 24 dòng có `text_for_embedding`, GX 1.x `success=True` |
| **CP2** | Benchmark Test Set & ChromaDB Vector Store Indexing | 65m - 95m (30') | `src/evaluation/testset.py`, ChromaDB collection `papers-baseline` | Sinh bộ test set (10 câu), ChromaDB index 24 docs |
| **CP3** | Baseline Pipeline End-to-End & Báo Cáo Pha 1 | 95m - 120m (25') | `script/run_phase1.py`, `baseline_metrics.json`, `phase1_report.md` | Phase 1 sinh báo cáo markdown và baseline Hit Rate |
| **CP4** | Synthetic Data Corruption Suite & Đo Lường Suy Giảm | 120m - 165m (45') | `src/ingestion/corruption.py`, `corruption_log.json`, `corrupted_metrics.json` | Tiêm 6 lỗi dữ liệu, đo lường sự sụt giảm của RAG |
| **CP5** | Idempotent Repair & Báo Cáo Đối Chiếu 3 Trạng Thái | 165m - 210m (45') | `run_corruption_flow.py`, `corruption_report.md`, `repaired_metrics.json` | Bảng so sánh 3 trạng thái: Baseline vs Corrupted vs Repaired |
| **CP6** | Live Demo Trên Bảng, Q&A & Nghiệm Thu Nộp Bài | 210m - 240m (30') | Trình diễn luồng phục hồi trực tiếp trên bảng, phản biện Q&A, nộp link LMS | Nhóm bảo vệ thành công trước lớp, 100% commit nhánh `main`, nộp link LMS |

---

## Chi Tiết Yêu Cầu Từng Checkpoint

### Checkpoint 0: Khởi tạo Môi trường & Ingestion Raw Data (30 phút)
- **Mục tiêu:** Thiết lập workspace Python chuẩn hóa (Python 3.11 - 3.13), cài đặt đầy đủ dependencies qua `uv` hoặc `pip`, thu thập dữ liệu metadata qua Crossref API và bảo toàn dữ liệu gốc.
- **Nhiệm vụ:**
  1. Tạo và kích hoạt virtual environment (`.venv`), cài đặt dependencies từ `pyproject.toml` hoặc `requirements.txt`.
  2. Tạo file `.env` từ `.env.example`, điền API Key cần thiết (`GOOGLE_API_KEY`, v.v.).
  3. Hoàn thiện hàm `parse_crossref_payload()` và logic tải trong `src/ingestion/crossref.py`, hỗ trợ cơ chế fallback đọc từ snapshot local `data/raw/crossref_response.json` khi mất mạng hoặc dính `429 Too Many Requests`.
  4. Lưu 2 file raw artifacts: `data/raw/crossref_response.json` và `data/raw/crossref_records.json`.
- **Tín hiệu nghiệm thu:**
  ```bash
  python -c "import chromadb, great_expectations, sentence_transformers; print('Môi trường sẵn sàng')"
  python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"
  ```
  Console in ra đúng chuỗi `Môi trường sẵn sàng` và `Tín hiệu hoàn thành: Đã tải 24 bài báo`.

---

### Checkpoint 1: Data Cleaning & Data Observability với Great Expectations 1.x (35 phút)
- **Mục tiêu:** Tiền xử lý, chuẩn hóa `text_for_embedding`, tính `age_days` và thiết lập chốt kiểm dịch chất lượng tự động theo chuẩn GX 1.x cùng Freshness SLA.
- **Nhiệm vụ:**
  1. Hoàn thiện hàm `build_clean_dataframe` trong `src/ingestion/cleaning.py`: khử trùng lặp theo `paper_id`, tính `age_days = (run_date - published).days`, ghép `text_for_embedding`.
  2. Cấu hình ephemeral context của Great Expectations 1.x trong `src/observability/quality.py`:
     ```python
     context = gx.get_context(mode="ephemeral")
     data_source = context.data_sources.add_pandas(name="papers_source")
     data_asset = data_source.add_dataframe_asset(name="papers_asset")
     batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
     batch = batch_def.get_batch(batch_parameters={"dataframe": df})
     ```
  3. Định nghĩa 4 Expectations thiết yếu: `ExpectTableRowCountToBeBetween`, `ExpectColumnValuesToNotBeNull`, `ExpectColumnValuesToBeUnique`, `ExpectColumnValueLengthsToBeBetween`.
  4. Tính toán Freshness SLA: Cảnh báo `is_fresh = False` nếu tỷ lệ bài báo có `age_days > 180` vượt quá 25%.
- **Tín hiệu nghiệm thu:**
  ```bash
  python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(f'Tín hiệu hoàn thành: Clean thành công {len(df)} dòng')"
  python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print(f'Tín hiệu hoàn thành: Quality check status = {res[\"success\"]}')"
  ```
  Console in ra `Tín hiệu hoàn thành: Clean thành công 24 dòng` và `Tín hiệu hoàn thành: Quality check status = True`.

---

### Checkpoint 2: Benchmark Test Set & ChromaDB Vector Store Indexing (30 phút)
- **Mục tiêu:** Xây dựng bộ test đánh giá chuẩn hóa gồm các câu hỏi qua 4 nhóm nghiệp vụ và đánh chỉ mục vector trên ChromaDB.
- **Nhiệm vụ:**
  1. Viết logic sinh câu hỏi đánh giá trong `src/evaluation/testset.py` phủ đủ 4 nhóm: `summary`, `authors`, `date`, `categories`.
  2. Lưu kết quả ra file `data/eval/test_set.json`.
  3. Khởi tạo ChromaDB collection `papers-baseline`, nạp vector embedding sinh từ `all-MiniLM-L6-v2` cho toàn bộ các tài liệu sạch.
- **Tín hiệu nghiệm thu:**
  ```bash
  python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=build_test_set(df, s.paths.eval_testset); print(f'Tín hiệu hoàn thành: Sinh được {len(ts)} câu hỏi test')"
  ```
  Console in ra `Tín hiệu hoàn thành: Sinh được 10 câu hỏi test`.

---

### Checkpoint 3: Baseline Pipeline End-to-End & Báo Cáo Pha 1 (25 phút)
- **Mục tiêu:** Chạy end-to-end chu trình dữ liệu sạch, kiểm thử RAG Agent và đo lường chỉ số nền (Baseline Benchmarks).
- **Nhiệm vụ:**
  1. Hoàn thiện liên kết trong `src/pipelines/phase1.py` và chạy kịch bản `python script/run_phase1.py`.
  2. Kiểm tra các artifact sinh ra:
     - `data/clean/papers_clean.csv` & `data/clean/papers_clean.json`
     - `data/chroma/` (vector database nạp dữ liệu sạch)
     - `data/eval/test_set.json`
     - `data/results/baseline_metrics.json`
     - `data/reports/phase1_report.md`
- **Tín hiệu nghiệm thu:**
  File `data/results/baseline_metrics.json` xuất hiện với các chỉ số `retrieval_hit_rate` và `mean_token_f1`, báo cáo `data/reports/phase1_report.md` được sinh ra hoàn chỉnh.

---

### Checkpoint 4: Synthetic Data Corruption & Đo Lường Suy Giảm (45 phút)
- **Mục tiêu:** Giả lập sự cố dữ liệu bẩn trong sản xuất bằng cách tiêm 6 kịch bản lỗi, chứng minh Data Quality Gate báo động và Agent suy giảm chất lượng (Silent Failure).
- **Nhiệm vụ:**
  1. Triển khai 6 kịch bản làm bẩn dữ liệu trong `src/ingestion/corruption.py`:
     - Drop latest records (mất 20% bản ghi mới).
     - Blank summary (xóa rỗng tóm tắt).
     - Inject noise (chèn ký tự rác vào tóm tắt).
     - Truncate title (cắt ngắn tiêu đề < 8 ký tự).
     - Stale date (lùi ngày xuất bản về quá khứ).
     - Duplicate rows (nhân bản dữ liệu).
  2. Ghi log chi tiết vào `data/results/corruption_log.json`.
  3. Đo lường sự sụt giảm chất lượng retrieval và câu trả lời của RAG trên tập dữ liệu bị tiêm lỗi, ghi ra `data/results/corrupted_metrics.json`.
- **Tín hiệu nghiệm thu:**
  Tồn tại `data/results/corruption_log.json` ghi nhận đầy đủ 6 dạng lỗi và file `data/results/corrupted_metrics.json` phản ánh rõ rệt sự sụt giảm chỉ số so với baseline.

---

### Checkpoint 5: Idempotent Repair & Báo Cáo Đối Chiếu 3 Trạng Thái (45 phút)
- **Mục tiêu:** Tự động kích hoạt cơ chế phục hồi dữ liệu an toàn (Idempotent Repair) từ nguồn Raw đáng tin cậy, lập báo cáo so sánh định lượng 3 trạng thái.
- **Nhiệm vụ:**
  1. Thực thi luồng khôi phục dữ liệu sạch từ bản lưu trữ thô ban đầu `data/raw/crossref_records.json` (hoặc `crossref_response.json`).
  2. Chạy toàn bộ pipeline kiểm chứng qua lệnh:
     ```bash
     python script/run_corruption_flow.py
     ```
  3. Xuất báo cáo đối chiếu chi tiết tại `data/reports/corruption_report.md` với bảng so sánh rõ ràng 3 trạng thái: **Baseline vs Corrupted vs Repaired**.
- **Tín hiệu nghiệm thu:**
  Console in ra bảng so sánh hiệu năng 3 trạng thái, file `data/reports/corruption_report.md` có đầy đủ 3 cột so sánh chứng minh AI lấy lại phong độ sau khi phục hồi dữ liệu.

---

### Checkpoint 6: Live Demo Trên Bảng, Q&A & Nghiệm Thu Nộp Bài (30 phút)
- **Mục tiêu:** Các nhóm lần lượt lên bảng trình diễn (Live Demo) quy trình phát hiện dữ liệu bẩn và cơ chế tự phục hồi trước Giảng viên & cả lớp, phản biện Q&A, đối chiếu checklist và hoàn tất nộp bài.
- **Nhiệm vụ:**
  1. Chuẩn bị terminal và artifacts: sẵn sàng chạy demo trực tiếp `run_phase1.py` và `run_corruption_flow.py`.
  2. Đại diện nhóm lên bảng (3-5 phút/nhóm):
     - Trình chiếu bảng đối chiếu 3 trạng thái: Baseline vs Corrupted vs Repaired từ `corruption_report.md`.
     - Chỉ ra hiện tượng Silent Failure khi RAG bị tiêm lỗi dữ liệu và sự phục hồi sau khi chạy Repair.
     - Trả lời các câu hỏi chất vấn kỹ thuật từ Giảng viên & Trợ giảng (GX 1.x, Freshness SLA, vector embeddings, tính Idempotent).
  3. Rà soát checklist cuối giờ, đảm bảo 100% thành viên có commit trên GitHub nhánh `main` (Insights > Contributors) và nộp link repository lên VLearn LMS trước 23:59:59.
- **Tín hiệu nghiệm thu:**
  Bảo vệ thành công phần Live Demo trên bảng, toàn bộ thành viên xuất hiện trên Insights > Contributors của GitHub nhánh `main` và đã submit link bài tập lên LMS.
