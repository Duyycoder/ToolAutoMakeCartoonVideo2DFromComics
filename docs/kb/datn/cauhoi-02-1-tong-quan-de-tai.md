# 1. Tổng quan đề tài

Thông điệp xuyên suốt: không mô hình AI nào tự biến truyện thành video; phần khó là điều phối nhiều mô hình trên máy 6 GB VRAM sao cho quan sát được, dừng được, chạy lại được.

## 1.1 Em giới thiệu đề tài trong 30 giây.
- **Mức:** ★
- **Ý trả lời chính:** Truyện chữ → dịch bằng LLM local → TTS → LLM chia cảnh + viết prompt → Stable Diffusion sinh ảnh có khóa phong cách/nhân vật → ffmpeg dựng video từng chương + video tổng. Orchestrator FastAPI điều phối các subprocess, chạy trên máy 6 GB VRAM.
- **Tra ở:** ch00 §1, ch14 Q1

## 1.2 Tên đề tài đầy đủ là gì? "Platform đa tiến trình" nghĩa là gì?
- **Mức:** ★
- **Ý trả lời chính:** "Xây dựng platform đa tiến trình cho quy trình tự động sản xuất video hoạt hình 2D từ truyện chữ bằng các mô hình AI local". Đa tiến trình = mỗi bước nặng chạy thành một process OS riêng, không phải đa luồng trong một process.
- **Tra ở:** ch00 §1

## 1.3 Bìa báo cáo ghi "FLATFORM"?
- **Mức:** ★★
- **Ý trả lời chính:** Nhận là lỗi đánh máy trên bìa; lời cam đoan và nội dung viết đúng "platform".
- **Tra ở:** ch00 §1

## 1.4 Repo tên `...FromComics` (truyện tranh) mà đề tài là truyện chữ?
- **Mức:** ★★
- **Ý trả lời chính:** Tên repo đặt từ giai đoạn ý tưởng ban đầu; phạm vi đã chốt là truyện chữ vì nguồn dễ lấy, cần sinh cả hình lẫn tiếng. (Kiểm lại câu này cho khớp lịch sử thật của em.)
- **Tra ở:** —

## 1.5 Vì sao chọn đề tài này?
- **Mức:** ★
- **Ý trả lời chính:** Truyện chữ/truyện dịch nhiều người đọc, nhu cầu nghe-nhìn lớn; làm tay tốn công theo số chương (mỗi chương hàng chục cảnh). Giải pháp có sẵn: dịch vụ online (phí, lộ dữ liệu), ComfyUI (không quản lý truyện nhiều chương), script rời (không có trạng thái). Khoảng trống: nền tảng cục bộ có trạng thái.
- **Tra ở:** ch00 §4, Q2

## 1.6 Bài toán khó ở đâu?
- **Mức:** ★
- **Ý trả lời chính:** Truyện chữ thiếu thông tin máy cần: cảnh dài bao lâu, có ai, ở đâu, góc máy, nhân vật trông ra sao. Hệ thống phải tự sinh phân cảnh, prompt, hồ sơ nhân vật, timeline trước khi sinh ảnh và âm.
- **Tra ở:** ch00 §4.1

## 1.7 Đầu vào, đầu ra, dữ liệu trung gian cụ thể?
- **Mức:** ★
- **Ý trả lời chính:** Vào: thư mục `.md/.txt` , URL nguồn hỗ trợ, hoặc chủ đề cho AI viết. Ra: `video/<chương>.mp4` + `video/TongHop_<timestamp>.mp4` . Trung gian: `.md [VI]` , `glossary.json` , `.wav` , `context.json` , `state.json` , `generated_from_script.srt` , `draft_frames/` , `final_frames/` .
- **Tra ở:** ch00 §5.4, Q3

## 1.8 Mục tiêu và phạm vi? Ngoài phạm vi là gì?
- **Mức:** ★
- **Ý trả lời chính:** Pipeline có trạng thái từ truyện đến MP4; mỗi bước quan sát/dừng/chạy lại được; Windows + GPU NVIDIA 6 GB. Ngoài phạm vi: nhiều người dùng, xác thực, phân quyền, cloud, animation chuyển động thật (AnimateDiff/SVD).
- **Tra ở:** ch00 §4.2

