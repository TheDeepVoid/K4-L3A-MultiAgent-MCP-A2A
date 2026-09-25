# L3A Architecture Record

Team phải cập nhật tài liệu này cùng source. Mục tiêu là mô tả quyết định có thể kiểm chứng, không ghi prompt bí mật hoặc chain-of-thought.

## 1. System overview

Vẽ hoặc mô tả luồng từ `inputs/<case_id>.json` đến MCP calls, specialist agents, verifier, output và trace.

Hệ thống dự kiến sử dụng Python async state-machine. Mỗi agent là một hàm có trách nhiệm, input và output riêng. Coordinator quản lý luồng xử lý trong solve_case(case, gateway, trace).

```text
Input case
    |
    v
Coordinator
    |
    v
Order/Item: xác minh thông tin nền cần thiết
    |
    v
Coordinator giao nhiệm vụ liên quan
    |
    +--------------------+
    v                    v
Payment               Shipment
    |                    |
    +--------------------+
    |
    v
Gom facts và evidence theo case_id
    |
    v
Policy: áp dụng chính sách, tạo output dự thảo
    |
    v
Verifier
    |
    +-- Đạt --> Coordinator --> Output cuối
    |
    +-- Cần sửa/bổ sung --> Coordinator
                              |
                              v
                       Agent phụ trách
                              |
                              v
                       Policy → Verifier
                       (tối đa một vòng bổ sung)
```

### Truy cập bằng chứng

- Order/Item, Payment, Shipment và Policy gọi MCP thông qua EvidenceGateway theo quyền được quy định tại mục 2.
- Các nhiệm vụ chỉ chạy đồng thời khi không phụ thuộc dữ liệu nhau.
- Chỉ giao những nhiệm vụ liên quan đến case.
- Evidence được lưu trong state riêng của từng lần solve_case.
- Bộ thu thập evidence là thành phần dùng chung, không bắt buộc là một agent LLM riêng.

### Output và trace

- solve_case trả về dict tuân thủ l3a-output-v2.schema.json.
- TraceWriter ghi các sự kiện thực tế trong suốt quá trình xử lý.
- Message A2A và state nội bộ không được đưa nguyên vào public output.
- Chỉ finalize sau khi Verifier chấp nhận output cuối cùng.

Đây là kiến trúc dự kiến, chưa phản ánh workflow đã triển khai.
Trạng thái triển khai thực tế theo từng phần được ghi tại mục 8.

## 2. Agent ownership

| Actor | Input | Trách nhiệm | Output/handoff |
| --- | --- | --- | --- |
| Coordinator | Case đầu vào | Xác định phạm vi case, chia nhiệm vụ, điều phối và giới hạn vòng xử lý | Nhiệm vụ cho specialist kèm case_id và phạm vi entity |
| Order/item | Nhiệm vụ kiểm tra đơn và sản phẩm | Xác minh trạng thái đơn, item và seller liên quan bằng MCP | Facts đã xác minh và evidence_refs cho Policy |
| Payment | Nhiệm vụ kiểm tra thanh toán | Xác minh giao dịch, thanh toán nhiều phần, thu trùng và hoàn tiền | Facts tài chính và evidence_refs cho Policy |
| Shipment | Nhiệm vụ kiểm tra vận chuyển | Xác minh trạng thái và các mốc giao hàng | Facts vận chuyển và evidence_refs cho Policy |
| Policy | Kết quả specialist và bằng chứng chính sách | Áp dụng chính sách, đề xuất kết luận, trách nhiệm và phương án xử lý | Output dự thảo cho Verifier |
| Verifier | Output dự thảo và bằng chứng đã thu thập | Kiểm tra schema, phạm vi entity, liên kết bằng chứng và tính nhất quán nghiệp vụ | Kết quả kiểm tra cho Coordinator: đạt hoặc yêu cầu bổ sung cụ thể |

Nêu rõ actor nào được quyền gọi tool nào. Tránh cho mọi agent quyền truy vấn tất cả tool nếu không cần thiết.

### Quyền gọi tool

Danh sách tool đã được xác nhận bằng `day09 mcp-tools`. Phân quyền dưới đây là thiết kế cần thực thi trong workflow.

