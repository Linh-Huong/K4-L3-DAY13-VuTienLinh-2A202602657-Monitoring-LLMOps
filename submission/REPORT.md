# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Vũ Tiến Linh
- **MSSV:** 2A202602657
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/Linh-Huong/K4-L3-DAY13-VuTienLinh-2A202602657-Monitoring-LLMOps
- **Commit SHA cuối:** 61a34f827748393ced851ea7c9b412dd53dced23
- **Challenge ID:** day13-k4-l3b-monitoring-llmops-v1
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602657`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | Đạt toàn bộ contract schema, log enrichment và PII scrubbing |
| `validate_dashboard.py` | 6/6 panel | 6/6 panel | Đạt đủ contract 6/6 panel theo config/dashboard.yaml |
| `pytest` | 22 passed | 26 passed | 26/26 unit tests passed (gồm 4 tests PII mở rộng kiểm tra CCCD, thẻ, passport và multiple PII) |
| Số traces hợp lệ | 0 | 15+ traces | Đã tích hợp Langfuse tracing với child spans và correlation_id chuẩn xác |
| Số PII leak | 0 | 0 | Toàn bộ CCCD, số thẻ tín dụng, hộ chiếu, email, phone đều được che bằng [REDACTED] |
| Latency P95 / TTFT P95 | 1501 ms / 50 ms | 160 ms / 50 ms | Hệ thống phản hồi nhanh, ổn định trong điều kiện vận hành bình thường |
| Retrieval success rate | 100% (10/10) | 100% | 100% request retrieval thành công khi không có sự cố |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:**
  Được xử lý tập trung trong `CorrelationIdMiddleware` (`app/middleware.py`). Khi request đến, middleware đọc header `X-Request-ID`. Nếu header có giá trị, middleware tái sử dụng giá trị đó làm correlation ID; nếu không có, middleware tự sinh mới theo định dạng `f"req-{uuid.uuid4().hex[:8]}"`. Correlation ID được lưu vào `request.state.correlation_id` và bind vào `structlog.contextvars` qua `bind_contextvars(correlation_id=...)` để tự động đính kèm vào mọi log event trong suốt request lifecycle. Sau khi xử lý xong, correlation ID được chèn vào response header `X-Request-ID` cùng với `X-Response-Time-Ms`.
- **Các metadata được ghi vào structured log:**
  - Request-level context: `service` ("api"), `correlation_id` (ví dụ `req-5bf6f7f3`), `user_id_hash` (chuỗi hex SHA256 12 ký tự), `session_id`, `feature`, `model`, `env` ("dev"/"prod").
  - Event-level metrics: `event` (`request_received`, `response_sent`, `request_failed`), `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name` ("retrieval"), `tool_success` (true/false), và `payload` (chứa preview tóm tắt).
- **Cách bảo đảm PII được scrub trước khi ghi:**
  Tích hợp bộ xử lý `scrub_event` vào processor chain của structlog trong `app/logging_config.py` trước khi render ra JSON. Hàm `scrub_event` gọi `_scrub_value()` duyệt đệ quy qua toàn bộ dict/list trong event dict (gồm cả event name và payload) và áp dụng hàm `scrub_text()` từ `app/pii.py`. Hàm `scrub_text()` áp dụng các biểu thức chính quy (regular expressions) để nhận diện và thay thế:
  - CCCD/CMND Việt Nam (12 số liên tiếp): `[REDACTED_CCCD]`
  - Số thẻ ngân hàng/tín dụng (16 số): `[REDACTED_CREDIT_CARD]`
  - Số hộ chiếu Việt Nam (1 chữ cái theo sau bởi 7-8 số): `[REDACTED_PASSPORT]`
  - Email và số điện thoại Việt Nam: `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`
- **Cách kiểm chứng kết quả:**
  - Chạy `python scripts/validate_logs.py`: đạt 100/100 điểm, 0 PII leak detected.
  - Chạy `pytest tests/test_pii.py`: vượt qua toàn bộ 4 test case kiểm thử đơn vị che CCCD, thẻ, passport và hỗn hợp nhiều PII.
  - Kiểm tra trực tiếp file `data/logs.jsonl`: không có dữ liệu PII nhạy cảm ở dạng plain-text.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
  Mọi trace được gửi về project Langfuse cá nhân `day13-k4-l3b-2A202602657` (khớp với MSSV `2A202602657` của tôi). Tên project hiển thị rõ ràng trên góc giao diện Langfuse (minh chứng trong `evidence/06-trace-list.png`). Mỗi trace có metadata `correlation_id` khớp chính xác với `correlation_id` trong file `data/logs.jsonl` được tạo ra trên máy local của tôi.
- **Cấu trúc root/retrieval/generation observations:**
  Mô hình cây quan sát (Observation Tree) tuân thủ đúng chuẩn Langfuse:
  1. **Root Span:** `lab-agent-run` (type `agent`), bao bọc toàn bộ chu trình xử lý request.
  2. **Child Span 1:** `retrieval` (type `retriever`), con trực tiếp của `lab-agent-run`, đo thời gian truy vấn mock RAG và số lượng document trả về.
  3. **Child Span 2:** `generation` (type `generation`), con trực tiếp của `lab-agent-run`, ghi nhận model name (`claude-sonnet-4-5`), prompt template sử dụng, số lượng input/output tokens và chi phí tính toán `cost_usd`.
- **Cách nối trace với log:**
  Log và Trace được liên kết chặt chẽ thông qua `correlation_id` (dạng `req-[8hex]`). `CorrelationIdMiddleware` sinh hoặc nhận `correlation_id`, sau đó giá trị này được structlog ghi vào trường `correlation_id` trong từng dòng JSON của `data/logs.jsonl`, đồng thời được gắn vào metadata của root span `lab-agent-run` và child span `generation` trên Langfuse. Khi gặp sự cố hoặc cần tra cứu, kỹ sư chỉ cần lấy `correlation_id` từ log và tìm kiếm trên ô Search Metadata của Langfuse để mở ngay trace tương ứng.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** Version 1, mang label `baseline` (và ban đầu là `production`).
- **Version/label candidate:** Version 2 (nội dung có thêm chỉ dẫn "trả lời ngắn gọn"), mang label `candidate`.
- **Trace ID của mỗi version:**
  - **Baseline (Version 1, label `baseline`):** `b6dec6f7a42efeb45e699fe73e90dc12`
  - **Candidate (Version 2, label `candidate`):** `a4090e198a36178d0420b6a01c437969`
- **Cách promote và rollback `production`:**
  - **Cơ chế:** Ứng dụng luôn nạp prompt thông qua con trỏ label `production` (`client.get_prompt("day13-chat", label="production")`). Việc cập nhật prompt không yêu cầu chỉnh sửa mã nguồn hay deploy lại ứng dụng.
  - **Promote:** Sau khi kiểm thử Version 2 (candidate) với trace `a4090e198a36178d0420b6a01c437969` cho kết quả tốt, ta truy cập giao diện Langfuse > Prompts > `day13-chat`, gán label `production` cho Version 2. Ứng dụng sẽ tự động sử dụng version 2 cho các request tiếp theo.
  - **Rollback:** Nếu Version 2 gặp sự cố hoặc suy giảm chất lượng, thao tác rollback được thực hiện ngay lập tức trên UI bằng cách gán lại label `production` trỏ về Version 1. Quá trình rollback diễn ra tức thì mà không gây gián đoạn hệ thống.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dựng dashboard runtime tại `/dashboard` đọc dữ liệu từ `data/logs.jsonl` gồm đúng 6 panel theo `config/dashboard.yaml`: (1) Latency (P50, P95, P99, TTFT P95 kèm SLO line 3000ms); (2) Traffic (Request rate / phút); (3) Errors (Error rate và Retrieval success rate); (4) Cost (Chi phí USD tích lũy); (5) Tokens (Input & Output tokens); (6) Quality (Điểm chất lượng câu trả lời trung bình).
- **SLO và lý do chọn:** Chọn primary SLO `fast_successful_requests` với target 99.5% trong cửa sổ 28 ngày (`good_event: event == "response_sent" and latency_ms <= 3000`, `total_event: event == "request_received"`). Lý do chọn: Dựa trên baseline ban đầu P95 ~1501ms và trạng thái vận hành ổn định (~160ms), ngưỡng 3000ms là phù hợp cho ứng dụng AI/LLM interactive, vừa đảm bảo SLA cho người dùng vừa đủ dung sai cho mạng và retrieval.
- **Cách tính error budget:** Với target SLO 99.5%, error budget là 0.5% (100% - 99.5%). Nếu workload trong 28 ngày có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO (10,000 * 0.5% = 50 requests). Nếu số request vi phạm vượt quá 50, error budget bị burn hết, kích hoạt chính sách đóng băng deploy tính năng mới để tập trung fix reliability.
- **Ba alert và runbook tương ứng:**
  1. `HighLatencyP95` (Warning, 5m): Khi P95 latency > 3000ms trong 5 phút. Runbook tại `docs/alerts.md#alert-1` hướng dẫn mở dashboard latency, lọc correlation_id chậm và mở trace Langfuse để xác định span nghẽn.
  2. `HighErrorRate` (Critical, 5m): Khi tỷ lệ lỗi > 2% trong 5 phút. Runbook tại `docs/alerts.md#alert-2` hướng dẫn phân tích error_breakdown, lọc log request_failed và kiểm tra traceback trace để kích hoạt failover/circuit breaker.
  3. `RetrievalFailureRate` (Warning, 5m): Khi tỷ lệ retrieval thành công < 90% trong 5 phút. Runbook tại `docs/alerts.md#alert-3` hướng dẫn kiểm tra trạng thái vector store và chuyển sang fallback document cache.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** 12:31:48 – 12:32:05 (UTC: `05:31:48Z` – `05:32:05Z`) ngày 30/09/2026.
