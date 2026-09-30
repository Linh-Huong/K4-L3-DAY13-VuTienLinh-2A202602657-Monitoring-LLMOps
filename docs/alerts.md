# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` liên tục trong 5 phút
- Ảnh hưởng tới người dùng: Người dùng phải chờ lâu hơn bình thường để nhận phản hồi từ chatbot/AI
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard tại `/dashboard` (panel Latency) để xác nhận khoảng thời gian và mức độ tăng của P95/P99.
  2. Lọc `data/logs.jsonl` trong khung giờ đó, chọn một `correlation_id` có `latency_ms` cao bất thường.
  3. Mở trace có cùng `correlation_id` trên Langfuse, so sánh thời gian của span `retrieval` và span `generation` để xác định bước gây nghẽn cổ chai.
- Mitigation tạm thời: Nếu do prompt mới làm LLM sinh câu trả lời quá dài, thực hiện rollback prompt về version cũ; nếu do tài nguyên vector store, tạm thời chuyển sang fallback document cache hoặc hạ tải concurrency.
- Owner: `student-2A202602657`

## Alert 2

- Tên: `HighErrorRate`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Error rate của toàn bộ API requests (`request_failed / request_received`)
- Điều kiện và thời gian duy trì: `error_rate_pct > 2%` liên tục trong 5 phút
- Ảnh hưởng tới người dùng: Người dùng nhận mã lỗi HTTP 500 hoặc không nhận được câu trả lời từ hệ thống
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard (panel Errors) để kiểm tra biểu đồ error rate và phân loại lỗi trong `error_breakdown`.
  2. Tìm các dòng log có `event == "request_failed"` trong `data/logs.jsonl`, đọc `error_type` và thông điệp lỗi trong `payload.detail`.
  3. Mở trace tương ứng trên Langfuse để xem traceback đầy đủ tại span bị lỗi.
- Mitigation tạm thời: Khởi động lại dịch vụ hoặc kích hoạt circuit breaker; nếu do LLM/API key bên ngoài hết hạn hoặc timeout, chuyển hướng lưu lượng sang mô hình dự phòng.
- Owner: `student-2A202602657`

## Alert 3

- Tên: `RetrievalFailureRate`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Tỷ lệ tìm kiếm context thành công (`tool_success == true` của tool `retrieval`)
- Điều kiện và thời gian duy trì: `retrieval_success_rate_pct < 90%` liên tục trong 5 phút
- Ảnh hưởng tới người dùng: Chatbot trả lời chung chung (fallback answer) do thiếu tài liệu tham khảo chính xác từ cơ sở tri thức
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard (panel Errors) quan sát đường `Retrieval Success (%)`.
  2. Lọc log kiểm tra các event có `tool_name == "retrieval"` và `tool_success == false`.
  3. Tìm kiếm trace ID trên Langfuse để xem span `retrieval` bị exception gì (ví dụ: `Vector store timeout`, kết nối database lỗi).
- Mitigation tạm thời: Kiểm tra trạng thái vector store / database tài liệu; nếu service retrieval đang gặp sự cố, tạm thời kích hoạt chế độ trả lời bằng static knowledge base.
- Owner: `student-2A202602657`