| Actor | Tool được phép gọi |
| --- | --- |
| Coordinator | Discovery qua gateway.list_tools(); không gọi tool dữ liệu |
| Order/item | get_order, get_order_items, get_sellers, get_product_context |
| Payment | get_order_payments, get_payment_timeline, get_refund_timeline |
| Shipment | get_shipment_summary |
| Policy | get_policy |
| Verifier | Không gọi MCP trực tiếp |

### Quy tắc thực thi

- Kiểm tra allowlist của actor trước mỗi lần gọi tool.
- Được phép gọi không có nghĩa phải gọi tất cả tool; chỉ truy vấn khi nhiệm vụ cần dữ liệu đó.
- Mọi lời gọi dữ liệu phải truyền đúng case_id.
- Arguments phải theo định nghĩa tool thực tế, không suy đoán từ tên.
- Verifier yêu cầu Coordinator giao lại nhiệm vụ khi cần thêm evidence.
- get_customer_history chưa cấp cho agent nào vì thiết kế hiện tại chưa xác định nhu cầu sử dụng lịch sử khách hàng.
- Nếu phát sinh nhu cầu, cập nhật quyền và mục đích sử dụng rõ ràng trước khi triển khai lời gọi đó.

### Arguments đã xác nhận qua MCP discovery

| Tool | Arguments bắt buộc |
| --- | --- |
| get_order | case_id, order_id |
| get_order_items | case_id, order_id |
| get_order_payments | case_id, order_id |
| get_payment_timeline | case_id, order_id |
| get_refund_timeline | case_id, order_id |
| get_shipment_summary | case_id, order_id |
| get_sellers | case_id, order_id |
| get_product_context | case_id, order_id |
| get_policy | case_id, policy_version |
| get_customer_history | case_id, customer_unique_id |

Tất cả arguments trên có kiểu string.

- case_id lấy từ case đang xử lý.
- order_id phải thuộc phạm vi case; không tự tạo hoặc lấy từ case khác.
- policy_version phải lấy từ nguồn cấu hình hoặc input được quy định, không tự đoán và không mặc định dùng "latest".
- customer_unique_id phải có căn cứ và thuộc phạm vi case. get_customer_history hiện chưa được cấp quyền trong thiết kế.
- Metadata hiện xác nhận input arguments; chưa xác nhận cấu trúc data trả về của từng tool.

## 3. A2A protocol

Mô tả message envelope, correlation theo `case_id`, điều kiện handoff, timeout và cách tránh vòng lặp. Chỉ trace sự kiện/decision code quan sát được; không trace nội dung suy luận riêng.

### Message nội bộ

Mỗi lần giao hoặc chuyển nhiệm vụ sử dụng message gồm:

| Field | Ý nghĩa |
| --- | --- |
| case_id | Case đang xử lý |
| sender | Agent gửi |
| recipient | Agent nhận |
| task | Nhiệm vụ cụ thể |
| entity_scope | Phạm vi order, item hoặc entity cần kiểm tra |
| facts | Dữ kiện đã xác minh; để trống khi chưa có |
| evidence_refs | Mã bằng chứng thật hỗ trợ facts |
| status | pending, completed hoặc needs_more_evidence |

Đây là message nội bộ, không thêm các field này vào public output hoặc MCP evidence envelope.

### Luồng handoff

1. Coordinator nhận case, xác định yêu cầu và phạm vi entity.
2. Coordinator giao Order/item xác minh thông tin nền cần thiết.
3. Khi đã có đủ định danh, Coordinator giao Payment và Shipment các nhiệm vụ liên quan. Các nhiệm vụ độc lập có thể chạy đồng thời.
4. Kết quả specialist được gom theo case_id và chuyển cho Policy. Mỗi kết quả phải nêu facts, evidence_refs và dữ liệu còn thiếu.
5. Policy sử dụng facts và bằng chứng chính sách để tạo output dự thảo.
6. Policy chuyển bản dự thảo cho Verifier.
7. Nếu kiểm tra đạt, Coordinator trả output đã được xác minh.
8. Nếu cần bổ sung, Verifier nêu rõ phần thiếu; Coordinator giao lại cho specialist phụ trách, sau đó chạy lại Policy và Verifier.

### Điều kiện và giới hạn