- **Triệu chứng từ metrics:** Panel 1 (Latency percentiles and TTFT) trên Dashboard cho thấy latency vọt cao bất thường lên `2652 - 2653 ms` (vượt ngưỡng challenge threshold 2000ms và gấp hơn 16 lần so với baseline bình thường ~156 - 160ms). Trong khi đó, TTFT P95 vẫn giữ nguyên 50ms, Error rate là 0%, Cost và Tokens không có biến động bất thường.
- **Log line và correlation ID liên quan:** Lọc `data/logs.jsonl` trong khoảng thời gian trên, phát hiện request bị ảnh hưởng có `correlation_id = req-5bf6f7f3`:
  ```json
  {"service": "api", "latency_ms": 2653, "ttft_ms": 50, "tokens_in": 36, "tokens_out": 81, "cost_usd": 0.001323, "quality_score": 0.9, "tool_name": "retrieval", "tool_success": true, "payload": {"answer_preview": "Starter answer. You should improve this output logic and add better quality chec..."}, "event": "response_sent", "feature": "monitoring", "env": "dev", "session_id": "k4-l3b-challenge-s04", "model": "claude-sonnet-4-5", "user_id_hash": "c3a24a72d92a", "correlation_id": "req-5bf6f7f3", "level": "info", "ts": "2026-09-30T05:32:02.053314Z"}
  ```
