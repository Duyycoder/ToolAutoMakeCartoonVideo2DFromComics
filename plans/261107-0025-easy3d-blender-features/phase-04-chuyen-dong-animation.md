# Đợt 4 — Chuyển động (animation)

**Ưu tiên:** P1 · **Trạng thái:** pending

- Thanh thời gian dưới khung 3D (ẩn tới khi bấm **🎬 Chuyển động**): kéo con trỏ thời gian, nút Phát/Dừng, độ dài 1–30 s.
- "📍 Ghi tư thế": lưu vị trí/góc/cỡ của vật đang chọn tại thời điểm hiện tại (keyframe); chấm keyframe trên thanh, bấm để xoá.
- Mẫu nhanh: Bàn xoay 360°, Nảy lên xuống, Lắc lư, Phóng to dần.
- Xuất: video (MediaRecorder canvas → MP4 nếu WebView2 hỗ trợ, không thì WebM), GLB có animation (GLTFExporter animations).
- Kỹ thuật: THREE.AnimationClip + AnimationMixer; lưu clip trong project GLB.
- Files: `animation-timeline-panel.js`, `keyframe-animation-store.js`, `video-export-recorder.js`.
