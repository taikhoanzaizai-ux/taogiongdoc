"""Explain observed error text without pretending that every failure is known."""
import re
def redact(text):
    text=re.sub(r'\bhf_[A-Za-z0-9]{20,}\b','[TOKEN HIDDEN]',text)
    return re.sub(r'(?im)(authorization\s*[:=]\s*(?:bearer\s+)?)[^\s,]+',r'\1[HIDDEN]',text)
def explain(engine,text):
    t=text.lower()
    if any(x in t for x in ('no space left','not enough space','disk full','winerror 112')):
        return 'Ổ đĩa không đủ chỗ','Xem đường dẫn và dung lượng trống trong Cài đặt. Bản mới lưu vào data cạnh app; đóng app, chép bản cập nhật vào thư mục đã giải nén trên ổ còn chỗ rồi mở BAT_DAU.bat để chuyển dữ liệu cũ. Giữ cache đã tải.'
    if any(x in t for x in ('out of memory','memoryerror','not enough memory','paging file is too small')):
        return 'Không đủ bộ nhớ để nạp mô hình','Đóng ứng dụng nặng, dùng CPU/model nhẹ hơn hoặc máy có thêm RAM. Đã cài thư viện chưa có nghĩa model nạp được.'
    if any(x in t for x in ('dns error','no such host','11001','getaddrinfo failed','temporary failure in name resolution')):
        return 'Máy không phân giải được tên miền tải thư viện','Máy không tra được tên miền tải gói (ví dụ files.pythonhosted.org). Kiểm tra Internet/DNS hoặc đổi mạng, rồi Thử lại; bộ cài giữ cache và tự thử lại có giới hạn. Không cần cài lại Python. Có thể kiểm tra bằng: nslookup files.pythonhosted.org'
    if engine=='vibevoice' and any(x in t for x in ('can only setitems','weights only load failed','weights_only')):
        return 'Không đọc được định dạng tệp giọng VibeVoice','Cập nhật lên 1.4.1 rồi Thử lại VibeVoice. Bản sửa kiểm tra SHA256 của 25 tệp giọng chính thức trước khi nạp định dạng cũ. Không cần xóa model.'
    if 'wsl' in t and any(x in t for x in ('chưa sẵn sàng','0x80370102','0x8007019e','virtualization','restart','not installed','e_fail','distribution failed to start','không khởi động được','--manage','--move')):
        return 'WSL2 chưa sẵn sàng cho Fish Speech','Chạy SUA_FISH_WSL.bat để cập nhật WSL, khởi động lại Windows rồi Thử lại riêng Fish. Kiểm tra ảo hóa và dung lượng. Bộ cài chỉ khởi động lại QuanVoice-Fish, giữ distro và dùng WSL --manage --move để chuyển ổ; không unregister.'
    if any(x in t for x in ('microsoft visual c++','failed building wheel','cmake','cl.exe')):
        return 'Có thư viện yêu cầu biên dịch trên Windows','Cập nhật bộ cài rồi thử lại GPT-SoVITS. Nếu vẫn lỗi, tải chẩn đoán để xác định đúng gói cần xử lý.'
    if 'torchaudio' in t and any(x in t for x in ('no module named','could not load','winerror','undefined symbol','dll load failed')):
        return 'Thư viện PyTorch/torchaudio chưa tương thích','Bấm Thử lại để bộ cài kiểm tra và sửa cặp thư viện CPU. Không xóa model đã tải.'
    if any(x in t for x in ('gatedrepo','401 client error','403 client error','access to model','repositorynotfounderror')):
        return 'Không tải được tài nguyên hoặc thiếu quyền truy cập','Xem địa chỉ và thông báo gốc bên dưới. Kiểm tra repo/checkpoint và quyền tài khoản nếu nguồn yêu cầu; cài lại không tự cấp quyền truy cập.'
    if any(x in t for x in ('readtimeout','connecttimeout','connectionerror','timed out','certificate_verify_failed','network is unreachable','nameresolutionerror')):
        return 'Lỗi kết nối khi tải dữ liệu','Kiểm tra mạng/đồng hồ/chứng chỉ của máy, rồi Thử lại để dùng tiếp cache. Bộ cài không tắt xác minh chứng chỉ.'
    return 'Cần xem thông báo gốc để xác định nguyên nhân','Ảnh trạng thái không chứa nguyên nhân chi tiết. Tải chẩn đoán và gửi file đó để kiểm tra đúng lỗi; không cần xóa dữ liệu.'