- Mọi message phải giữ nguyên case_id của case đang xử lý.
- Agent chỉ xử lý entity trong phạm vi được giao.
- Không chuyển lời khách hàng khai thành facts khi chưa xác minh.
- Specialist thiếu bằng chứng trả status = needs_more_evidence; không tự tạo dữ kiện hoặc evidence_ref.
- Coordinator chờ các nhiệm vụ cần thiết hoàn thành hoặc hết hạn trước khi chuyển kết quả tổng hợp cho Policy.
- Cho phép tối đa một vòng bổ sung sau lần kiểm tra đầu tiên.
- Deadline dự kiến cho toàn bộ solve_case là 180 giây; mỗi lần gọi MCP tối đa 30 giây và không vượt thời gian còn lại.
- Khi hết giới hạn, chỉ trả kết luận về việc thiếu bằng chứng nếu output đó vượt qua kiểm tra schema và nghiệp vụ; nếu không, báo lỗi xử lý case thay vì tạo kết quả giả.

### Trace cho handoff

- task_assigned: Coordinator giao nhiệm vụ.
- handoff: agent chuyển kết quả hoặc yêu cầu cho agent khác.
- Ghi actor, target và case_id đúng với hành động thực tế.
- Chỉ ghi sự kiện quan sát được và decision code;
  không ghi suy luận riêng.

Các quy tắc trên là thiết kế dự kiến, cần được triển khai trong workflow.

## 4. Evidence lifecycle

Mô tả cách validate MCP response, lưu `evidence_ref`, map evidence vào claim/output và emit `tool_result_consumed`. Evidence không được tái sử dụng giữa các case.

### 1. Thu thập

- Specialist gọi MCP thông qua EvidenceGateway, luôn truyền case_id.
- Chỉ gọi tool đã được discovery và được phép dùng theo vai trò.
- EvidenceGateway kiểm tra envelope theo mcp-evidence-response-v1.schema.json trước khi trả kết quả.
- Specialist kiểm tra thêm domain, cấu trúc data cần dùng và phạm vi entity. Envelope hợp lệ chưa bảo đảm đúng nghiệp vụ.

### 2. Lưu theo case

- Mỗi lần chạy solve_case có kho evidence nội bộ riêng.
- Lưu nguyên envelope nhận từ MCP.
- Lưu riêng ngữ cảnh gọi: case_id, actor, tool_name và arguments.
- Không thêm ngữ cảnh nội bộ vào envelope.
- Không chỉnh sửa hoặc tự tạo evidence_ref và result_hash.
- Không tái sử dụng evidence giữa các case.

### 3. Liên kết với kết luận

- Mỗi fact dùng để kết luận phải liên kết với evidence hỗ trợ nó.
- Policy nhận facts cùng evidence_refs từ các specialist.
- Chỉ đưa vào output các evidence_refs thực sự hỗ trợ kết luận.
- Nếu sử dụng claim_assessments, liên kết evidence với từng claim.
- Thiếu bằng chứng phải được ghi nhận rõ; không suy đoán thành fact.

### 4. Ghi trace khi sử dụng

- Emit tool_result_consumed khi agent thực sự dùng kết quả MCP để xác minh fact hoặc đưa ra quyết định.
- Ghi đúng case_id, actor, tool_name và evidence_refs đã sử dụng.
- Việc nhận được response chưa tự động có nghĩa đã sử dụng evidence.
- Mỗi event chứa tối đa 20 evidence_refs theo trace schema.

### 5. Kiểm tra trước khi trả output

- Verifier kiểm tra mọi evidence_ref được trích dẫn đều có trong kho evidence của case hiện tại.
- Kiểm tra ngữ cảnh gọi và entity scope phù hợp với case.
- Kiểm tra nội dung bằng chứng thực sự hỗ trợ kết luận được gắn.
- Kiểm tra danh sách evidence_refs trong output không trùng lặp và không vượt quá giới hạn 30 phần tử.
- Kiểm tra cục bộ không thay thế việc đối chiếu provenance với MCP audit của hệ thống chấm.

Đây là thiết kế dự kiến; EvidenceGateway đã có kiểm tra schema envelope, các bước quản lý và kiểm tra nghiệp vụ cần triển khai thêm.

## 5. Failure policy

