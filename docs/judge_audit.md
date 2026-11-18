# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | đạt | dùng có giới hạn |
| helpful | 100 | 0.375 | 1.000 | 0.300 | không đạt | loại khỏi gate |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | HL-001 | PASS (judge) | FAIL (human) | Human | Câu chúc lịch sự nhưng không trả lời yêu cầu; thêm mục tiêu tác vụ vào rubric. |
| 2 | HL-003 | PASS (judge) | FAIL (human) | Human | “Gửi lại thông tin” không hỏi cụ thể mã đơn; yêu cầu câu hỏi làm rõ cụ thể. |
| 3 | HL-008 | PASS (judge) | FAIL (human) | Human | Câu trả lời thiếu thông tin cần thiết; rubric phân biệt lịch sự với hữu ích. |
| 4 | HL-012 | PASS (judge) | FAIL (human) | Human | Trả lời sai/lạc mục tiêu dù giọng điệu thân thiện; rubric cần kiểm tra độ liên quan. |
| 5 | HL-017 | FAIL (judge) | PASS (human) | Human | Câu ngắn vẫn giải quyết đúng yêu cầu; không buộc lời chào/câu kết mẫu. |

## Kết luận
- Loại `helpful`: dù P=1.000, R=0.300 và κ=0.375 dưới sàn; ma trận nhầm lẫn có 21 false negative (TP=9, FP=0, FN=21, TN=70), nên judge bỏ sót phần lớn câu trả lời con người gắn nhãn lỗi. Dùng `tone_ok` chỉ cho giọng điệu, không suy diễn thành độ đúng nghiệp vụ.
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật.
