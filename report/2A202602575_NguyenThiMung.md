# Báo cáo Cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân
- **Họ và tên:** Nguyễn Thị Mừng
- **MSSV:** 2A202602575
- **Tên nhóm:** K4A-DAY10-VSF-DataPipeline
- **Vai trò chính:** Pipeline integration và Retrieval

## 2. Module và Deliverables phụ trách
Theo phân công nhóm, tôi chịu trách nhiệm xây dựng hệ thống nhúng (Embedding/Index), đánh giá (Evaluation) và trực tiếp điều phối (Orchestration) kết nối toàn bộ các mắt xích của Pipeline. Cụ thể các file/module tôi sở hữu:
- **`core/`**: Quản lý cấu hình, biến môi trường và tiện ích chung của dự án.
- **`retrieval/`, MiniLM, ChromaDB**: Tích hợp mô hình nhúng và hệ cơ sở dữ liệu vector.
- **Evaluation**: Đo lường các chỉ số Hit rate, Token F1, Judge (`data/results/*_metrics.json, *_answers.json`).
- **Orchestration**: Kịch bản chạy toàn tuyến `phase1.py`, `corruption_flow.py` và sinh báo cáo (`phase1_report.md`, `corruption_report.md`).
- **Corruption/repair (Đồng sở hữu cùng Ngọc Trân)**: Điều phối logic Rebuild repaired data từ Raw.

## 3. Chi tiết công việc đã thực hiện

### 3.1. Thiết lập Core & Cấu hình (`core/`)
- Cấu hình file `core/config.py` và `core/utils.py`, quản lý tham số LLM (`gpt-4o-mini`), Embedding model, cấu hình thông số truy vấn (như `top_k = 4`) và đồng bộ hệ thống path artifacts (đường dẫn file) cho toàn bộ pipeline.

### 3.2. Khối Embedding & Index (Thư mục `retrieval/`)
- Nhận đầu vào là dataframe sạch từ phần Cleaning, tôi tích hợp mô hình mã nguồn mở `sentence-transformers/all-MiniLM-L6-v2` để sinh vector embeddings.
- Thiết lập hệ lưu trữ vector **ChromaDB local**. Xây dựng cơ chế tạo lập và cô lập 3 collection riêng biệt tương ứng với 3 trạng thái: `papers-baseline`, `papers-corrupted`, và `papers-repaired` để không bị trùng lặp dữ liệu. Output sinh ra các file tại `data/embeddings/`.

### 3.3. Khối Evaluation (Đánh giá LLM)
- Xây dựng hệ thống QA truy xuất (Retrieval QA) sử dụng cấu hình OpenAI để trả lời câu hỏi dựa trên ngữ cảnh đã index.
- Tính toán và ghi nhận các chỉ số đánh giá: Retrieval Hit rate, Mean Token F1, và điểm Judge Heuristic. Kết quả được lưu tự động vào `data/results/*_metrics.json` và `*_answers.json`.

### 3.4. Orchestration (`phase1.py` & `corruption_flow.py`)
- **Pipeline Phase 1:** Lắp ráp thứ tự chạy tuần tự: Load Settings -> Load Raw -> Cleaning -> Observability Gate -> Indexing -> Evaluation. Kết xuất ra `phase1_report.md`.
- **Pipeline Phase 2 (Corruption/Repair Flow):** 
  - Điều phối kịch bản lấy clean dataframe để bạn Trân tiêm 6 lỗi.
  - Gọi re-index và re-evaluate dữ liệu lỗi (Corrupted).
  - Khởi động cơ chế Repair: Chủ động đọc lại từ `data/raw/crossref_records.json` để rebuild sạch sẽ, sau đó re-index và re-evaluate dữ liệu phục hồi (Repaired).
  - Tự động sinh `corruption_report.md` tóm tắt so sánh 3 trạng thái.

## 4. Kết quả đạt được
- **Embedding & Retrieval:** Xây dựng thành công 3 embedding manifests. Khả năng truy hồi (Retrieval Hit Rate) ở mốc Baseline đạt tuyệt đối **1.0000** và Token F1 đạt **0.3400**.
- **Orchestration:** Các file `run_phase1.py` và `run_corruption_flow.py` thực thi trơn tru (exit code 0), các phase chạy đúng thứ tự và truyền dữ liệu cho nhau chính xác mà không bị đứt gãy.
- **Đánh giá suy giảm & phục hồi:** Metrics tôi đo lường thể hiện rất rõ tác động của lỗi (Hit rate giảm từ 1.0000 -> 0.2000, F1 giảm từ 0.3400 -> 0.0000). Ở trạng thái Repaired, các chỉ số phục hồi 100% về đúng mốc Baseline.

## 5. Tự đánh giá và Bài học
- **Giới hạn:** Bộ đánh giá Judge hiện tại đang dùng Fallback Heuristic thay vì gọi một mô hình LLM làm giám khảo (Evaluator LLM) độc lập; tool Ragas chưa được kích hoạt.
- **Bài học:** Việc đóng vai trò Orchestration đòi hỏi cái nhìn tổng quan (End-to-End) khắt khe. Việc thiết lập đúng cấu trúc ChromaDB Collections theo từng trạng thái data (Baseline/Corrupted/Repaired) là cực kỳ quan trọng để đảm bảo Evaluation Metrics mang ý nghĩa thực sự và không bị rò rỉ ngữ cảnh (Context Leakage) trong bài test.
