# NỘI QUY & NGUYÊN TẮC THỰC HIỆN BÀI LAB (RULES)

> **Mã môn:** AI-ENGINEER-K4  
> **Áp dụng cho:** Bài Lab Day 10 - Data Pipeline & Data Observability  
> **Đối tượng:** Học viên chương trình Đào tạo Nhân Tài AI Thực Chiến Khóa 4 - VinUni

---

## 1. Nguyên Tắc Deadline & Nộp Bài

1. **Thời hạn chót (Deadline):**
   - **Mặc định:** `23:59:59` ngày diễn ra bài lab (Múi giờ `GMT+7 / Asia/Ho_Chi_Minh`).
   - Mọi mốc thời gian khác phải tuân thủ thông báo chính thức từ Giảng viên / Trợ giảng trên hệ thống VLearn LMS.
2. **Quy định nộp bài cá nhân (BẮT BUỘC):**
   - Dù bài lab được triển khai theo **hình thức nhóm (Teamwork)** và dùng chung 1 GitHub Repository, **TỪNG THÀNH VIÊN VẪN PHẢI NỘP ĐƯỜNG LINK REPO CỦA NHÓM LÊN VLEARN LMS TỪ TÀI KHOẢN CÁ NHÂN**.
   - Bất kỳ thành viên nào không nộp link trên tài khoản LMS của mình trước hạn chót sẽ bị hệ thống ghi nhận là **0 điểm bài lab** do không có bản ghi nộp bài hợp lệ.
3. **Chính sách trễ hạn (Late Submission):**
   - Nộp muộn trong vòng 0 - 2 giờ: **Trừ 10% tổng điểm**.
   - Nộp muộn từ 2 - 12 giờ: **Trừ 25% tổng điểm**.
   - Nộp muộn sau 12 giờ: **0 điểm** (trừ trường hợp bất khả kháng được thông báo và phê duyệt bởi Giảng viên phụ trách trước hạn chót).

---

## 2. Bảo Mật API Key & Quản Trị Bí Mật (Secret Management)

1. **Tuyệt đối cấm commit API Key:**
   - Tuyệt đối không commit file `.env`, file cấu hình chứa `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` hoặc bất kỳ Secret/Token nào vào Git history.
   - Luôn sử dụng file `.env.example` với các giá trị placeholder (`your_api_key_here`).
2. **Chế tài xử phạt:**
   - Bị phát hiện commit API Key cá nhân hoặc key của ban tổ chức vào Git: **Trừ ngay 20 điểm** và yêu cầu revoke/rotate key lập tức.
   - Nếu commit vào public repository gây rò rỉ chi phí: **Hủy kết quả bài lab (0 điểm)**.

---

## 3. Chính Sách Sử Dụng Trợ Lý AI (AI Policy)

1. **Khuyến khích AI làm đòn bẩy (Accelerator):**
   - Học viên được khuyến khích sử dụng các công cụ Generative AI (Gemini, Claude, ChatGPT, GitHub Copilot, Cursor) để hỗ trợ tìm kiếm tài liệu, giải thích cú pháp thư viện (Great Expectations, ChromaDB), gợi ý cấu trúc code.
2. **Yêu cầu làm chủ kiến trúc & Thấu hiểu sâu sắc:**
   - Mọi dòng code được commit vào repository phải do các thành viên trong nhóm hoàn toàn hiểu rõ logic và có khả năng giải thích, bảo vệ trực tiếp trước Hội đồng giảng viên/Mentor.
   - Cấm sao chép nguyên mẫu (Copy-paste mù quáng) các đoạn mã AI tạo ra mà không kiểm chứng hoặc không hiểu luồng dữ liệu.

---

## 4. Liêm Chính Học Thuật & Phòng Chống Gian Lận (Academic Integrity)

1. **Nguyên tắc độc lập nhóm:**
   - Mỗi nhóm phải tự thiết kế, lập trình và thực thi pipeline của nhóm mình.
   - Nghiêm cấm mọi hành vi sao chép code, clone repository, hoặc tráo đổi artifact/báo cáo giữa các nhóm với nhau.
2. **Quy định về dữ liệu & Báo cáo thực tế:**
   - Các file báo cáo `phase1_report.md`, `corruption_report.md` và các file kết quả `baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json` phải được sinh ra từ quá trình chạy pipeline thực tế (`script/run_phase1.py`, `script/run_corruption_flow.py`).
   - Nghiêm cấm bịa đặt, sửa tay số liệu đánh giá (Hit Rate, Token F1, Recall) để làm đẹp báo cáo.
3. **Xử lý vi phạm:**
   - Nếu phát hiện gian lận số liệu hoặc đạo văn code: Nhóm vi phạm nhận điểm 0 cho toàn bộ bài lab và chịu hình thức kỷ luật học thuật theo quy chế của VinUni & chương trình.

---

## 5. Quy Ước Đóng Góp Nhóm & Minh Bạch Phân Công

1. **Tập tin `TEAM.md`:**
   - Phải điền đầy đủ danh sách thành viên, MSSV, vai trò và phân công cụ thể từng Checkpoint.
   - Mỗi cá nhân bắt buộc có mục báo cáo đóng góp riêng trong `TEAM.md` (`# Cá nhân` -> `## HoVaTen-MSSV`).
2. **Lịch sử Git Commit:**
   - Điểm số của từng cá nhân sẽ được đối chiếu giữa bảng phân công trong `TEAM.md` và lịch sử commit thực tế trên GitHub (author, email, commit messages).
   - Trường hợp một thành viên không có commit hoặc không tham gia đóng góp sẽ nhận điểm 0 dù nhóm hoàn thành tốt bài lab.