| Failure | Retry? | Fallback | Trace event/code |
| --- | --- | --- | --- |
| MCP timeout hoặc lỗi tạm thời đã xác định | Tối đa 2 lần gọi lại, trong deadline còn lại | Ghi nhận thiếu bằng chứng nếu vẫn thất bại | task_assigned / MCP_TEMPORARY_RETRY khi giao lại nhiệm vụ |
| Không tìm thấy dữ liệu | Không lặp lại cùng truy vấn; chỉ truy vấn khác khi có căn cứ | Báo needs_more_evidence cho Coordinator | handoff / EVIDENCE_NOT_FOUND |
| Sai quyền hoặc arguments không hợp lệ | Không retry nguyên trạng | Báo lỗi cấu hình hoặc yêu cầu sửa tham số | handoff / MCP_REQUEST_REJECTED |
| MCP envelope sai schema | Không sử dụng response làm bằng chứng | Báo lỗi contract cho Coordinator | handoff / INVALID_EVIDENCE_ENVELOPE |
| Nguồn dữ liệu mâu thuẫn | Không gọi lại cùng truy vấn để mong có kết quả khác | Áp dụng quy tắc ưu tiên nguồn nếu có; nếu chưa giải quyết được thì giữ trạng thái chưa chắc chắn | handoff / SOURCE_CONFLICT |
| Kết quả specialist không hợp lệ | Tối đa một vòng sửa hoặc bổ sung do Coordinator điều phối | Xử lý theo giới hạn toàn workflow nếu vẫn không đạt | task_assigned / SPECIALIST_REWORK khi giao lại |

### Giới hạn retry

- Một yêu cầu MCP có tối đa 3 lần gọi: lần đầu và 2 lần retry.
- Chờ 1 giây trước retry thứ nhất, 2 giây trước retry thứ hai.
- Mỗi lần gọi tối đa 30 giây và không vượt thời gian còn lại.
- Tổng thời gian solve_case không vượt deadline 180 giây đã chọn.
- Không bắt đầu retry nếu deadline đã hết.
- Chỉ tự động retry thao tác đọc có thể lặp an toàn.
- Chỉ retry lỗi được xác định là tạm thời; không retry mọi exception.
- Giữ nguyên case_id và phạm vi truy vấn khi retry cùng yêu cầu.
- Retry MCP không đặt lại bộ đếm vòng bổ sung của workflow.
- Việc sửa kết quả specialist dùng chung giới hạn một vòng bổ sung đã quy định trong A2A protocol.

### Khi hết giới hạn

- Không tạo evidence_ref hoặc dữ kiện thay thế.
- Nếu bằng chứng chưa đủ, cân nhắc insufficient_evidence và needs_investigation theo đúng tình trạng thực tế.
- Output vẫn phải qua Verifier trước khi trả về.
- Nếu không thể tạo output hợp lệ và trung thực, báo lỗi xử lý case.

### Quy tắc ghi trace

- Các decision_code trong bảng là quy ước nội bộ.
- Chỉ dùng event_type có trong public trace schema.
- Chỉ ghi task_assigned khi thực sự giao hoặc giao lại nhiệm vụ.
- Chỉ ghi handoff khi thực sự chuyển kết quả hoặc báo cáo lỗi.
- Retry kỹ thuật bên trong một nhiệm vụ không tự động tạo thành một sự kiện task_assigned.
- Có thể ghi số lần thử bằng attributes với giá trị đơn.
- Không ghi API key, header xác thực hoặc nguyên văn lỗi chứa bí mật.

Đây là chính sách dự kiến, chưa phải retry đã được triển khai.

## 6. Verification invariants

Liệt kê kiểm tra trước finalize: schema, entity scope, evidence ownership, claim linkage, money totals, responsibility/action consistency và confidence bounds.

Verifier kiểm tra các điều kiện sau trước khi cho phép finalize.

### 1. Public output contract

- Output vượt qua Contracts.validate_output().
- schema_version đúng với variant L3A.
- Có đầy đủ field bắt buộc, không có field ngoài schema.
- Các enum, kiểu dữ liệu và giới hạn số phần tử đúng schema.

### 2. Case và entity scope

