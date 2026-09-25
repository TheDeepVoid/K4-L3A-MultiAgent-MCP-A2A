# Hướng Dẫn Kỹ Thuật Chi Tiết (Technical Guide)

Chào mừng bạn đến với tài liệu hướng dẫn từng bước của bài lab **Day 10 - Data Pipeline & Data Observability**.

> 💡 **Lời khuyên nhỏ trước khi bắt đầu:**  
> Đừng lo lắng nếu bạn thấy các thuật ngữ dữ liệu nghe có vẻ "đao to búa lớn"! Bản chất bài lab này rất thú vị: Chúng ta sẽ cùng nhau xây dựng một "nhà máy lọc nước sạch" (Data Pipeline) để cung cấp cho AI, sau đó thử nghịch ngợm "tiêm một chút nước đục" (Data Corruption) xem AI có bị đau bụng trả lời bậy bạ không, và cuối cùng dùng "bộ lọc dự phòng" để trả lại trạng thái sạch bóng!
> 
> Hãy đi từng bước một cách bình tĩnh, kiểm tra kỹ **Tín hiệu hoàn thành** ở mỗi bước trước khi chuyển sang bước tiếp theo nhé.

---

## Bước 1: Khởi tạo Môi trường & Cấu hình

Trước khi bắt tay vào làm việc, chúng ta cần chuẩn bị một "căn bếp" gọn gàng và đầy đủ dụng cụ:

1. Mở terminal tại thư mục gốc của project.
2. Kiểm tra phiên bản Python:
   ```bash
   python --version
   ```
   *Lưu ý:* Yêu cầu phiên bản Python 3.11, 3.12 hoặc 3.13. Các thư viện mới nhất trong bài lab yêu cầu môi trường này để tránh phát sinh lỗi không mong muốn. Nếu máy bạn đang ở bản cũ hơn (như 3.9 hay 3.10), hãy chuyển sang Python 3.11+ trước khi cài gói nhé.