## 1.9 Đóng góp chính của em?
- **Mức:** ★
- **Ý trả lời chính:** (1) Điều phối đa tiến trình/VRAM có checkpoint; (2) pipeline ảnh có kiểm soát: style lock, LoRA, IP-Adapter, Studio có cổng chất lượng; (3) trợ lý AI local có cổng GPU + tra cứu 0- VRAM. Kèm: dịch 2 tầng Zero Tolerance, sáng tác có rolling summary. Điều phối là đóng góp chắc nhất.
- **Tra ở:** ch00 §4.3, Q4

## 1.10 Mô hình đều của người khác, vậy đóng góp của em ở đâu?
- **Mức:** ★★
- **Ý trả lời chính:** Tầng điều phối và ghép nối: kiến trúc đa tiến trình, giao thức JSON Lines + SSE, checkpoint/resume, style lock, kiểm bất biến khi chia cảnh, dịch 2 tầng, batch 2-pass, chatbot có cổng GPU. Tự train LoRA phong cách `thuy_mac` .
- **Tra ở:** ch00 câu 2

## 1.11 Hệ thống dành cho ai?
- **Mức:** ★
- **Ý trả lời chính:** Người làm nội dung một mình trên máy cá nhân: nạp truyện, chọn giọng/phong cách, theo dõi log, duyệt kết quả trung gian, chạy lại bước lỗi. Hỗ trợ, không thay thế họa sĩ/biên tập.
- **Tra ở:** Q6

## 1.12 Chạy trên phần cứng nào? Tối thiểu bao nhiêu?
- **Mức:** ★
- **Ý trả lời chính:** Windows 10/11 + GPU NVIDIA. Máy đo RTX 3060 Laptop 6 GB. `hardware_adapter.py` : ≥ 7 GB → `cuda_high` ; < 7 GB → `cuda_low` (fp16 + CPU offload + VAE slicing); không CUDA → CPU fp32 (rất chậm).
- **Tra ở:** Q7, ch13

## 1.13 Phương pháp nghiên cứu? Các giả thuyết H1– H5 đã kiểm chứng chưa?
- **Mức:** ★★
- **Ý trả lời chính:** Nghiên cứu thiết kế (design science): xác định vấn đề → đề xuất kiến trúc → nguyên mẫu → quan sát → tinh chỉnh. H4, H5 kiểm chứng một phần; H1–H3 (Studio, LoRA/IP-Adapter, unify) chưa kiểm chứng định lượng.
- **Tra ở:** Q8, báo cáo 2.9, 5.6

## 1.14 Luồng 4 bước gồm gì?
- **Mức:** ★
- **Ý trả lời chính:** Bước 1 nguồn truyện + dịch; Bước 2 sinh giọng; Bước 3 dựng hoạt hình (chia cảnh, prompt, sinh ảnh, upscale, dựng video); Bước 4 ghép video tổng. Autosub là công cụ rời.
- **Tra ở:** ch00 §5

## 1.15 Vì sao UI ghi "Bước 4" mà code gọi `step5` ?
- **Mức:** ★★
- **Ý trả lời chính:** Lịch sử: step4 là Autosub, đã tách thành tab rời; ghép video giữ tên nội bộ step5. Ánh xạ `DISPLAY_NO=` `{1:1,2:2,3:3,5:4}` ( `auto_run.py:20` ) và `INTERNAL_STEP_BY_DISPLAY {4:5}` ( `app.js:402` ).
- **Tra ở:** ch00 câu 9

## 1.16 Có thật chạy local 100% không?
- **Mức:** ★★
- **Ý trả lời chính:** Có thể offline hoàn toàn: nguồn local/ai_write, dịch Ollama, TTS Piper/Kokoro/VieNeu/XTTS. Mặc định TTS là Edge (online) vì nhanh, giọng tự nhiên; Gemini là tùy chọn. Phép đo trong báo cáo dùng Piper.
- **Tra ở:** ch00 câu 10, §7 dòng 5

## 1.17 Một chương chạy mất bao lâu?
- **Mức:** ★
- **Ý trả lời chính:** Piper ≈ 2,7 phút/chương; Bước 3 ≈ 2,6 phút cho video 45 s (≈ 3,47× thời lượng) trên RTX 3060 Laptop. Bước 1 chưa tổng hợp thời gian trung bình.
- **Tra ở:** ch00 câu 11