- case_id của output khớp chính xác case đầu vào.
- Entity được kết luận là bị ảnh hưởng phải thuộc phạm vi case và có căn cứ từ dữ liệu đã xác minh.
- Không đưa entity từ case khác vào output.

### 3. Evidence và claim linkage

- Mọi evidence_ref được trích dẫn, kể cả trong claim_assessments, đều tồn tại trong kho evidence của case hiện tại.
- Evidence hỗ trợ đúng claim hoặc kết luận được gắn.
- Khi có claim_assessments, claim_id phải khớp claim đầu vào.
- Không coi lời khách hàng khai là bằng chứng MCP.
- Không xem việc evidence_ref đúng định dạng là đủ để xác nhận
  provenance hợp lệ.

### 4. Financial consistency

- Tính toán tiền nội bộ bằng Decimal, làm tròn theo policy áp dụng.
- currency là BRL.
- Các khoản hoàn tiền không âm.
- recommended_refund_brl bằng tổng amount_brl trong refund_lines.
- Không tính hoàn trùng một khoản.
- Mỗi khoản hoàn có căn cứ từ bằng chứng và chính sách.
- Khi tạo output, chuyển giá trị tiền thành JSON number phù hợp; không xuất Decimal dưới dạng chuỗi.

### 5. Business consistency

- primary_issue, case_status và resolution_actions không mâu thuẫn.
- ranked_causes có căn cứ và thứ hạng không trùng nhau.
- responsible_parties phù hợp bằng chứng về trách nhiệm.
- Không quy trách nhiệm cho một bên khi chưa có đủ căn cứ.
- Nếu chọn selected_source trong data_conflicts, nguồn đó phải nằm trong sources và việc lựa chọn phải có căn cứ.
- Nếu chưa giải quyết được xung đột, không giả vờ đã xác định được nguồn đúng.

### 6. Confidence

- Mọi confidence nằm trong khoảng từ 0 đến 1.
- Confidence phản ánh mức hỗ trợ của bằng chứng đối với kết luận.
- Không tự động đặt confidence cao chỉ vì output pass schema.

### 7. Kết quả verification

- Nếu đạt: emit verification_completed với decision_code = PASS.
- Nếu không đạt: emit verification_completed với decision_code = NEEDS_REWORK và trả danh sách lỗi cụ thể qua message nội bộ cho Coordinator.
- Coordinator chỉ giao bổ sung nếu còn ngân sách vòng và thời gian.
- Sau mọi chỉnh sửa, output phải được kiểm tra lại.
- Chỉ emit case_finalized khi output cuối cùng đã vượt qua verification.

Đây là thiết kế dự kiến. Kiểm tra schema đã có bộ hỗ trợ; các kiểm tra nghiệp vụ cần được triển khai thêm.

## 7. Reproducibility

### Nền tảng triển khai

- Python 3.11 trở lên theo yêu cầu của starter repo.
- Framework điều phối dự kiến: Python async state-machine.
- Điểm vào: `src/student_agent/workflow.py`, hàm `solve_case()`.
- Model LLM: chưa chốt. Khi sử dụng, ghi rõ model ID và các tham số thực tế; nếu không sử dụng thì ghi rõ không dùng LLM.
- Không ghi API key hoặc thông tin xác thực trong tài liệu và trace.

### Cấu hình chạy dự kiến

| Tham số | Giá trị |
| --- | --- |
| Số case xử lý đồng thời | 1 |
| Số MCP call đồng thời trong mỗi case | Tối đa 2 |
| Deadline toàn bộ solve_case | 180 giây |
| Timeout mỗi lần gọi MCP | Tối đa 30 giây, không vượt deadline còn lại |
| Retry cho lỗi MCP tạm thời | Tối đa 2 lần ngoài lần gọi đầu |
| Backoff trước các lần retry | 1 giây, 2 giây |
| Số vòng sửa hoặc bổ sung A2A | Tối đa 1 |

Đây là cấu hình mục tiêu, cần được triển khai và kiểm tra trong code.
Timeout của workflow được áp dụng bên ngoài `gateway.call()`;
không mặc định coi timeout HTTP có sẵn là timeout của workflow.

### Dependency và phiên bản

