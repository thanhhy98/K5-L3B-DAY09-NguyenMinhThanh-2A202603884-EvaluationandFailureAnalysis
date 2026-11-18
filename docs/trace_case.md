# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `<shape> <claim>@<seed>`, run ID trong report |
| Triệu chứng | Grader nào fail; reply nói gì so với ledger ghi gì |
| Bước sai đầu tiên | Số thứ tự event + kind + trích payload (≤1 dòng) |
| Vì sao là bước *đầu tiên* | Các bước trước đó đúng ra sao (dẫn số event) |
| Failure mode | Mã FM-xx trong `docs/failure_taxonomy.md` |
| Đối chứng | Cùng claim@seed trên shape `fixed`: bước đó khác thế nào |
| Regression test | Tên test + grader/assert nào bắt được; đã thấy fail trên variant lỗi và pass trên `fixed` chưa |
| Chưa chắc chắn | Điều trace không chứng minh được |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
# Regression case — ticket claims override database facts

**Trial:** `seeded_regression`, C-002@11. Reproduce with `python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11`.

- **Symptom:** Lab 8 grader fails (`status resolved != denied`); ledger records 20,000 VND and one refund while the label requires 0 VND and zero refunds.
- **First incorrect step:** event 3, `model_override`, payload `{"delay_days": 5}`. The investigator had already read the verified database value of 2 days in event 2; event 3 replaces it with the ticket's claim of 5 days.
- **Why it is first:** the handoff and read-only lookup complete before the override; the quote and refund are downstream consequences of the substituted delay.
- **Failure mode:** FM-03 (`ticket_trust`).
- **Regression assertion:** `DbFactKept` must fail when the trace contains `model_override`; `pass_rate` must fail against the C-002 label. `fixed` must not emit the override and must match the zero refund label.
- **Limit:** this replay establishes behavior for this public fixture and seed; it does not estimate behavior on real language models.