3. Kích hoạt môi trường ảo:
   - Windows PowerShell: `.\.venv\Scripts\Activate.ps1` (hoặc `.\.venv\Scripts\activate`)  
     *(💡 Nếu PowerShell báo lỗi script bị chặn do `ExecutionPolicy`, hãy "thuyết phục" nó bằng lệnh: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` rồi thử lại nhé).*
   - Linux/macOS: `source .venv/bin/activate`
4. Cài đặt toàn bộ thư viện & package dự án:
   ```bash
   python -m pip install -e .
   ```
   *(💡 Mẹo: Lệnh này vừa cài các thư viện ngoài, vừa liên kết mã nguồn trong thư mục `src/` vào môi trường ảo. Nếu máy bạn có sẵn công cụ siêu tốc `uv`, bạn có thể gõ `uv sync` thay thế).*
5. Tạo file cấu hình `.env` từ file mẫu `.env.example`:
   - Trên Windows PowerShell: `Copy-Item .env.example .env`
   - Trên Linux/macOS: `cp .env.example .env`
   Mở file `.env`, tìm dòng `GOOGLE_API_KEY=` và dán mã API Key của bạn ngay sau dấu `=`. Không để khoảng trắng thừa, không cần thêm dấu nháy kép. Máy tính thích sự gọn gàng!
6. Kiểm tra kết nối 3 "vũ khí cốt lõi" (ChromaDB để lưu vector, Great Expectations để kiểm dịch dữ liệu, Sentence-Transformers để tạo embedding):
   ```bash
   python -c "import chromadb, great_expectations, sentence_transformers; print('Môi trường sẵn sàng')"
   ```
   > **Tín hiệu hoàn thành:** Console in `Môi trường sẵn sàng`.

> 💡 **Mẹo gỡ rối (Troubleshooting):**  
> Nếu màn hình báo lỗi đỏ lòm `ModuleNotFoundError`, bạn đừng vội hoang mang! Đây là lỗi 90% người mới gặp phải do terminal chưa kịp kích hoạt đúng môi trường ảo `.venv`:  
> - **Kiểm tra xem bạn đang đứng ở đâu:** Gõ `where python` (trên Windows) hoặc `which python` (trên Mac/Linux). Nếu đường dẫn in ra không nằm trong thư mục `.venv`, hãy chạy lại lệnh kích hoạt ở bước 3.  
> - **Kiểm tra cài đặt:** Hãy chắc chắn bạn đã chạy xong bước 4 (`python -m pip install -e .`). Khi đã vào đúng venv, lệnh kiểm tra sẽ in ra ngay `Môi trường sẵn sàng`!

---

## Bước 2: Thu Thập Dữ Liệu & Cất Giữ Bản Gốc (Raw Preservation) (`src/ingestion/crossref.py`)

Trong bước này, chúng ta sẽ kéo dữ liệu bài báo học thuật từ bên ngoài về và cất giữ một bản sao nguyên gốc.

### Mục tiêu:
- Thu thập metadata từ Crossref REST API công khai.
- Chuẩn hóa các trường thông tin: `paper_id` (mã định danh DOI), `title` (tiêu đề), `summary` (tóm tắt - loại bỏ các thẻ HTML/XML rác như `<jats:p>`), `authors` (tác giả), `categories` (chuyên ngành), `published` (ngày xuất bản).
- Lưu lại 2 file dữ liệu thô (Raw Artifacts) làm "bản sao lưu nguồn cội" (Lineage):
  - `data/raw/crossref_response.json`: Toàn bộ dữ liệu gốc JSON từ API (nguyên đai nguyên kiện, không sửa một dấu phẩy).
  - `data/raw/crossref_records.json`: Danh sách đối tượng `PaperRecord` sau khi bóc tách gọn gàng.

> 🔍 **Tại sao phải cất giữ bản thô (Raw Preservation)?**  
> Hãy coi đây là "bảo hiểm dữ liệu" của bạn! Trong thực tế, dữ liệu gốc cào về thế nào thì phải giữ nguyên như thế. Lỡ các bước làm sạch phía sau bạn gõ nhầm code làm mất dữ liệu, chúng ta chỉ cần chạy lại từ file thô này mà không sợ bị API bên ngoài khóa IP hay mất mạng!

### Cơ chế Cứu hộ Offline (Khi mạng chập chờn hoặc API quá tải):
Nếu mạng phòng lab bị chập chờn hoặc API Crossref đang "hắt hơi sổ mũi" trả về lỗi `429 Too Many Requests`, bạn hoàn toàn yên tâm! Pipeline được trang bị cơ chế tự động chuyển sang đọc file snapshot mẫu có sẵn tại `data/raw/crossref_response.json`. Bạn không cần chỉnh sửa code gì cả, bài lab vẫn sẽ tiếp tục trôi chảy.

Kiểm tra bước 2:
```bash
python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"
```
> Tín hiệu hoàn thành: Console in ra `Tín hiệu hoàn thành: Đã tải 24 bài báo`.

---

## Bước 3: Làm Sạch Dữ Liệu & Chuẩn Bị Câu Chữ Tạo Vector (`src/ingestion/cleaning.py`)

Dữ liệu thô tải về thường có nhiều khoảng trắng thừa, định dạng ngày tháng lung tung. Chúng ta sẽ "tắm rửa" cho dữ liệu sạch sẽ trước khi cho AI học.

### Mục tiêu:
- Loại bỏ khoảng trắng thừa, chuẩn hóa định dạng văn bản cho sạch đẹp.
- Tính toán tuổi đời của dữ liệu: `age_days = (run_date - published).days` (để biết bài báo này đã ra đời được bao nhiêu ngày).
- Ghép nối các trường thành một đoạn ngữ cảnh hoàn chỉnh `text_for_embedding` (đây là "mẩu bánh mì" chuẩn bị đưa cho mô hình nhúng vector):
  ```text
  Title: <Tiêu đề bài báo>
  Authors: <Danh sách tác giả>
  Published: <Ngày xuất bản>
  Categories: <Lĩnh vực chuyên môn>
  Summary: <Tóm tắt nội dung>
  ```
- Khử trùng lặp bản ghi theo khóa duy nhất `paper_id` (tránh việc cùng một bài báo bị nạp 2 lần làm loãng kết quả tìm kiếm).

Kiểm tra bước 3:
```bash
python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(f'Tín hiệu hoàn thành: Clean thành công {len(df)} dòng')"
```
> **Tín hiệu hoàn thành:** Console in ra `Tín hiệu hoàn thành: Clean thành công 24 dòng`.

---

## Bước 4: Dựng "Trạm Kiểm Soát Dữ Liệu" (Data Observability Gate) với Great Expectations 1.x (`src/observability/quality.py`)

Trước khi đưa dữ liệu vào Vector Database, chúng ta phải dựng một "chốt kiểm dịch" nghiêm ngặt. Nếu dữ liệu có dấu hiệu rách nát, chốt này sẽ chặn đứng ngay!

### Yêu cầu Chuẩn GX 1.x (Theo Slide Khóa 4 Trang 51-52):
Không sử dụng cú pháp cũ `context.sources.pandas_default` (đã lỗi thời trên GX 1.x). Chúng ta sử dụng chuẩn mới:
```python
context = gx.get_context(mode="ephemeral")  # mode="ephemeral": chạy tạm trên RAM, cực nhanh và không đẻ file rác
data_source = context.data_sources.add_pandas(name="papers_source")
data_asset = data_source.add_dataframe_asset(name="papers_asset")
batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
batch = batch_def.get_batch(batch_parameters={"dataframe": df})
```

### 4 "Hàng Rào Kiểm Định" (Expectations) Bắt Buộc:
1. `ExpectTableRowCountToBeBetween`: Số lượng bản ghi nằm trong ngưỡng hợp lệ (5 đến 5000 dòng).
2. `ExpectColumnValuesToNotBeNull`: Các cột quan trọng `paper_id`, `title`, `text_for_embedding` không được phép để trống (null).
3. `ExpectColumnValuesToBeUnique`: Mỗi bài báo `paper_id` phải là độc nhất vô nhị, không chấp nhận bản ghi trùng lặp.
4. `ExpectColumnValueLengthsToBeBetween`: Trường `summary` phải có độ dài tối thiểu 30 ký tự (đủ nội dung để AI đọc hiểu).

### Kiểm Tra Độ Tươi Mới (Freshness Monitoring):
Không để AI "ăn dữ liệu ôi thiu"! Chúng ta đo lường tỉ lệ bài báo bị quá hạn (`age_days > 180 ngày` - tức hơn 6 tháng). Nếu tỉ lệ bài báo cũ vượt quá 25%, hệ thống sẽ lập tức gắn cờ cảnh báo `is_fresh = False` (nhắc nhở: dữ liệu sắp cũ, cần cập nhật bài mới!).

Kiểm tra bước 4:
```bash
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print(f'Tín hiệu hoàn thành: Quality check status = {res[\"success\"]}')"
```
> **Tín hiệu hoàn thành:** Console in ra `Tín hiệu hoàn thành: Quality check status = True`.

---

## Bước 5: Tạo Bộ Đề Thi Chuẩn (Benchmark Test Set) (`src/evaluation/testset.py`)

Để biết AI trả lời đúng hay sai, chúng ta cần một "đề thi chuẩn có sẵn đáp án" (Ground Truth) gồm 10 câu hỏi đa dạng, chia đều vào 4 dạng bài toán:
1. `summary`: Hỏi tóm tắt nội dung chính của một bài báo cụ thể.
2. `authors`: Hỏi ai là tác giả của công trình nghiên cứu.
3. `date`: Hỏi thời điểm bài báo được xuất bản.
4. `categories`: Hỏi về chuyên ngành / lĩnh vực phân loại.

Mỗi câu hỏi mẫu trong file `test_set.json` có cấu trúc rõ ràng:
```json
{
  "id": "eval_001",
  "question_type": "summary",
  "question": "What is the summary of the paper '<Title>'?",
  "ground_truth": "<Nội dung câu đầu tóm tắt chuẩn>",
  "ground_truth_doc_ids": ["<DOI bài báo>"]
}
```

Kiểm tra bước 5:
```bash
python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=build_test_set(df, s.paths.eval_testset); print(f'Tín hiệu hoàn thành: Sinh được {len(ts)} câu hỏi test')"
```
> **Tín hiệu hoàn thành:** Console in ra `Tín hiệu hoàn thành: Sinh được 10 câu hỏi test`.

---

## Bước 6: Chạy Toàn Tuyến Dữ Liệu Sạch (Baseline Pipeline) (`script/run_phase1.py`)

Bây giờ là lúc ghép nối toàn bộ mắt xích sạch sẽ để chạy thử nghiệm lần đầu tiên!
Lệnh này sẽ thực hiện trọn gói: Lấy dữ liệu -> Làm sạch -> Kiểm tra chất lượng -> Nhúng ChromaDB -> Đánh giá độ chính xác ban đầu (Baseline).

```bash
python script/run_phase1.py
```

> **Tín hiệu hoàn thành:**
> - File `data/clean/papers_clean.csv` xuất hiện đầy đủ các dòng sạch.
> - File `data/results/baseline_metrics.json` ghi nhận các chỉ số tốt ban đầu (Hit Rate và Token F1).
> - File `data/reports/phase1_report.md` được sinh ra với bảng số liệu chi tiết.

---

## Bước 7: Thử Thách "Tiêm Độc Tố Dữ Liệu" (Data Corruption Suite)

Trong thực tế, hệ thống dữ liệu luôn phải đối mặt với vô vàn sự cố ngoài ý muốn. Tại bước này, chúng ta sẽ đóng vai "kẻ thử thách có chủ đích" trong `src/ingestion/corruption.py` để tiêm 6 dạng lỗi thường gặp nhất:
1. **Drop latest records:** Bỏ rơi 20% các bài báo mới nhất (mô phỏng sự cố mất dữ liệu tươi).
2. **Blank summary:** Xóa trắng phần tóm tắt ở một số dòng (mô phỏng lỗi cào dữ liệu rỗng).
3. **Inject noise:** Chèn các chuỗi ký tự rác vô nghĩa vào tóm tắt (mô phỏng nhiễu ký tự).
4. **Truncate title:** Cắt ngắn tiêu đề bài báo xuống dưới 8 ký tự.
5. **Stale date:** Lùi ngày xuất bản về 365 ngày trước (mô phỏng dữ liệu bị mốc meo).
6. **Duplicate rows:** Nhân đôi các dòng để tạo dữ liệu trùng lặp.

Kiểm tra bước 7:
```bash
python -c "from core.config import load_settings; from ingestion.corruption import corrupt_clean_dataframe; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); c=corrupt_clean_dataframe(df, s.paths.corruption_log); print(f'Tín hiệu hoàn thành: Corrupted {len(c)} dòng')"
```
> **Tín hiệu hoàn thành:** File nhật ký lỗi `data/results/corruption_log.json` được ghi lại chi tiết.

---

## Bước 8: Đo Lường Sự Suy Giảm, Phục Hồi Dữ Liệu & Đối Chiếu 3 Trạng Thái

Đây là cao trào của bài lab! Chúng ta sẽ chạy toàn bộ luồng Phase 2 để:
1. Cho AI trả lời trên dữ liệu bẩn và chứng kiến điểm số sụt giảm nghiêm trọng (Silent Failure).
2. Tự động kích hoạt cơ chế phục hồi an toàn (Idempotent Repair) bằng cách đọc lại từ bản sao lưu thô ban đầu để ghi đè dữ liệu hỏng.
3. Xuất bảng so sánh đối đầu giữa 3 trạng thái: **Dữ liệu Sạch (Baseline) vs Dữ liệu Lỗi (Corrupted) vs Sau Phục Hồi (Repaired)**.

```bash
python script/run_corruption_flow.py
```

> **Tín hiệu hoàn thành:**
> - Console in ra bảng so sánh hiệu năng 3 cột rõ ràng.
> - Báo cáo `data/reports/corruption_report.md` được tạo thành công, minh chứng rõ ràng: Dữ liệu bẩn làm AI nói dối, và sau khi phục hồi đúng cách, AI lấy lại 100% phong độ ban đầu!