- Khi hoàn thiện triển khai, ghi phiên bản Python thực tế.
- Ghi phiên bản dependency thực tế và lưu bằng cơ chế pin/lock mà dự án sử dụng.
- Ghi commit source và `case_set_version` của lần chạy.
- Giữ nguyên public schemas đã phát hành.
- Nếu có sử dụng ngẫu nhiên, ghi seed và nơi áp dụng.
- Không cam kết kết quả LLM giống tuyệt đối giữa các lần chạy.

### Lệnh kiểm tra và chạy

Thực hiện tại root repo, sau khi đã cài đặt môi trường và cấu hình.

Kiểm tra input và discovery tool:

```powershell
day09 validate-inputs
day09 mcp-tools
```

Sau khi workflow đã được triển khai, chạy, kiểm tra kết quả và đóng gói:

```powershell
day09 run
day09 validate
day09 package --output dist/submission.zip
```

Không đưa `.env`, API key, source hoặc input vào ZIP nộp bài.

### Thông tin đã xác nhận

- Tên và arguments của 10 tool đã được xác nhận qua MCP discovery, xem mục 2.
- Việc xác nhận metadata chưa đồng nghĩa đã triển khai phân quyền tool hoặc kiểm tra cấu trúc dữ liệu trả về.

### Thông tin cần bổ sung sau khi triển khai

- Phiên bản Python và dependency thực tế.
- Model/config thực tế nếu sử dụng LLM.
- Commit source và `case_set_version` của lần chạy.
- Kết quả chạy validation và các giới hạn còn tồn tại.
## 8. Trạng thái triển khai

Tài liệu này được cập nhật cùng source. Mục này ghi phần nào của kiến trúc đã
được triển khai, phần nào còn ở trạng thái dự kiến, để các thành viên nối tiếp
có điểm xuất phát minh bạch.

### 8.1 Đã triển khai — Coordinator / Supervisor (Nguyễn Hải Đăng, TheDeepVoid)

| Thành phần | File | Ghi chú |
| --- | --- | --- |
| Intent analysis | `src/student_agent/intent.py` | Phân tích deterministic, không MCP, không LLM. Trích `case_id`, `claimed_order_id`, `policy_version`, claims; ánh xạ topic → hypothesis primary_issue; topic → các specialist domain cần thiết (`TOPIC_DOMAINS`, `TOPIC_HYPOTHESIS`). Topic lạ được báo trong `unknown_topics`, không crash. |
| A2A message envelope | `src/student_agent/messages.py` | `HandoffMessage` theo mục 3 (case_id, sender, recipient, task, entity_scope, facts, evidence_refs, status). Mở rộng nội bộ: `policy_version` (từ input, không đoán) và `output` (draft của policy dành cho verifier) — không đưa vào public output/trace. |
| Phân quyền tool | `src/student_agent/permissions.py` | Hằng số allowlist theo mục 2 cho coordinator/order/payment/shipment/policy/verifier; `assert_tool_allowed()`; `get_customer_history` không cấp cho ai. Việc *thực thi* trong agent thuộc task kế tiếp. |
| Agent registry + stubs | `src/student_agent/agents.py` | `SpecialistAgent` protocol, `AgentRegistry`, `build_default_registry()` với stub ném `NotImplementedError` kèm thông báo rõ ràng — không bịa facts/evidence_ref. |
| Coordinator loop | `src/student_agent/coordinator.py` | `Coordinator.run()`: phân tích intent → plan task theo domain → dispatch qua registry (concurrency tối đa 2, per-task timeout tối đa 30s, deadline toàn bộ 180s) → synthesize facts/evidence → handoff cho policy → verifier → tối đa 1 vòng bổ sung (SPECIALIST_REWORK) → trả output. Hết budget/ngân sách → báo lỗi xử lý case, không tạo kết quả giả. |
| Trace handoff | `src/student_agent/coordinator.py` | Emit `task_assigned`, `handoff`, `policy_decided`, `verification_completed` (PASS/NEEDS_REWORK). CLI giữ `case_received`/`case_finalized`; agent emit `tool_result_consumed`. |
| Điểm vào | `src/student_agent/workflow.py` | `solve_case()` tạo Coordinator với default registry. |

### 8.2 Chưa triển khai — task kế tiếp