- **Trace ID và span gây ảnh hưởng:** Mở trace tương ứng trên Langfuse có cùng `correlation_id = req-5bf6f7f3` (`Trace ID: 12d998304a215085477dee0009f33538`). So sánh latency giữa các span con trong cây:
  - Span `retrieval`: latency lên tới **2.503s** (chiếm 94.3% tổng thời gian request).
  - Span `generation`: latency chỉ **0.152s** (rất nhanh và bình thường).
  - Span `lab-agent-run`: total latency là **2.655s**.
  - Kết luận: Span gây chậm trực tiếp là span `retrieval`.
- **Root cause:** Module tìm kiếm tài liệu (vector store retrieval) gặp sự cố suy giảm hiệu năng nghiêm trọng (bị trễ 2.5s khi xử lý các truy vấn thuộc feature `monitoring`), dẫn tới toàn bộ thời gian xử lý request tăng vọt từ ~160ms lên 2653ms. LLM generation vẫn phản hồi nhanh bình thường.
- **Fix action:** 
  1. Tắt chế độ sự cố bằng lệnh `python scripts/inject_incident.py --disable` (hoặc gọi API `/incidents/rag_slow/disable`).
  2. Khôi phục dịch vụ vector database / restart cluster; trong môi trường production, tạm thời bật cache kết quả tìm kiếm ngữ cảnh (semantic cache) hoặc chuyển sang secondary vector replica để giảm tải ngay lập tức.
