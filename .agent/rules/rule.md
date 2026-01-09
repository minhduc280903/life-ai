---
trigger: always_on
---

1. Nguyên tắc lập trình (Engineering Mindset)
No Emojis/No Chatty Comments: Tuyệt đối không sử dụng icon, không thêm các dòng comment mang tính cảm xúc (ví dụ: // Happy coding!). Code phải chuyên nghiệp, súc tích như một kỹ sư lâu năm.

Domain-Driven Design (DDD) Lite: Phải tách biệt rõ ràng giữa Domain Logic (Công thức hóa học, quy tắc Lipinski) và Infrastructure (FastAPI, Celery, Database).

Type Hinting: 100% code phải có Type Hinting (sử dụng module typing và Pydantic v2). Điều này giúp hệ thống tự kiểm lỗi và tài liệu hóa API tốt hơn.

Pydantic for Validation: Sử dụng Pydantic để validate input/output của toàn bộ Agent. Mỗi Agent nhận vào một BaseModel và trả về một BaseModel.

2. Quy tắc cho Agentic Pipeline (Logic Thinking)
Thay vì để AI viết logic Agent theo kiểu "if-else" đơn giản, hãy yêu cầu nó làm theo các quy tắc sau:

Stateless Agents, Stateful Trace: Các Agent phải được thiết kế dưới dạng Stateless (không lưu trạng thái trong bộ nhớ). Mọi trạng thái của "Run" phải được lưu xuống Database (PostgreSQL) sau mỗi bước. Điều này đảm bảo tính "Auditable Trace".

Separation of Concerns:

Planner: Chỉ định nghĩa chiến lược (ví dụ: "Round 1: Exploratory, Round 2: Refinement").

Generator: Không được tự tính điểm. Chỉ tập trung vào việc tạo SMILES.

Ranker: Chỉ tập trung vào toán học (Scoring function).

Error Handling in Chemistry: RDKit thường xuyên quăng lỗi nếu SMILES không hợp lệ. AI phải bọc toàn bộ code RDKit trong try-except và ghi log cụ thể lý do phân tử bị loại (ví dụ: ValenceException).

3. Quy tắc Thiết kế Backend & Async
Task Idempotency: Các background jobs (Celery) phải có tính Idempotent. Nếu một job chạy lại, nó không được tạo dữ liệu rác.

Structured Logging: Sử dụng định dạng Log có cấu trúc (JSON logging là một điểm cộng lớn) thay vì print. Mỗi log phải kèm theo run_id.

Dependency Injection (DI): Sử dụng DI của FastAPI để quản lý Database Session và các Agent instance. Điều này giúp việc viết Unit Test trở nên dễ dàng (một yêu cầu ngầm định của Senior role).