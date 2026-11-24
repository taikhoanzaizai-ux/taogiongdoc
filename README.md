# Quân Voice Studio

Ứng dụng Windows tạo và clone giọng trên máy. VieNeu V3 Turbo và Chatterbox Multilingual dùng môi trường riêng. OmniVoice và MOSS-TTS Local Transformer v1.5 hỗ trợ tiếng Việt, Anh, Nhật và Hàn.

## Cài trên Windows x64

1. Tải `QuanVoice-Studio-Windows.zip` từ [GitHub Releases](https://github.com/taikhoanzaizai-ux/taogiongdoc/releases/latest).
2. Giải nén rồi mở `QUAN_VOICE.vbs`. Internet cần thiết để tải thư viện và trọng số ở lần đầu.
3. Mở **Kho mô hình**, chọn **Cấu hình** để chọn CPU hoặc GPU, rồi bấm **Cài tự động**. OmniVoice cần lời đọc khớp với audio mẫu khi clone. MOSS-TTS tải riêng Python 3.12 và có thể chậm trên CPU. Thử đoạn ngắn trước khi tạo bài dài.

## Cập nhật

Từ bản 1.6.5, mở Studio bằng `QUAN_VOICE.vbs`, vào **Cài đặt → Cập nhật ứng dụng → Kiểm tra bản cập nhật** rồi chọn **Cập nhật ngay**. Studio tải bản Windows từ GitHub, tự đóng và tự mở lại sau khi thay tệp. Thư mục `data` được giữ nguyên. Từ các bản cũ, giải nén ZIP 1.6.5 đè vào thư mục cài đặt một lần để có nút này.

Khi phát hành phiên bản mới, cập nhật phiên bản trong mã rồi đẩy tag `vX.Y.Z` để GitHub Actions tạo ZIP và GitHub Release.

## Đóng gói

`python scripts/package.py --mini-only`