- **Preventive measure:**
  1. Cài đặt Alert cảnh báo sớm khi latency của span `retrieval` vượt quá 1000ms trong 3 phút liên tục.
  2. Bổ sung cấu hình hard timeout cho thao tác retrieval (ví dụ: `timeout = 1.0s`): nếu retrieval quá 1s không phản hồi, tự động ngắt và kích hoạt fallback trả lời bằng static knowledge base thay vì để người dùng chờ đợi quá lâu.
  3. Áp dụng Circuit Breaker pattern cho kết nối tới cơ sở dữ liệu vector.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
  Tách riêng bộ xử lý PII scrubbing `scrub_event` thành structlog processor độc lập và tái cấu trúc regex bằng lookahead/boundary rõ ràng. Điều này đảm bảo toàn bộ payload, log message và context metadata đều được làm sạch trước khi ghi ra đĩa hoặc xuất ra terminal, loại bỏ rủi ro rò rỉ thông tin cá nhân (PII) dù log được gọi ở bất kỳ tầng nào của ứng dụng.
- **Một lỗi/blocker đã gặp:**
  Uvicorn với cờ `--reload` mặc định chỉ theo dõi thay đổi trong các file Python (`.py`), không tự động reload khi sửa file cấu hình `.env` (ví dụ khi chuyển đổi `LANGFUSE_PROMPT_LABEL=baseline` sang `candidate`). Điều này khiến request vẫn sử dụng cấu hình cũ nếu không khởi động lại server.
- **Cách tìm nguyên nhân và xử lý:**
  Phát hiện qua việc kiểm tra giá trị `prompt_label` trong metadata của trace Langfuse vẫn giữ nguyên `production` sau khi đã sửa `.env`. Xử lý bằng cách bổ sung cơ chế kiểm tra `load_dotenv(override=True)` trong `CorrelationIdMiddleware` khi chạy môi trường dev (loại trừ khi chạy test pytest), giúp cấu hình môi trường luôn được đồng bộ ngay lập tức cho từng request mà không cần restart server thủ công.
- **Cách hiểu luồng Metrics → Logs → Traces:**
  - **Metrics**: Cho cái nhìn vĩ mô (tín hiệu cảnh báo sớm) xem hệ thống có đang khỏe mạnh không, panel nào bị đột biến (ví dụ P95 latency tăng vọt lên 2653ms).
  - **Logs**: Thu hẹp phạm vi vào thời điểm xảy ra sự cố, lọc các sự kiện bất thường để lấy ngữ cảnh và định danh cụ thể (`correlation_id = req-5bf6f7f3`).
  - **Traces**: Đi sâu vào vi mô (từng hàm/span trong vòng đời xử lý request) bằng cách tra cứu theo `correlation_id` để nhìn thấy biểu đồ thác nước (waterfall chart), từ đó định vị chính xác span nào tiêu tốn thời gian nhất (span `retrieval` 2.503s vs `generation` 0.152s).
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
  - Prompt versioning & label abstraction phân tách việc quản lý logic prompt khỏi chu kỳ release mã nguồn, cho phép A/B testing và rollback tức thì khi prompt mới gây hallucination hoặc suy giảm chất lượng.
  - Token/cost monitoring giúp phát hiện sớm các query bất thường hoặc prompt loop làm cạn kiệt ngân sách.
  - SLO và Error budget đặt ra ranh giới định lượng giữa tốc độ phát triển tính năng và độ ổn định của hệ thống.
- **Điều quan trọng nhất đã học:**
  Kỹ năng xây dựng hệ thống quan sát toàn diện (Observability) cho ứng dụng LLM không chỉ dừng lại ở việc ghi log truyền thống, mà phải kết hợp chặt chẽ giữa Structured Logging, Tracing đa tầng (Child Spans) và Metrics Dashboard để có thể phát hiện và khắc phục sự cố nhanh chóng theo quy trình chuẩn.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**
  Hiện tại hệ thống mock RAG và LLM chạy trên giả lập local; nếu triển khai môi trường production quy mô lớn, cần tích hợp OpenTelemetry Collector phân tán và cài đặt Semantic Cache cho vector search để tối ưu chi phí và độ trễ.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [x] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.

