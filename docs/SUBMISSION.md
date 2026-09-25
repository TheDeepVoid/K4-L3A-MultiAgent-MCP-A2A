# Hướng Dẫn Nộp Bài & Quy Chuẩn Đánh Giá (SUBMISSION)

> ⚠️ **QUY ĐỊNH BẮT BUỘC ĐỂ TRÁNH THIẾU BÀI HOẶC CHẤM NHẦM:**  
> Dù bài thực hành làm theo nhóm, **MỖI CÁ NHÂN ĐỀU PHẢI TỰ NỘP ĐƯỜNG LINK REPOSITORY CỦA NHÓM LÊN CỔNG VLEARN LMS**.  
> Cổng LMS chấm điểm độc lập theo tài khoản của từng cá nhân. Nếu thành viên nào không nộp link thì hệ thống sẽ ghi nhận vắng/chưa nộp bài!

---

## 1. QUY TẮC ĐẶT TÊN REPO BÀI NỘP

Theo **Quy ước chung Khóa 4**:
- **Cấu trúc đặt tên repo:**  
  `K4-L3-DAY10-TenNhom-DataPipeline`  
  *(Viết không dấu, không khoảng trắng, ngăn cách bằng dấu gạch nối `-`).*
- **Ví dụ chuẩn:**  
  `K4-L3-DAY10-DataTitans-DataPipeline`  
  `K4-L3-DAY10-Group05-DataPipeline`

---

## 2. DEADLINE & THỜI ĐIỂM CHỐT BÀI

- **Thời hạn chốt bài (Default Deadline):** **23h59 trong ngày làm lab** (Giờ Việt Nam — GMT+7).
- **Quy định gia hạn:** Nếu có thông báo chính thức từ Key Coach, hạn nộp có thể được mở rộng tối đa 48h sau buổi lab.
- **Phạt nộp muộn:** Sau thời điểm chốt bài, các commit muộn sẽ bị trừ 10% tổng số điểm cho mỗi ngày trễ hạn. Không chấp nhận các commit sửa bài sau thời hạn gia hạn.

---

## 3. CẤU TRÚC REPO PHẢI NỘP (DELIVERABLES)

Trước khi nộp bài, repository của nhóm trên GitHub phải đảm bảo có đầy đủ các artifacts sinh ra qua các giai đoạn:

```text
K4-L3-DAY10-TenNhom-DataPipeline/
├── data/
│   ├── raw/
│   │   ├── crossref_response.json           <- Raw response từ Crossref API
│   │   └── crossref_records.json            <- Raw records đã parse
│   ├── clean/
│   │   ├── papers_clean.csv                 <- Dữ liệu sạch đã chuẩn hóa
│   │   └── papers_clean.json
│   ├── chroma/                              <- Vector Database ChromaDB (chứa 3 collections tách biệt)
│   ├── eval/
│   │   └── test_set.json                    <- Bộ 10 câu hỏi benchmark cố định
│   ├── quality/
│   │   ├── baseline_quality_report.json     <- Báo cáo GX 1.x cho dữ liệu sạch (Pass)
│   │   ├── corrupted_quality_report.json    <- Báo cáo GX 1.x khi bị tiêm lỗi (Fail)
│   │   └── freshness_report.json            <- Báo cáo độ tươi Freshness SLA
│   ├── results/
│   │   ├── baseline_metrics.json            <- Hit rate & F1 của Baseline
│   │   ├── corruption_log.json              <- Nhật ký chi tiết 6 dạng lỗi đã tiêm
│   │   ├── corrupted_metrics.json           <- Chỉ số sụt giảm của Corrupted flow
│   │   └── repaired_metrics.json            <- Chỉ số phục hồi sau khi Repair
│   └── reports/
│       ├── phase1_report.md                 <- Báo cáo phân tích Baseline
│       └── corruption_report.md             <- BẢNG ĐỐI CHIẾU ĐỊNH LƯỢNG 3 TRẠNG THÁI
├── script/
│   ├── run_phase1.py                        <- Entrypoint chạy Pha 1
│   └── run_corruption_flow.py               <- Entrypoint chạy Pha 2
├── src/                                     <- Toàn bộ code hoàn thiện trong core/, ingestion/, retrieval/, evaluation/, observability/, pipelines/
├── report/                                  <- Báo cáo tổng kết nhóm và cá nhân
│   ├── group_report.md                      <- Báo cáo kết quả chung của nhóm
│   └── <MSSV>_HoTen.md                      <- Báo cáo vai trò cá nhân của từng thành viên
├── docs/                                    <- Thư mục tài liệu hướng dẫn và quy chuẩn
│   ├── Guide.md                             <- Hướng dẫn kỹ thuật chi tiết
│   ├── CHECKPOINTS.md                       <- Lộ trình 7 checkpoints và cách tự kiểm tra
│   ├── RUBRIC.md                            <- Tiêu chí chấm điểm
│   ├── RULES.md                             <- Quy định học vụ và liêm chính học thuật
│   ├── SUBMISSION.md                        <- Hướng dẫn nộp bài
│   └── TEAM.md                              <- Danh sách thành viên, MSSV & phần tự khai cá nhân
├── README.md                                <- Đề bài và tài liệu tổng quan
```

---

## 4. CHECKLIST BẮT BUỘC TRƯỚC KHI NỘP LINK LÊN VLEARN

- [ ] **Chạy thành công 2 lệnh:** 
  - `python script/run_phase1.py` (Exit code 0)
  - `python script/run_corruption_flow.py` (Exit code 0)
- [ ] **Báo cáo đối chiếu 3 trạng thái:** Tồn tại `data/reports/corruption_report.md` có đầy đủ bảng so sánh Baseline vs Corrupted vs Repaired.
- [ ] **Chứng minh được độ suy giảm và phục hồi:** Có bằng chứng số liệu trong `baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json`.
- [ ] **Khai báo `TEAM.md`:** Đã điền đầy đủ họ tên, MSSV và phần tự khai cá nhân của từng thành viên.
- [ ] **Bảo mật:** Không commit file `.env` chứa API Key lên GitHub.
- [ ] **Kiểm tra Contributor trên GitHub nhánh `main`:**
  - Truy cập repo nhóm trên GitHub $\rightarrow$ vào tab **Insights > Contributors**.
  - Bắt buộc **100% thành viên trong nhóm** đều phải xuất hiện trên đồ thị commit của nhánh mặc định (`main`).
- [ ] **Nộp link:** Từng thành viên copy link repo (ví dụ: `https://github.com/<UserTruongNhom>/K4-L3-DAY10-TenNhom-DataPipeline`) và nộp lên cổng LMS trước 23h59!
