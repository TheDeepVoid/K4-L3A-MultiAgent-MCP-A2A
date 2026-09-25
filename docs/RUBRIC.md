# TIÊU CHÍ CHẤM ĐIỂM (RUBRIC): DAY 10 - DATA PIPELINE & DATA OBSERVABILITY

> **Tổng điểm chuẩn:** 100 điểm (bắt buộc)  
> **Điểm thưởng tối đa (Bonus):** 10 điểm (vượt chuẩn)  
> **Điểm tối đa có thể đạt:** 110/100 điểm  
> **Yêu cầu bằng chứng:** Mọi mức điểm đều yêu cầu mã nguồn thực thi, log kiểm chứng, và file artifact dữ liệu tương ứng.

---

## 1. Bảng Tiêu Chí Điểm Bắt Buộc (Thang 100)

| STT | Tiêu chí đánh giá | Điểm tối đa | Bằng chứng yêu cầu (Evidence) | Tiêu chuẩn đạt điểm tối đa |
| :---: | :--- | :---: | :--- | :--- |
| **1** | **Cấu trúc dự án & Quản lý môi trường** | **10** | `pyproject.toml` / `requirements.txt`, cấu trúc thư mục module hóa sạch sẽ | Dự án được tổ chức theo module chuẩn (`core`, `ingestion`, `observability`, `evaluation`, `agent`), môi trường ảo tái lập dễ dàng qua `uv` hoặc `pip`. Không bị lỗi import path. |
| **2** | **Raw Data Ingestion & Lineage** | **15** | `src/ingestion/crossref.py`, `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Tải và parse thành công dữ liệu từ Crossref API (hoặc local fallback snapshot khi mất mạng). Lưu trữ đầy đủ 2 file raw artifact để đảm bảo data lineage. |
| **3** | **Data Cleaning & Pre-embed Modeling** | **15** | `src/ingestion/cleaning.py`, `data/clean/papers_clean.csv` / `papers_clean.json` | Xử lý sạch văn bản (loại bỏ JATS XML tag, khoảng trắng thừa), tính toán `age_days`, khử trùng lặp theo `paper_id`, và sinh cột `text_for_embedding` đầy đủ cấu trúc 5 phần. |
| **4** | **Embedding & Vector Store Indexing** | **10** | `src/retrieval/embeddings.py`, `src/retrieval/index.py`, ChromaDB local persist directory | Khởi tạo thành công ChromaDB collection, sinh vector embedding từ mô hình `all-MiniLM-L6-v2`, index 24 tài liệu đầy đủ metadata truy vấn. |
| **5** | **Multi-Provider QA Agent** | **10** | `src/retrieval/` (`agent.py`, `llm.py`, `qa.py`) router và model clients | Hệ thống Agent hỗ trợ cơ chế chuyển đổi linh hoạt giữa các LLM provider (`mock`, `google`, `openai`, `anthropic`). Xử lý prompt chặt chẽ, trích xuất câu trả lời chuẩn xác từ context. |
| **6** | **Baseline Evaluation & Scoring** | **10** | `src/evaluation/testset.py`, `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` | Sinh bộ testset 10 câu hỏi đa dạng qua 4 dạng nghiệp vụ (`summary`, `authors`, `date`, `categories`). Đánh giá đo lường đầy đủ Hit Rate và Token F1 trên dữ liệu sạch. |
| **7** | **Data Observability (GX 1.x & Freshness SLA)** | **15** | `src/observability/quality.py`, log kiểm định GX | Cài đặt đúng cú pháp Great Expectations 1.x (không dùng cú pháp cũ bị lỗi). Định nghĩa đủ 4 expectations thiết yếu. Đo lường tỷ lệ bài báo quá hạn (`age_days > 180`) theo Freshness SLA. |
| **8** | **Data Corruption Suite, Repair & Impact Analysis** | **15** | `src/ingestion/corruption.py`, `data/reports/corruption_report.md`, `corrupted_metrics.json`, `repaired_metrics.json` | Thực thi đủ 6 kịch bản làm bẩn dữ liệu. Minh chứng rõ rệt sự sụp đổ chỉ số hiệu năng trên dữ liệu bẩn và phục hồi sau khi sửa chữa. Báo cáo đối chiếu 3 trạng thái có phân tích sâu sắc. |
| | **TỔNG ĐIỂM BẮT BUỘC** | **100** | | |

---

## 2. Tiêu Chí Điểm Thưởng (Bonus - Tối đa 10 điểm)

> **Lưu ý:** Điểm bonus chỉ được xét duyệt khi nhóm đã hoàn thành và đạt ít nhất 85 điểm ở phần bài bắt buộc. Tổng điểm sau bonus không vượt quá 110 điểm.

| STT | Hạng mục vượt chuẩn | Điểm cộng | Điều kiện & Bằng chứng nghiệm thu |
| :---: | :--- | :---: | :--- |
| **B1** | **Interactive Observability Dashboard / Drift Monitor** | **+5** | Xây dựng giao diện web trực quan (Streamlit / Gradio / HTML) hiển thị trạng thái Data Quality, biểu đồ phân bố độ tuổi bài báo, hoặc cảnh báo Drift theo thời gian thực. |
| **B2** | **Automated Self-Healing / Auto-Repair Pipeline** | **+5** | Pipeline có cơ chế tự động phát hiện lỗi schema/data quality vi phạm và tự động kích hoạt logic rollback hoặc re-fetch/repair tự động mà không cần can thiệp thủ công. |
| **B3** | **End-to-End Automated Test Suite (Pytest CI)** | **+5** | Bộ test tự động kiểm thử toàn diện từ Ingestion, Cleaning, GX Suite, đến Retrieval với coverage > 80%, có cấu hình chạy qua GitHub Actions hoặc script one-click test. |

*(Tổng điểm thưởng tối đa cho cả bài lab không vượt quá **10 điểm**).*

---

## 3. Quy Định Trừ Điểm & Chế Tài (Deductions)

| Mức độ vi phạm | Lỗi cụ thể | Mức trừ điểm |
| :--- | :--- | :---: |
| **Nghiêm trọng** | Commit API Key / Token bí mật vào Git history | **-20đ** (hoặc 0đ nếu leak public repo) |
| **Nghiêm trọng** | Bịa đặt số liệu trong báo cáo, không khớp với kết quả chạy thực tế | **-20đ** |
| **Nghiêm trọng** | Đạo văn / Sao chép code giữa các nhóm | **Hủy bài (0đ)** |
| **Trung bình** | Mã nguồn không chạy được end-to-end trên máy giám khảo / trợ giảng | **-15đ** |
| **Trung bình** | Sử dụng sai chuẩn Great Expectations (dùng cú pháp cũ gây crash) | **-10đ** |
| **Trung bình** | Hardcode đường dẫn tuyệt đối local (`C:\Users\...` hoặc `D:\...`) | **-5đ** |
| **Nhẹ** | Thiếu một trong các file quy ước chuẩn (`TEAM.md`, `SUBMISSION.md`, `CHECKPOINTS.md`, `RULES.md`) | **-5đ / file** |
| **Nhẹ** | File `TEAM.md` không có phần tự khai báo đóng góp chi tiết từng thành viên | **-5đ / thành viên** |
| **Nhẹ** | Nộp muộn sau deadline quy định (theo mốc thời gian quy định tại `RULES.md`) | **-10% đến -25%** |