| Thành phần | Trạng thái |
| --- | --- |
| Order/item, payment, shipment agents | Stub trong `agents.py`; cần triển khai theo `SpecialistAgent` protocol: gọi MCP qua `EvidenceGateway`, kiểm tra allowlist, emit `tool_result_consumed`, trả facts + evidence_refs thật. |
| Tích hợp MCP Evidence Gateway | Có sẵn `EvidenceGateway.call()`; agents cần gọi đúng tool đã discovery, đúng case_id, không tự tạo evidence_ref. |
| Policy agent (biz logic) | Stub; cần áp dụng `get_policy` với `policy_version` từ input (coordinator truyền qua `message.policy_version`), tạo draft theo `l3a-output-v2.schema.json`. |
| Verifier (biz invariants) | Stub; cần kiểm tra mục 6 (schema, entity scope, evidence ownership, claim linkage, tài chính, confidence). |

Trạng thái hiện tại: `day09 run` dừng ngay tại stub agent `order` với
`NotImplementedError` kèm hướng dẫn — không emits output giả. Khi task kế tiếp
hoàn tất agents và policy/verifier, `solve_case` sẽ chạy end-to-end mà không
cần đổi giao diện coordinator.

### 8.3 Domain grounding (Olist)

Dữ liệu tham khảo cục bộ: `/home/aminix/.cache/kagglehub/datasets/olistbr/brazilian-ecommerce/versions/2`
(Cảnh báo: chỉ là tham khảo nghiệp vụ để hiểu ý nghĩa field; dữ liệu có thẩm
quyền để kết luận là MCP Evidence Gateway, không phải CSV cục bộ.)

Các đặc trưng đã kiểm chứng bằng script trên toàn bộ dataset:

| Đặc trưng | Giá trị kiểm chứng | Ý nghĩa cho intent/domain |
| --- | --- | --- |
| `order_status` enum | delivered 96k, shipped 1.1k, invoiced 314, processing 301, unavailable 609, canceled 625, created 5, approved 2 | `canceled` và `unavailable` là status riêng biệt, tương ứng topic `canceled_order_paid` / `unavailable_order_paid`. Không có status "delay" — late delivery tính bằng so sánh `order_delivered_customer_date` vs `order_estimated_delivery_date` (8.11% delivered bị trễ). |
| Canceled orders | 625 order, **100% có payment rows**, 74% có item rows | `canceled_order_paid`: payment đã capture; câu hỏi là tiền có được hoàn không → cần domain order + payment (timeline/refund). |
| Unavailable orders | 609 order, **100% có payment rows**, chỉ 6 order có item rows | `unavailable_order_paid` khác biệt với canceled: product không khả dụng, payment đã capture → cần order + payment. |
| `payment_sequential` | 1..29, ~3k order có >1 payment row | Split payment là hợp lệ (topic `valid_split_payment`); nhiều sequential cùng order ≠ duplicate. |
| `payment_type`, installments | credit_card/boleto/voucher/debit_card/not_defined; installments 0..24 | `payment_mismatch`/`duplicate_charge` phải đối chiếu tổng payment_value theo từng payment row, không theo lời khai. |
| Refund data | Không có bảng refund trong dataset công khai | Evidence refund chỉ có qua MCP (`get_refund_timeline`); coordinator không bao giờ suy ra tiền hoàn từ CSV. |
| Sellers / order | ~1.3k order có ≥2 sellers (tối đa 5) | `responsible_parties` phải scoped theo seller/item; không quy trách nhiệm cho toàn order khi có nhiều seller. |
| Items / order | ~9.8k order có >1 item, mỗi item có `price` + `freight_value` | `recommended_refund_brl` theo item/seller, không double-count. |
| Milestone vận chuyển | `order_delivered_carrier_date` (bàn giao carrier = xong phần seller) vs `order_delivered_customer_date` (xong phần logistics) | Phân biệt `late_delivery_seller` vs `late_delivery_logistics`: nếu carrier_date gần/đúng hạn nhưng customer_date trễ → trách nhiệm logistics. |

Các bước phân tích ở mục 8.1 (TOPIC_DOMAINS, TOPIC_HYPOTHESIS) được thiết kế
theo đúng các đặc trưng trên. Khi task kế tiếp triển khai agents, ánh xạ tool
→ field dữ liệu nên dựa trên bảng này.