## 1.18 Gọi là "hoạt hình 2D" nhưng thực ra là slideshow?
- **Mức:** ★★★
- **Ý trả lời chính:** Đúng, nói thẳng: mỗi cảnh là ảnh tĩnh giữ theo thời lượng lời đọc, cắt cứng, không có zoompan/xfade. Lý do: video diffusion cần VRAM lớn hơn 6 GB nhiều và rất chậm. Hướng gần: filter `zoompan` (Ken Burns) + `xfade` của ffmpeg, gần như không tốn GPU.
- **Tra ở:** Q5, ch11

## 1.19 So với ComfyUI hơn gì?
- **Mức:** ★★
- **Ý trả lời chính:** ComfyUI mạnh cho một ảnh/workflow, nhưng không quản lý truyện nhiều chương, không có dịch, TTS, dựng theo thời lượng, checkpoint theo chương. Đánh đổi: kém linh hoạt khi đổi mô hình.
- **Tra ở:** Q62

## 1.20 So với Runway, Pika, Sora (text-to-video online)?
- **Mức:** ★★
- **Ý trả lời chính:** Online ra clip chuyển động thật nhưng ngắn, khó giữ nhân vật qua nhiều cảnh, tốn phí, gửi dữ liệu ra ngoài, không có chuỗi truyện → giọng đọc. Hệ thống của em miễn phí, cục bộ, giữ nhân vật, nhưng chỉ ra ảnh tĩnh.
- **Tra ở:** Q63

## 1.21 Khác gì MoneyPrinterTurbo?
- **Mức:** ★★
- **Ý trả lời chính:** Một phần MediaComposer ( `video.py` , `composer.py` , `material.py` ) kế thừa kiểu MoneyPrinterTurbo cho luồng stock footage/Autosub. Luồng truyện → hoạt hình ( `storytelling/` , `studio/` , batch runner, style lock, LoRA) là phần em xây mới. Nói rõ ranh giới.
- **Tra ở:** Q64

## 1.22 Phần nào em tự viết, phần nào là thư viện?
- **Mức:** ★★★
- **Ý trả lời chính:** Thư viện/mô hình: FastAPI, Selenium, BS4, Ollama + Qwen/HY-MT2, engine TTS, diffusers + SD1.5, Hyper-SD, IP- Adapter, peft, Real-ESRGAN, rembg, faster-whisper, ffmpeg, pyloudnorm. Tự viết: toàn bộ orchestrator, webui, adapter CLI, dịch 2 tầng + glossary, chunk TTS + hậu kỳ, phân cảnh có kiểm bất biến, timeline, style lock, batch 2-pass, bootstrap nhân vật, Studio, chatbot, test, CI.
- **Tra ở:** Q65

## 1.23 Vì sao đầu ra tiếng Việt, nguồn tiếng Trung?
- **Mức:** ★★
- **Ý trả lời chính:** Nguồn truyện mạng chủ yếu tiếng Trung, người dùng đích là người Việt; cũng nhận nguồn đã là tiếng Việt (local) hoặc AI viết trực tiếp bằng tiếng Việt (bỏ qua dịch).
- **Tra ở:** ch03, ch04

## 1.24 Kết quả đạt được so với mục tiêu?
- **Mức:** ★★
- **Ý trả lời chính:** Đạt: pipeline đủ 4 bước, dừng/chạy lại, 0 rò chữ Hán, VRAM đỉnh 4 GB, 173 test, 15/16 ca kiểm thử hệ thống. Chưa đạt: từ chối ngoài phạm vi 87,5% < 90% (TC16), chưa đo MOS/CLIP, video tĩnh.
- **Tra ở:** Q55, báo cáo 5.5

## 1.25 Nếu làm lại em sẽ đổi gì?
- **Mức:** ★★
- **Ý trả lời chính:** Ghi JSON atomic, truyền key qua biến môi trường, dùng bảng `jobs` làm nhật ký lần chạy, bỏ merge trùng trong auto-run, thêm zoompan/xfade, đo CLIP/MOS, benchmark nhiều GPU.
- **Tra ở:** ch14 câu 12
