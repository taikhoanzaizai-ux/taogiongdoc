# Các dự án gốc

QUÂN Voice Studio là giao diện và lớp tích hợp. Các dự án upstream giữ nguyên tác giả, giấy phép và thông tin bản quyền.

Xem `upstream/<engine>/LICENSE*` và README tương ứng trong gói đầy đủ. Revision được ghi trong `desktop/sources.lock.json`.

1. Whisper — https://github.com/openai/whisper
2. GPT-SoVITS — https://github.com/RVC-Boss/GPT-SoVITS
3. VibeVoice — https://github.com/microsoft/VibeVoice
4. Chatterbox — https://github.com/resemble-ai/chatterbox
5. IndexTTS — https://github.com/index-tts/index-tts
6. Fish Speech — https://github.com/fishaudio/fish-speech
7. VieNeu-TTS — https://github.com/pnnbao97/VieNeu-TTS

Bộ trọng số lớn không được nhúng trong gói. Các tệp upstream vốn đã có trong checkout được giữ nguyên; tệp LFS pointer chưa tải nội dung. Tham khảo giấy phép đi kèm từng checkpoint tải riêng.

## Công cụ nền đi kèm gói đầy đủ

- Python 3.11.9 x64: bộ cài chính thức python.org, giấy phép PSF, https://docs.python.org/3.11/license.html. Trình cài giữ các thông báo bản quyền trong bản cài Python.
- Git for Windows MinGit x64: ZIP phát hành chính thức, GPLv2 và giấy phép thành phần; các giấy phép trong ZIP được giữ nguyên. Mã nguồn tương ứng: https://github.com/git-for-windows/git/releases/tag/v2.56.0.windows.2 và https://github.com/git-for-windows/build-extra.
- FFmpeg essentials từ Gyan: ZIP nguyên vẹn giữ giấy phép/thông báo đi kèm, https://www.gyan.dev/ffmpeg/builds/; nguồn FFmpeg https://ffmpeg.org/download.html và cấu hình/bản nguồn theo trang nhà cung cấp. Bản build có thể mang GPL tùy thư viện đã bật; xem LICENSE trong ZIP.
- Các wheel PyPI nền giữ nguyên metadata/giấy phép trong file WHL.

Các bộ cài được cung cấp nguyên vẹn; không đổi giấy phép upstream. Ubuntu WSL và trọng số không nằm trong ZIP, được tải từ nguồn gốc trong lần chuẩn bị đầu. Giấy phép ứng dụng không thay thế giấy phép checkpoint.

- Microsoft Visual C++ x64 Redistributable: bộ cài gốc của Microsoft, giấy phép Microsoft trong trình cài. Dùng khi thư viện native như ONNX cần runtime; https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist. Không phải mã nguồn mở; không chỉnh sửa bộ cài.

## Lớp tương thích GPT-SoVITS CPU / Windows 1.3.2

Bộ cài dùng opencc-python-reimplemented (https://github.com/yichen0831/opencc-python), jieba (https://github.com/fxsjy/jieba), pyopenjtalk-plus 0.4.1.post9 (https://github.com/tsukumijima/pyopenjtalk-plus) và ONNX Runtime CPU thay các gói yêu cầu build/GPU trong profile Windows mặc định. Giữ giấy phép riêng của từng gói. Các thay đổi import áp dụng trên bản nguồn trong thư mục dữ liệu; file `.quanvoice-original` giữ bản upstream để đối chiếu.

## Cửa sổ desktop 1.4

Dùng pywebview (BSD-3-Clause, https://github.com/r0x0r/pywebview) cùng Python.NET và Microsoft WebView2 theo giấy phép tương ứng, Các wheel cần cho cửa sổ được giữ trong gói Windows đầy đủ; runtime WebView2 có thể cần cài riêng nếu Windows chưa có. Biểu tượng ứng dụng vẽ bằng mã, dựa trên biểu tượng sóng âm của giao diện hiện tại. Wrapper VibeVoice dùng API streaming tại revision trong sources.lock.json; giữ thông tin và giấy phép Microsoft trong nguồn gốc.
