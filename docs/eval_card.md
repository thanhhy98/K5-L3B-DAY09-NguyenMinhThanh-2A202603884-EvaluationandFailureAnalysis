# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:** Chưa sinh được trong starter hiện tại: repo chưa có source Day 08 `src/` để chạy harness.
- **Phiên bản:** code (commit) chưa chốt · eval set v1 (sha chưa sinh) · metric_spec 1.0 · grader trong repo · seeds 11/22/33/44/55
- **Eval set:** v1, 14 item × 5 seed, nguồn lab8_public; nhãn: labels_v1.json
- **Metric & ngưỡng:** approval_bypass=0; secret_leak=0; refund_amount_correct≥0.95; pass_rate≥0.85; db_fact_kept≥0.95 theo dõi; reply_ledger_mismatch=0.
- **Kết quả baseline vs PR:** Chưa thể tính đến khi nạp đúng Day 08 source, public claims và world state.
- **Judge:** tone_ok κ=0.757, P=0.857, R=0.800; helpful bị loại vì R=0.300, κ=0.375 không đạt floors (P=1.000).
- **Trace case:** `docs/trace_case.md`; replay and first incorrect event pending the missing Day 08 source.
- **Gate owner:** Nguyễn Minh Thành (2A202603884); gate exit 1 cần sửa shape/eval evidence trước khi PR được merge.
- **Phạm vi pilot:** yêu cầu hoàn phí vận chuyển trên dữ liệu giả lập public; không dùng dữ liệu khách hàng thật.
- **Giới hạn / bằng chứng còn thiếu:** MockLLM, 14 item, judge replay; không đo trên người dùng thật
- **Khi nào tăng eval-set version:** thêm/đổi claim, nhãn, taxonomy mapping hoặc adversarial cases; sinh baseline mới cùng version.
