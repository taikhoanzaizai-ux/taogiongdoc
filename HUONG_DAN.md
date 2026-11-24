# QUÂN Voice Studio 1.5.6 Desktop

## Bản 1.5.6 — sửa lỗi danh sách thư mục trên Windows PowerShell 5.1

Thông báo `Cannot convert 'app-env bootstrap cache ... voices' ... ChildPath` phát sinh khi Windows PowerShell 5.1 trả cả mảng JSON thành một đối tượng, còn bộ khôi phục liên kết truyền đối tượng đó cho `Join-Path`. Kiểm tra bằng PowerShell 7 trước đây chưa bao phủ khác biệt này.

- Đọc, làm phẳng và kiểm tra từng tên thư mục trước khi ghép đường dẫn. Hỗ trợ danh sách trống, một tên, nhiều tên và mảng lồng nhau từ nhật ký cũ.
- Tiếp tục hồ sơ chuyển dữ liệu đang dở của 1.5.5; không yêu cầu xóa `migration-aliases.json`, `studio.db`, voice hoặc model.
- Nhật ký khôi phục được ghi thành một danh sách phẳng để tránh mảng ngày càng lồng sâu trên PowerShell 5.1.

**Cập nhật nhanh:** đóng Studio và thông báo lỗi. Chép nội dung `QuanVoice-Studio` trong gói cập nhật 1.5.6 đè vào đúng thư mục app đang dùng trên E:. Giữ nguyên `data`, `install-assets` và `upstream`. Mở `MO_VA_GHI_LOI.cmd`, kiểm tra dòng phiên bản 1.5.6 và đợi hoàn tất; sau đó mở `QUAN_VOICE.vbs` như bình thường. Bản cập nhật nhỏ dùng lại bộ cài và 7 nguồn đã có; gói đầy đủ 1.5.6 kèm đủ các thành phần như bản trước. Trọng số còn thiếu tải khi chuẩn bị mô hình.

Đã tái hiện lỗi ghép đường dẫn bằng mã 1.5.5 khi mô phỏng quy tắc JSON của PowerShell 5.1; bản sửa vượt qua các ca tương thích JSON, chuyển dữ liệu bị ngắt, giữ voice/model và khởi động backend thật với SQLite. Đây là mô phỏng hành vi PowerShell trên Linux, chưa phải kiểm thử junction, bộ cài hay cửa sổ native trực tiếp trên Windows.

## Bản 1.5.5 — sửa nhận diện dữ liệu sau khi đổi thư mục

Ảnh báo `Cannot identify one saved library behind the old data links` xảy ra khi liên kết cũ còn trỏ tới thư mục có tên “Phần mềm”, còn app đang mở ở đường dẫn mới. Bộ chuyển dữ liệu trước đây từ chối cả trường hợp cơ sở dữ liệu vẫn ở C: hoặc cơ sở dữ liệu tại đích cũ không còn.

- Nhận diện cơ sở dữ liệu còn lại thay vì yêu cầu mọi thư mục phải ở cùng chỗ. Hai cơ sở dữ liệu khác nội dung vẫn được giữ riêng, không tự ghi đè.
- Chép thư mục còn tồn tại từ đường dẫn liên kết cũ vào `data` của app hiện tại; giữ nguyên bản gốc. Kiểm tra xung đột tệp giọng trước khi di chuyển cơ sở dữ liệu.
- Nếu đường dẫn thư mục cũ đã mất, tạo lại thư mục chứa ở nơi hiện tại, ghi đường dẫn gốc vào `data/migration-link-recovery.json`; không tự phục hồi âm thanh đã mất.
- Bổ sung hồ sơ chuyển dữ liệu cho lần chạy dở của phiên bản cũ; lần sau có thể tiếp tục. Cập nhật đường dẫn mô hình đã lưu từ cả vị trí C: lẫn thư mục cũ.

**Cách cập nhật:** đóng Studio và thông báo cũ. Chép nội dung `QuanVoice-Studio` trong ZIP 1.5.5 đè vào đúng thư mục app đang dùng, giữ nguyên `data` và các thư mục cũ. Mở `MO_VA_GHI_LOI.cmd`, kiểm tra dòng đầu là 1.5.5 và đợi hoàn tất. Sau đó dùng `QUAN_VOICE.vbs` như bình thường. Không xóa `studio.db` hoặc liên kết cũ để bỏ qua lỗi.

Đã kiểm tra các trường hợp cơ sở dữ liệu ở C:, hai bản cơ sở dữ liệu giống/khác nhau, thư mục cũ còn/mất, xung đột WAV, chép bị ngắt rồi mở lại, cùng khởi động backend thật với SQLite. Kiểm tra liên kết chạy bằng PowerShell trên Linux; chưa kiểm thử junction và giao diện native trực tiếp trên Windows. Bộ cài đầy đủ vẫn kèm 7 bộ nguồn, Python, Git, FFmpeg, VC++ và thư viện nền; trọng số/thư viện riêng của mô hình còn thiếu sẽ tải khi chuẩn bị mô hình lần đầu.

## Bản 1.5.4 — bộ cài đầy đủ và kiểm tra lại toàn bộ đường khởi động

**Lỗi trong ảnh `jobs`:** liên kết đã trỏ đúng `data/jobs` trong app trên E, nhưng thư mục này chưa tồn tại. Các bản trước kiểm tra theo nhóm thư mục và còn chặn thư mục khác. Quy tắc mới áp dụng chung cho mọi liên kết thư mục cùng trỏ đúng vị trí app: tạo lại thư mục chứa rồi tiếp tục. Việc này không tự phục hồi tệp âm thanh đã mất; dữ liệu còn tồn tại được giữ, và nhật ký ghi rõ thư mục nào thiếu.

**Gói Windows đầy đủ** có mã ứng dụng, cả 7 bộ nguồn tại revision cố định, bộ cài Python 3.11.9 x64, MinGit, FFmpeg, Visual C++ Runtime và các wheel dành cho Python 3.11 x64, gồm thành phần cửa sổ desktop. SHA256 và kích thước của các bộ cài được đối chiếu trước đóng gói. Gói nhỏ trên bản web là gói cập nhật mã, sẽ tải thành phần còn thiếu khi cần.

- Dùng lại Python 3.11 x64 đã có qua vị trí cài thông thường/PATH/registry/Python Launcher. Thiếu Python Launcher không còn bắt cài lại Python đang dùng được. Khi chưa có Python đúng bản, bộ cài Python đi kèm được dùng, có tùy chọn Launcher và PATH.
- Môi trường ứng dụng hỏng hoặc mất Python gốc được chuyển sang thư mục `app-env-before-repair-*` để giữ lại, rồi tạo môi trường ứng dụng mới. Không xóa các môi trường/model/giọng đã lưu khác.
- Các lệnh cài và mở ứng dụng xét mã thoát; stderr dùng để ghi tiến trình/cảnh báo được giữ trong nhật ký. Các lỗi mã thoát khác 0 vẫn dừng và hiện thông báo.
- Bộ thư viện lõi và giao diện được cài từ wheel đi kèm khi đủ, có kiểm tra hash. Có thể chuyển sang trình duyệt nếu WebView chưa dùng được.
- Giọng có bản ghi trong cơ sở dữ liệu nhưng mất WAV sẽ báo cần nhập lại tệp gốc; không trả lỗi máy chủ chung hoặc xếp tác vụ clone không thể chạy.
- Mã nguồn và công cụ nền đã có trong gói; thư viện SDK/trọng số lớn cho các model, Ubuntu/WSL và runtime WebView2 nếu máy thiếu vẫn có thể cần mạng. Các model đã có và còn đọc được tiếp tục dùng lại. Đã đóng gói đầy đủ không có nghĩa đã nhúng toàn bộ trọng số của 7 dự án.

**Cách áp dụng:** đóng app và hộp lỗi. Chép nội dung thư mục `QuanVoice-Studio` trong ZIP đè vào đúng thư mục hiện tại trên E đang chứa `QUAN_VOICE.vbs`; giữ `data` và các thư mục dữ liệu cũ. Chạy `MO_VA_GHI_LOI.cmd` lần đầu và kiểm tra dòng phiên bản **1.5.4**, chờ các bước cài/chuyển xong. Các lần sau mở `QUAN_VOICE.vbs` hoặc shortcut trên Desktop.

Kiểm tra: hệ thống tệp có liên kết đúng đích bị thiếu ở nhiều tên thư mục; chuyển/tiếp tục/xung đột; SQLite thật trước và sau chuyển; khởi động backend FastAPI thật từ dữ liệu đó; cổng bận và khóa; nguyên văn TXT/SRT; resolve toàn bộ wheel offline cho Windows/Python 3.11. Chưa chạy trực tiếp bộ cài hoặc cửa sổ native trên Windows và chưa nạp đủ trọng số để thử tổng hợp bằng cả 7 dự án trên máy người dùng.

## Bản cập nhật 1.5.3 — sửa liên kết cache bị thiếu hoặc trỏ tới nơi khác

Bản 1.5.2 còn dừng ở `Old data links elsewhere … cache` khi thư mục đích cache không còn tồn tại. Bản này xử lý riêng dữ liệu có thể tạo lại, đồng thời kiểm tra chuỗi liên kết qua nhiều lần chuyển app.

- Liên kết cache cùng trỏ về thư mục app nhưng thiếu thư mục đích: tạo `data/cache` trên ổ app, rồi tiếp tục mở. Môi trường ứng dụng, cache, thư viện model, công cụ và các thư mục tạm bị thiếu cũng được phân loại để có thể tạo lại. Các thành phần đã mất có thể cần tải lại, không được báo là đã khôi phục nội dung cũ.
- Cache cũ còn nằm ở thư mục khác: sao chép sang cache trong app, giữ nguồn cũ và các file đã có ở đích. Chỉ cập nhật liên kết sau khi sao chép thành công; lỗi sao chép có thể chạy lại để tiếp tục.
- `migration-link-recovery.json` ghi lại đích liên kết cũ và đích mới. Thư mục giọng tham chiếu hoặc bản thu đã mất không bị thay bằng thư mục rỗng; thông báo chỉ rõ vị trí cần khôi phục.
- Cửa sổ tiến trình và thông báo lỗi hiển thị số bản **1.5.3** để xác nhận đã chép đè đúng thư mục. Nếu vẫn thấy thông báo cũ không có phiên bản, kiểm tra thư mục app đang mở.

Đóng cửa sổ lỗi và các lần mở app cũ. Chép nội dung thư mục `QuanVoice-Studio` trong ZIP đè vào đúng thư mục đang chứa `QUAN_VOICE.vbs` trên ổ E, giữ `data`, rồi chạy `MO_VA_GHI_LOI.cmd`. Chờ sao chép dữ liệu nếu có. Các lần sau mở `QUAN_VOICE.vbs`.

Đã tái hiện lỗi thiếu đích `cache` ở bản cũ, kiểm tra bản sửa bằng PowerShell với liên kết thật trên hệ thống tệp Linux và mô phỏng robocopy: cache thiếu, cache ngoài thư viện, sao chép lỗi/chạy lại, giữ nguồn và file đích, nhiều tầng liên kết, giữ dữ liệu giọng và phát hiện liên kết vòng. Chưa kiểm chứng trực tiếp junction và robocopy trên Windows.

## Bản cập nhật 1.5.2 — sửa lỗi “Old data links elsewhere … app-env”

Lỗi này xảy ra khi thư mục cũ `LocalAppData/QuanVoiceStudio` có các liên kết tương thích trỏ tới một thư viện đã được chuyển trước đó. Giải nén app sang thư mục khác có thể khiến bộ chuyển dữ liệu hiểu sai nguồn và dừng.

- Bộ chuyển tìm thư viện gốc thật từ các liên kết. Chỉ tự nhận khi chúng thống nhất một thư mục và thư mục đó có `studio.db`. Nếu dữ liệu nằm rải ở nhiều nơi hoặc không xác định được thư viện, các thư mục được giữ lại và thông báo nêu rõ nguyên nhân.
- Chuyển tiếp dữ liệu về `data` cạnh app mới, giữ các liên kết tương thích để môi trường Python/model đã có còn hoạt động. Nhật ký nguồn `migration-source.json` cho phép tiếp tục cả khi cơ sở dữ liệu đã chuyển xong mà bước sau bị ngắt.
- Không gộp hai cơ sở dữ liệu khác nhau. Nếu app mới đã có thư viện độc lập và không chuyển dở, tiếp tục dùng thư viện đó.
- Các file migration của lần cũ được giữ ở nguồn; không ghi đè nhật ký lần mới. Đĩa WSL đã đăng ký vẫn do chức năng chuyển WSL riêng quản lý, không được sao chép hoặc di chuyển trực tiếp trong bước này.

**Áp dụng cho lỗi trong ảnh:** đóng Studio, bộ cài và hộp thông báo lỗi; chép nội dung thư mục `QuanVoice-Studio` trong ZIP vào đúng thư mục app trên E:, giữ `data` và các thư mục thư viện cũ. Chạy `MO_VA_GHI_LOI.cmd` để thấy tiến trình. Khi chuyển dữ liệu đang chạy, chờ hoàn tất. Những lần sau mở `QUAN_VOICE.vbs` như bình thường. File lỗi nếu còn: `data/bootstrap/mo-app-<số>.log`.

Đã kiểm tra bằng PowerShell trên hệ thống tệp mô phỏng: các liên kết C→thư viện cũ→thư mục mới, tiếp tục sau khi đã chuyển cơ sở dữ liệu, dữ liệu giọng/cache/model và các tình huống xung đột. Chưa kiểm chứng junction native trên Windows; nếu nguồn liên kết không còn tồn tại, ứng dụng sẽ báo cần kết nối lại ổ/thư mục gốc thay vì tự đoán hoặc tải lại toàn bộ voice.

## Bản cập nhật 1.5.1 — nút Xuất SRT luôn có trên màn hình tạo giọng

- **Tạo giọng AI → Xuất SRT**, ngay cạnh **Xuất TXT**. Nút này xuất hiện cả khi chưa tạo giọng và dùng được trên bản web.
- **Nguồn phụ đề**: chọn văn bản đang soạn hoặc một bản thu đã hoàn tất. Nếu có bản thu TTS khớp nguyên văn, hộp xuất tự chọn bản thu đó. Vẫn có thể đổi nguồn.
- Khi chưa có âm thanh, nhập **Tổng thời lượng dự kiến (giây)**. Mốc SRT được ước lượng theo văn bản và thời lượng này; không phải mốc nhận dạng âm thanh. Không cần kết nối bộ xử lý để xuất văn bản này.
- **Nội dung xuất → Toàn bộ** tải một SRT. **Từng đoạn** cho chọn các đoạn cách nhau bằng dòng trống: một đoạn tải SRT, nhiều đoạn gom ZIP. Có thể đặt lại mốc từng file từ 0 hoặc giữ mốc của toàn văn bản.
- Kết quả tạo giọng/chép lời và lịch sử vẫn có nút **Xuất SRT…** với mốc của bản thu như bản 1.5.0. Giữ nguyên model/voice/data khi cập nhật.

Đóng Studio, chép đè nội dung thư mục `QuanVoice-Studio` từ ZIP cập nhật vào thư mục app đang dùng, giữ `data`, rồi mở lại. Bản cập nhật này dùng cùng API với 1.5.0; các bản 1.4.x phải đóng bộ xử lý cũ.

## Bản cập nhật 1.5.0 — xuất TXT và SRT đầy đủ hoặc từng đoạn

- **Tạo giọng AI → Xuất TXT**: tải nguyên văn nội dung đang soạn thành TXT UTF-8, kể cả trước khi tạo âm thanh. Không cắt theo giới hạn ký tự của mô hình.
- Sau khi tạo giọng hoặc chép lời xong, dùng **Tải TXT** hoặc **Xuất SRT…** ngay trong kết quả và **Lịch sử & hàng đợi**.
- Trong cửa sổ xuất SRT, chọn **Toàn bộ** để tải một SRT của bản thu; hoặc chọn **Từng đoạn**, đánh dấu các đoạn muốn tải. Chọn một đoạn sẽ tải SRT riêng; nhiều đoạn được gom vào ZIP, mỗi đoạn một file, đúng thứ tự ban đầu.
- Với các file riêng, chọn mốc **Bắt đầu từ 00:00:00** để dùng với clip đã cắt, hoặc **Giữ mốc trong bản đầy đủ**. Mỗi file đánh số phụ đề lại từ 1.
- Trong chế độ tạo một bản thu, một đoạn là phần văn bản ngăn bằng dòng trống. Trong chế độ chép lời, một đoạn tương ứng một đoạn Whisper nhận dạng. Chế độ **Tạo theo đoạn / BATCH** tạo nhiều bản thu độc lập: mở xuất của bản thu cần lấy.
- TTS mới ghi thời lượng thực của từng khối tổng hợp và điều chỉnh theo tốc độ/định dạng âm thanh cuối. Mốc từng dòng SRT bên trong khối vẫn là **ước lượng**, chưa phải căn chỉnh từng từ. Bản thu cũ không có dữ liệu thời gian sẽ ước lượng theo tổng thời lượng; cửa sổ xuất luôn ghi rõ. SRT chép lời dùng mốc Whisper nhận dạng.

**Cập nhật:** đóng Studio và bộ xử lý cũ, chép nội dung thư mục `QuanVoice-Studio` trong ZIP đè vào thư mục app đang dùng, giữ nguyên `data`, rồi mở `QUAN_VOICE.vbs`. Bản 1.5.0 cần bộ xử lý mới để có API xuất, không dùng lại backend 1.4.x còn chạy. Không cần cài lại các model/voice đã có.

Đã kiểm tra xuất qua API bằng WAV thật, thay đổi tốc độ bằng FFmpeg, mốc Whisper, lựa chọn đoạn trong ZIP và văn bản tiếng Việt dài. Chưa kiểm thử cửa sổ native trên Windows cho bản này.

## Bản cập nhật 1.4.3 — mở app khi bộ cài đang giữ khóa

Ảnh `Another setup window is already running` xuất phát từ khóa bộ cài. Trước đây, mỗi lần mở đều đi qua khóa này và lần bấm thêm bị báo lỗi ngay.

- Bản mới kiểm tra Python ứng dụng, import thư viện, hash requirements và các công cụ đã cài. Nếu môi trường sẵn sàng, mở thẳng Studio, dùng model/voice đã lưu, không chạy lại bộ cài và không chờ khóa cài đặt.
- Nếu môi trường còn thiếu và đang có một lần cài thật, cửa sổ chờ hiển thị nhật ký. Khi môi trường sẵn sàng hoặc bộ cài nhả khóa, lần mở tiếp tục. Đóng cửa sổ chờ chỉ hủy lần mở thêm; không dừng bộ cài đầu tiên.
- Khóa bị bỏ lại do tiến trình trước thoát được nhận lại theo quy tắc của .NET, sau đó các bước kiểm tra/khôi phục cài đặt vẫn được thực hiện. Không bỏ qua khóa đang có người giữ để chạy hai bộ cài.
- Có thể dùng lại backend 1.4.2 cùng thư mục dữ liệu đang chạy vì bản này chỉ sửa đường khởi động và không thay đổi API.
- Mỗi lần mở có nhật ký `data/bootstrap/desktop-launch-<PID>.log` riêng. Bộ cài kết thúc transcript và nhả khóa trước khi chờ cửa sổ Studio. Phần chuẩn bị WebView được giữ trong khóa cài đặt để tránh hai tiến trình pip cùng sửa môi trường.
- `CHAN_DOAN.bat` bật chế độ sửa đầy đủ (`-Repair`). Chỉ dùng khi cần sửa môi trường, sau khi đóng Studio/bộ cài đang chạy. Không xóa `data`, cache, voice hoặc model để xử lý thông báo khóa.

Đóng thông báo lỗi cũ, chép nội dung thư mục `QuanVoice-Studio` trong ZIP cập nhật đè vào thư mục app đang dùng rồi mở `QUAN_VOICE.vbs`. Dữ liệu vẫn ở ổ giải nén. Nếu bộ cài cũ thật sự chưa xong, chờ cửa sổ tiến trình thay vì bấm mở nhiều lần.

Đã kiểm tra PowerShell bằng hai tiến trình giữ/nhả mutex thật: mở nhanh khi khóa bận, chờ rồi tiếp tục, nhận lại khóa bị bỏ dở, từ chối receipt cũ/môi trường hỏng/chuyển dữ liệu dở. Chưa kiểm chứng WinForms và cửa sổ native trực tiếp trên Windows.


## Bản cập nhật 1.4.2 — sửa lỗi 10048 khi mở cửa sổ

Ảnh báo `[Errno 10048] ... bind on address ('127.0.0.1', 8765)` nghĩa là cổng đang được một tiến trình khác sử dụng. Đây là lỗi khởi động máy chủ cục bộ, không phải voice/model hỏng.

- Đóng phiên Studio cũ trước khi cập nhật. Chép nội dung thư mục `QuanVoice-Studio` trong ZIP đè vào thư mục app đang dùng trên D/E, rồi mở `QUAN_VOICE.vbs` hoặc `BAT_DAU.bat`. Giữ nguyên `data`.
- Bản mới nhận lại phiên cùng phiên bản và cùng thư mục dữ liệu nếu còn chạy. Dùng khóa của hệ điều hành để tránh hai bộ xử lý cùng mở một `studio.db`. Khóa tự được nhả khi tiến trình thoát, không phải xóa file `server.lock` bằng tay.
- Nếu cổng 8765 bị phần mềm khác chiếm, Studio chọn cổng khả dụng khác, giữ socket ngay từ lúc chọn và truyền chính socket đó cho Uvicorn; tránh khoảng trống giữa kiểm tra cổng và khởi động. Cửa sổ và trình duyệt mở đúng địa chỉ mới; xem **Cài đặt → Địa chỉ ứng dụng Windows**.
- Không tự đóng hoặc tắt các tiến trình Python/phần mềm khác. Nếu phiên **cũ** còn chạy mà không thấy cửa sổ, khởi động lại Windows một lần rồi mở bản cập nhật. Không cần cài lại model, xóa cache hoặc chuyển dữ liệu về C.
- Dữ liệu, cache và tệp tạm vẫn lưu ở `data` cạnh app. Nếu hai bản đã có hai thư viện độc lập thì giữ cả hai, không tự gộp.

Đã kiểm tra cổng bị chiếm, giữ cổng tránh tranh chấp, dùng lại phiên đang chạy, nhả khóa sau khi tiến trình thoát, và mở backend Uvicorn thật ở cổng thay thế với cửa sổ giả lập. Chưa chạy thử cửa sổ native trên Windows.


## Bản cập nhật 1.4.1 — lưu cùng ổ giải nén, sửa bốn lỗi đã gửi

1. Đóng Studio và các cửa sổ xử lý cũ. Chép nội dung thư mục `QuanVoice-Studio` trong ZIP cập nhật đè vào **thư mục app bạn đã giải nén trên ổ còn dung lượng**, ví dụ `D:\Codex\QuanVoice-Studio`.
2. Chạy `BAT_DAU.bat`. Dữ liệu mặc định nằm ở **`<thư mục app>\data`**, gồm model, voice, lịch sử, kết quả, môi trường, cache tải và tệp tạm. Ví dụ `D:\Codex\QuanVoice-Studio\data`. Dung lượng trống và đường dẫn thực tế hiện ở **Cài đặt → Lưu trữ**.
3. Lần cập nhật đầu, bộ khởi động chuyển dữ liệu cũ `%LOCALAPPDATA%\QuanVoiceStudio` sang `data`. Giữ app đóng trong lúc chuyển. Nếu gián đoạn, mở BAT_DAU.bat để tiếp tục. Các thư mục tương thích ở vị trí cũ là **junction trỏ sang ổ mới**, để đường dẫn bên trong môi trường Python đã cài vẫn hoạt động; phần model đó không còn chiếm dung lượng ở C. Không xóa các junction. Nếu đích và nguồn đã có hai `studio.db` độc lập, bộ cài giữ cả hai và dùng dữ liệu cạnh app, không tự gộp/ghi đè thư viện.
4. **VibeVoice:** đã tái hiện lỗi `SETITEMS / BaseModelOutputWithPast` bằng PyTorch và nạp thành công cả 25 preset chính thức. Loader kiểm tra đúng SHA256/độ dài tệp trước khi dùng chế độ đọc tương thích định dạng cũ. Tệp không khớp vẫn bị chặn; không tắt kiểm tra cho pickle tùy ý. Bấm **Thử lại VibeVoice**.
5. **IndexTTS:** lỗi ảnh là hết dung lượng. Giữ checkpoint tải dở; bản mới dùng ổ của app, kiểm tra chỗ trống trước bước tải. Giải phóng đúng ổ nếu cần rồi Thử lại; không cần xóa voice.
6. **GPT-SoVITS:** lỗi ảnh là DNS `files.pythonhosted.org`, không phải thiếu Python. Bộ cài giữ cache, thử lại tối đa 3 lượt lệnh với thời gian chờ, uv cũng có retry nội bộ. Nếu DNS vẫn lỗi, kiểm tra `nslookup files.pythonhosted.org`, đổi mạng/sửa DNS rồi Thử lại. Bộ cài không đổi DNS hệ thống hoặc tắt TLS.
7. **Fish Speech:** lỗi ảnh là WSL `CreateInstance/E_FAIL`, distro chưa chạy được. Đóng Studio, chạy **`SUA_FISH_WSL.bat`**, khởi động lại Windows nếu WSL yêu cầu rồi Thử lại Fish. Bộ cài kiểm tra khởi động distro trước apt/pip, chỉ khởi động lại `QuanVoice-Fish`. Distro cũ ở C được chuyển bằng **`wsl --manage QuanVoice-Fish --move <app>\data\wsl\QuanVoice-Fish`** trong lần Thử lại Fish. Nếu WSL chưa hỗ trợ `--move` hoặc không chuyển được, bộ cài báo lỗi và dừng; nếu WSL đã chuyển một phần, giữ cả hai thư mục và gửi chẩn đoán. Bộ cài không tự sao chép/xóa VHD đang đăng ký, không `--unregister`.

Python/Git/FFmpeg cài mới được đặt trong data; Python 3.11 hợp lệ đã có trên máy có thể được dùng lại. Python Launcher, VC Runtime, thành phần Windows/WSL và swap của Windows vẫn do hệ điều hành quản lý. Không cam kết mọi thành phần hệ thống chuyển khỏi C. Cache uv/pip cũ ở ngoài thư mục dữ liệu có thể còn thuộc các ứng dụng khác, bản cập nhật không tự xóa cache dùng chung.

**Kiểm chứng:** 25 preset VibeVoice thật trên CPU; kiểm tra tự động API/worker/cache/đường dẫn/retry/chẩn đoán và parser PowerShell. Chưa kiểm chứng thực tế chuyển ổ, junction, WSL hoặc cả bảy engine trên Windows của bạn. Gói này là cập nhật ứng dụng, không kèm toàn bộ trọng số hoặc bộ cài nền của gói đầy đủ.


Ứng dụng giao diện tiếng Việt để tạo giọng, clone từ âm thanh tham chiếu, quản lý giọng mẫu và chép lời. Chạy trên máy tính, giao diện mở trong trình duyệt tại http://127.0.0.1:8765.

## Mở như phần mềm riêng và dùng lại giọng

1. Đóng bản Studio/cửa sổ CMD cũ trước khi chép cập nhật.
2. Chép nội dung trong thư mục `QuanVoice-Studio` của bản cập nhật đè vào thư mục ứng dụng cũ. Không xóa `%LOCALAPPDATA%\QuanVoiceStudio` hoặc thư mục `QUAN_VOICE_DATA` đang dùng.
3. Mở **BAT_DAU.bat**, **QUAN_VOICE.vbs** hoặc biểu tượng **QUÂN Voice Studio** ngoài Desktop. Ứng dụng mở trong cửa sổ riêng, có biểu tượng và nút thu nhỏ/phóng to/đóng. Không cần giữ CMD. Lần cập nhật đầu có thể cần Internet để cài thành phần cửa sổ pywebview; đây là phần giao diện, không tải lại toàn bộ model.

- Giọng clone, file tham chiếu, model đã tải, cấu hình và lịch sử nằm trong dữ liệu cục bộ. Khi quay lại, chọn giọng đã lưu để dùng; không phải tải file giọng lên lại. Model/giọng/preset/tốc độ/giao diện và bản nháp được ghi nhớ trong SQLite. Lần chuyển từ bản cũ có thể cần chọn lại preset một lần nếu trước đó chỉ lưu ở trình duyệt khác; giọng trong thư viện vẫn được giữ.
- Khi khởi động, ứng dụng tự chuẩn bị model gần nhất từ ổ đĩa vào RAM. Không tự cài lại/khắc phục các model lỗi mỗi lần mở. Nếu muốn cài tiếp model khác hoặc sửa cache thiếu, vào **Kho mô hình → Cài tự động/Thử lại**.
- Worker SDK cho VieNeu, Chatterbox, IndexTTS, VibeVoice và Whisper được giữ giữa các tác vụ. GPT/Fish giữ API đang chạy. Nghe thử rồi tạo tiếp bằng cùng model không khởi tạo lại toàn bộ model. VibeVoice dùng SDK trực tiếp để tránh nạp lại model ở mỗi đoạn.
- Giữ một model SDK trong RAM tại một thời điểm. Đổi model, đổi phiên bản/thiết bị/cấu hình cảm xúc yêu cầu bộ model khác, hủy tác vụ hoặc đóng hẳn phần mềm có thể giải phóng/nạp lại model. Đây là nạp từ ổ đĩa, khác với tải lại từ Internet.
- **Cài đặt → Tự chuẩn bị model gần nhất khi mở**: bật để nạp trước; tắt nếu muốn mở giao diện nhanh và nạp khi dùng. **Dùng dữ liệu model đã tải** mặc định bật: worker SDK và API do ứng dụng mở dùng cache Hugging Face/Transformers. Nếu còn thiếu tài nguyên, chuẩn bị model khi có mạng. Một số thành phần upstream có cơ chế cache riêng nên không cam kết mọi model chạy offline khi chỉ cài thư viện.
- **Giải phóng RAM** dừng bộ xử lý do ứng dụng mở; lần tạo tiếp tự nạp lại. Dữ liệu trên ổ đĩa không bị xóa. Giọng mặc định của Chatterbox được khôi phục khi chuyển từ giọng clone về giọng có sẵn để tránh dùng nhầm giọng clone trước đó.
- Cửa sổ chính dùng WebView2 và lưu profile riêng ở `desktop-profile` trong thư mục dữ liệu (không dùng chế độ ẩn danh). Nếu WebView2/.NET chưa khả dụng, mở bằng chế độ ứng dụng của Edge/Chrome và giữ profile riêng. Nhấn **Thoát** để dừng backend trong chế độ dự phòng. Không có trình duyệt phù hợp thì mở địa chỉ localhost; `CHAN_DOAN.bat` giữ chế độ CMD để xem lỗi.

Model vẫn phải được nạp vào RAM sau khi đóng hẳn ứng dụng/khởi động lại Windows; không có cách giữ nguyên RAM sau khi máy tắt. Lần mở mới ứng dụng tự thực hiện việc này, dùng lại dữ liệu đã lưu. RAM/VRAM và tốc độ ổ đĩa quyết định thời gian chờ.

Đã kiểm tra giữ worker/model qua nhiều job, warm-up, đổi cấu hình, hủy/khởi động lại worker, lưu/khôi phục giọng và cấu hình. Kiểm thử SDK dùng mô hình giả lập; chưa kiểm chứng cửa sổ native và suy luận cả 7 model trên Windows thật.

## Bản sửa cài đặt 1.3.2

Hộp chọn hiển thị đủ **7 mô hình**, gồm **6 tạo giọng + Whisper chép lời**. Whisper không tạo/clone giọng; chọn thẻ này sẽ mở phần Âm thanh → văn bản. Danh sách ngôn ngữ hiển thị đầy đủ theo từng mô hình, không rút xuống 3 mã ngôn ngữ.

Bản cập nhật là gói nhỏ để chép đè ứng dụng đã giải nén, không xóa dữ liệu/voice/checkpoint. Đóng cửa sổ Studio cũ, chép nội dung trong `QuanVoice-Studio` vào thư mục ứng dụng cũ, mở BAT_DAU.bat và Ctrl+F5. Các model đã chuẩn bị vẫn được giữ. Bấm **Thử lại** ở model đang lỗi.

- GPT-SoVITS CPU trên Windows: tránh buộc build OpenCC/jieba_fast/pyopenjtalk bằng compiler. Dùng OpenCC Python, jieba thường, wheel `pyopenjtalk-plus` tương thích API và ONNX Runtime CPU. Bản sao nguồn trong thư mục dữ liệu được điều chỉnh tên import `jieba_fast` thành `jieba`; bản gốc được giữ cạnh file với đuôi `.quanvoice-original`. Nguồn upstream trong gói đầy đủ không bị sửa. Hiệu năng/ngữ điệu có thể khác; chưa kiểm thử tiếng Nhật/Trung trên máy Windows thật.
- Kiểm tra import PyTorch/torchaudio, sửa cặp CPU khi import lỗi; kiểm tra dependency trước khi tải/nạp model. Sửa môi trường Python dang dở và bổ sung file nguồn còn thiếu thay vì chỉ kiểm tra thư mục có tồn tại.
- Fish: đọc được đầu ra WSL UTF-8/UTF-16, báo lỗi WSL gốc và tăng khả năng thử lại tải mạng. Vẫn cần WSL2/ảo hóa và đủ RAM; bản cập nhật không tự vượt qua giới hạn phần cứng/quyền truy cập checkpoint.
- Tăng thời gian chờ kết nối tải Hugging Face/uv. Không tắt kiểm tra chứng chỉ.

Nếu còn lỗi, bấm **Chi tiết lỗi → Tải chẩn đoán** hoặc nút **Tải chẩn đoán** ở Kho mô hình, rồi gửi file `QuanVoice-ChanDoan.txt`. File gồm nhật ký cài và API, có thể chứa đường dẫn cục bộ của máy; không chủ động kèm kịch bản, file giọng hay biến môi trường. Không thể xác định mọi nguyên nhân chỉ từ ảnh ghi “Cài chưa xong”. Bộ cài mới chưa được xác nhận chạy thành công cả 7 model trên máy Windows của bạn.

## Nội dung dài, không đặt giới hạn ký tự

Bản 1.3.1 bỏ mức chặn 20.000 ký tự cho kịch bản, mức 400 ký tự cho nghe thử và phần cắt nội dung khi nhập TXT/JSON. Chế độ tạo theo đoạn cũng bỏ mức chặn 50 đoạn. Văn bản được giữ đầy đủ trong tác vụ.

Khi tạo bằng một trong 6 engine TTS, ứng dụng chia nội dung thành đoạn nhỏ theo dấu câu/khoảng trắng phù hợp ngữ cảnh mô hình, đọc lần lượt và ghép theo thứ tự thành **một file WAV hoặc MP3**. Giọng, ngôn ngữ, tốc độ và cảm xúc giữ nguyên. Không cần chia tay hoặc rút ngắn kịch bản. Lịch sử và log hiển thị số ký tự đã xử lý. Mô hình có thể thể hiện ngữ điệu khác tại ranh giới đoạn.

Ứng dụng không tự dừng tác vụ TTS/nghe thử sau 2 giờ nữa; nút Hủy vẫn hoạt động. Thời gian chờ mỗi yêu cầu API con và cài đặt vẫn được giữ để phát hiện dịch vụ không phản hồi. Văn bản dài vẫn phụ thuộc RAM, ổ đĩa, thời gian và khả năng của mô hình; không có bảo đảm vô hạn tài nguyên. VibeVoice SDK giữ model và cache preset trong cùng worker. WAV lớn được xuất với RF64 khi cần.

Nếu bản nháp vượt dung lượng lưu của trình duyệt, nội dung hiện tại vẫn được giữ để tạo giọng; bấm **Lưu dự án** để lưu JSON trước khi đóng/tải lại trang. Cập nhật bằng cách đóng bản cũ, giải nén bản mới rồi mở BAT_DAU.bat; không xóa thư mục dữ liệu để giữ model/giọng/lịch sử.

## Bắt đầu trên Windows 10/11 x64

1. Giải nén **toàn bộ** `QuanVoice-Studio-1.3.1-Unlimited.zip`, ví dụ `D:\QuanVoice`. Không chạy bên trong ZIP. Đóng bản Studio cũ trước khi mở bản mới.
2. Bấm đúp **BAT_DAU.bat**. Bộ cài tự cài **Python 3.11.9 x64**, pip, **Python Launcher**, thêm Python/Scripts/Launcher vào **PATH**; giải nén **Git for Windows (MinGit)** và **FFmpeg**, thêm chúng vào PATH của tài khoản. Không cần đánh dấu các ô bằng tay. Bộ cài cũng kiểm tra và cài Microsoft Visual C++ x64 Runtime nếu thiếu, Windows có thể yêu cầu quyền quản trị. Git bản MinGit phục vụ dòng lệnh, không có giao diện Git GUI.
3. Giữ cửa sổ lệnh mở. Studio tự mở tại http://127.0.0.1:8765 và tự chuẩn bị đủ **7 mô hình** theo thứ tự: VieNeu, Whisper, Chatterbox, IndexTTS, VibeVoice, GPT-SoVITS, Fish Speech. Trong **Kho mô hình** theo dõi số đã xong; **Lịch sử & hàng đợi → Xem log** có chi tiết. Thời gian và dung lượng phụ thuộc từng bộ trọng số, có thể rất lớn.
4. Giữ Internet cho lần đầu tải thư viện AI/trọng số và Ubuntu cho Fish. Python/Git/FFmpeg và các wheel nền Windows đã nằm trong gói đầy đủ. **Đây là gói tự cài, không phải bộ 7 mô hình đã cài sẵn offline.** Khi Windows hiện hộp thoại quản trị để bật WSL, cho phép nếu muốn dùng Fish. Không tự khởi động lại máy; nếu Windows yêu cầu, hãy khởi động lại rồi mở BAT_DAU.bat lần nữa.
5. Có thể dùng mô hình đã báo **Đã chuẩn bị** trong khi mô hình khác đang cài. Bắt đầu với **VieNeu · Tiếng Việt · Hải Đăng**, bấm **Nghe thử** trước khi tạo bản đầy đủ. Clone hỗ trợ 5 mô hình; Whisper chép lời và VibeVoice Realtime dùng preset, không clone file tùy ý.

**BAT_DAU_NHANH.bat** chỉ tự chuẩn bị VieNeu + Whisper, không yêu cầu WSL; sau đó bấm **Cài tiếp toàn bộ** nếu muốn. **Start-Windows.bat** là tên thay thế cho BAT_DAU.bat. Desktop có lối tắt tự tạo, cần giữ thư mục đã giải nén tại vị trí cũ.

## Mới trong phiên bản 1.3

- Bộ cài Windows tự xử lý công cụ nền, kiểm SHA256 các bộ cài và wheel đi kèm, dùng môi trường riêng từng engine.
- Tự tải và kiểm tra nạp mô hình mặc định; VieNeu/VibeVoice tạo đoạn mẫu ngắn, Whisper/Chatterbox/Index kiểm tra tải và nạp, GPT/Fish kiểm tra khởi động API. Đây không phải kiểm chứng chất lượng suy luận cho mọi giọng/ngôn ngữ/thiết bị.
- Mỗi engine có trạng thái thành công/lỗi riêng. Lỗi một engine không ngăn engine tiếp theo. Bấm **Thử lại** hoặc mở lại BAT_DAU.bat để tiếp tục; thư viện/cache đã tải được dùng lại. Không báo hoàn tất khi tải lỗi.
- GPT-SoVITS và Fish tự khởi động API khi tạo/nghe thử; các dịch vụ do ứng dụng mở được dừng khi chuyển sang engine khác để giải phóng bộ nhớ. Dịch vụ API do bạn tự mở được giữ nguyên.
- Fish dùng distro WSL2 riêng tên **QuanVoice-Fish**, Ubuntu 24.04 từ máy chủ Ubuntu chính thức. Không xóa/sửa distro cá nhân. Khi bật WSL lần đầu có thể cần quyền quản trị, bật ảo hóa và khởi động lại Windows. Nếu bước này lỗi, dùng các engine còn lại và thử Fish sau.

## Mới trong phiên bản 1.2

### Nghe thử trước khi tạo toàn bộ nội dung

- Trong **Tạo giọng AI**, chọn mô hình và giọng đọc rồi dùng khung **Câu đọc nghe thử** ngay bên dưới. Nhập nội dung cần nghe (nên dùng câu ngắn để chờ nhanh) và bấm **Nghe thử giọng AI**. Trình phát xuất hiện ngay trong khung này; kịch bản dài không bị đổi và chưa được tạo thành âm thanh.
- Trong **Thư viện giọng**, bấm nút nghe thử để mở trình phát trong hộp thoại. Với IndexTTS, file giọng mẫu gốc và giọng AI đọc câu mới được ghi rõ là hai loại âm thanh riêng.
- Mẫu nghe thử chạy qua engine AI thật trên máy, không dùng giọng đọc của trình duyệt thay thế. Cần cài mô hình hoặc khởi động API tương ứng. Lần đầu có thể cần tải model; mẫu phải chờ nếu bộ xử lý đang bận.
- Câu nghe thử đã hoàn thành được lưu lại. Cùng mô hình/cấu hình, giọng, câu và thông số sẽ dùng lại file sẵn có. Có thể hủy khi đang chờ hoặc xử lý. Tác vụ nghe thử được tách khỏi lịch sử tạo nội dung chính.
- Kết quả và bản thu tham chiếu tạm nằm trong thư mục dữ liệu ứng dụng. Giọng chỉ được thêm vào thư viện khi bạn bấm lưu; nghe thử clone không tự tạo hồ sơ giọng đã lưu.

### Chọn mô hình ngay trong màn Clone

1. Mở **Clone giọng nói**. Màn hình hiển thị đủ 7 mô hình. Chọn một trong 5 mô hình hỗ trợ clone: **VieNeu-TTS, Chatterbox, GPT-SoVITS, Fish Speech hoặc IndexTTS**. Whisper và VibeVoice Realtime không chọn được cho clone file và có giải thích ngay trên thẻ.
2. Tải giọng mẫu hoặc thu âm; nghe **giọng gốc** bằng trình phát của file. Nhập ngôn ngữ/lời thoại đúng với bản thu và xác nhận quyền sử dụng.
3. Chọn **Ngôn ngữ nội dung mới** trong các ngôn ngữ mà engine hỗ trợ, nhập câu ngắn rồi bấm **Nghe thử giọng clone**. Mô hình dùng đúng file tham chiếu và lựa chọn của bạn.
4. Khi ưng ý, bấm **Lưu giọng & dùng [tên mô hình]**. Ứng dụng mở màn tạo giọng với đúng mô hình, giọng đã lưu và ngôn ngữ đầu ra vừa chọn. Bạn có thể nhập kịch bản dài và tạo sau đó.

Giọng đã lưu ghi nhớ mô hình ưu tiên. Nút **Dùng giọng này** trong kho giọng cá nhân sẽ chọn lại mô hình đó. Bạn vẫn có thể đổi mô hình clone khác bằng bộ chọn ở màn tạo giọng.

### Cập nhật từ 1.0/1.1

Đóng ứng dụng cũ, giải nén gói 1.2 vào thư mục mới rồi chạy **Start-Windows.bat**. Giữ nguyên thư mục dữ liệu `%LOCALAPPDATA%\QuanVoiceStudio` hoặc `QUAN_VOICE_DATA` để dùng lại các giọng, lịch sử và model đã cài. Không phải tải lại toàn bộ trọng số chỉ để cập nhật giao diện. Nếu giao diện cũ còn trong bộ nhớ trình duyệt, nhấn **Ctrl+F5** để tải lại.

## Mới trong phiên bản 1.1

- Mục **Giọng đọc** nay là danh sách chọn, gồm preset của mô hình và giọng bạn đã lưu.
- **Thư viện giọng → Giọng có sẵn trong mô hình**: duyệt, tìm kiếm theo tên, vùng miền, giới tính hoặc ngôn ngữ; bấm **Dùng giọng này** để chọn, hoặc **Tạo mẫu nghe**. Mẫu nghe dùng mô hình thật và nằm trong hàng đợi; cần cài model trước.
- VieNeu có danh sách **25 giọng v3 Turbo** và **11 giọng v3 Nano**, đọc từ JSON upstream theo đúng phiên bản; không gộp giọng của hai phiên bản. Chọn Nano trong thư viện rồi dùng một giọng Nano sẽ cập nhật cấu hình engine cục bộ sang Nano.
- VibeVoice liệt kê **25 preset đi kèm checkout** theo ngôn ngữ. Dùng tên file đầy đủ để tránh chọn nhầm do trùng tên. Có nút tải các gói giọng thử nghiệm được liên kết trong script chính thức Microsoft; sau khi tải, làm mới danh sách để quét toàn bộ preset thực sự đã cài.
- IndexTTS có **11 file mẫu tham chiếu** trong danh sách chính thức (01–09, 11, 12). Đây là file mẫu, không phải giọng được huấn luyện riêng có tên. File tải vào cache/thư mục ví dụ khi nghe hoặc tạo lần đầu.
- Chatterbox hiển thị giọng mặc định checkpoint (`conds.pt`, khi checkpoint có cung cấp) và hỗ trợ chọn giọng bạn clone; không bịa thêm danh sách nhiều tên giọng.
- Fish Speech đọc **giọng đã đăng ký trên API cục bộ** qua `/v1/references/list`. Chọn một giọng sẽ gửi đúng `reference_id` khi tạo. Đây không phải danh mục giọng có sẵn từ dịch vụ fish.audio trên Internet.
- GPT-SoVITS không có kho preset kèm repo; dùng giọng tham chiếu đã lưu. Whisper chỉ chép lời và không có giọng đọc.
- Nút **Giao diện** ở thanh trên cùng, hoặc **Cài đặt → Màu sắc & độ dễ đọc**: sáng/tối/theo hệ thống, 6 màu nhanh, màu tùy chọn, tương phản cao, cỡ chữ 100/110/120%. Áp dụng ngay và tự lưu trong trình duyệt. Mặc định chữ đậm hơn, lớn hơn và màu xanh dương dễ đọc.

### Cập nhật từ 1.0

Đóng ứng dụng và các cửa sổ xử lý trước. Giải nén gói 1.1 vào thư mục mới rồi chạy `Start-Windows.bat`. Giữ nguyên `%LOCALAPPDATA%\QuanVoiceStudio` (hoặc biến `QUAN_VOICE_DATA` bạn đã đặt) để dùng lại giọng, lịch sử, môi trường và trọng số; không xóa thư mục này. Với mô hình đã cài, không cần bấm cài lại chỉ để cập nhật giao diện và danh sách giọng.

## Có gì trong ứng dụng

- Văn bản thành giọng nói, tạo một file hoặc nhiều đoạn, hàng đợi xử lý tuần tự.
- Điều chỉnh tốc độ 0,5–2 lần bằng FFmpeg, xuất WAV hoặc MP3.
- Clone bằng giọng tham chiếu với VieNeu, Chatterbox Multilingual, GPT-SoVITS API v2, IndexTTS 2.5, Fish Speech API.
- Kho giọng mẫu, thu âm bằng micro (tối đa 60 giây), nghe mẫu, xem dạng sóng, dùng lại và xóa mẫu.
- Whisper chép lời, tải TXT và SRT.
- Lịch sử, tải kết quả, tạo lại, hủy tác vụ, nhật ký lỗi.
- Lưu/mở dự án JSON, nhập văn bản TXT. Dự án JSON không chứa âm thanh; sao lưu cả thư mục dữ liệu khi chuyển máy.
- Cài riêng từng engine, cấu hình đường dẫn Python, mã nguồn, checkpoint và CPU/CUDA. Không cài chung các thư viện AI vào một môi trường.

## Bảy dự án được tích hợp

| Dự án | Chế độ tích hợp | Tiếng Việt | Cách chạy |
| --- | --- | --- | --- |
| [VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS) | v3 Turbo hoặc Nano, TTS + clone | Có | SDK riêng, CPU ONNX mặc định |
| [Chatterbox](https://github.com/resemble-ai/chatterbox) | Multilingual, TTS + clone | Không trong bản này | SDK riêng, CPU hoặc CUDA |
| [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) | API v2, TTS + clone | Không | API trên cùng máy, cổng 9880 |
| [Fish Speech](https://github.com/fishaudio/fish-speech) | API chính thức, TTS + clone | Có, tùy checkpoint | Linux/WSL, cổng 8080 |
| [IndexTTS](https://github.com/index-tts/index-tts) | IndexTTS 2.5, clone + cảm xúc | Không | SDK, checkpoint IndexTTS-2.5 |
| [VibeVoice](https://github.com/microsoft/VibeVoice) | Realtime 0.5B, TTS preset | Không | CLI chính thức, preset theo ngôn ngữ |
| [Whisper](https://github.com/openai/whisper) | ASR: chép lời và phụ đề | Có | SDK, base mặc định |

VibeVoice Realtime không nhận file clone tùy ý; bản TTS nhiều người nói cũ đã được tác giả gỡ khỏi repository. Whisper không phải mô hình tạo giọng. Không có engine thay thế bằng giọng trình duyệt.

## Cài thêm mô hình

### VieNeu

Bộ cài dùng mã nguồn chính thức và core ONNX cho CPU. Trọng số Turbo tải ở lần tạo đầu. Nếu máy yếu, đổi phiên bản trong cấu hình sang `v3nano`; Nano có chất lượng thấp hơn và danh sách preset khác. Dùng preset Nano như `Minh Quân`, không dùng tên `Hải Đăng` của Turbo.

Muốn dùng CUDA, cần cài extra `cuda` của VieNeu vào đúng môi trường riêng và PyTorch tương thích theo README upstream. Chọn CUDA trong giao diện chỉ chọn thiết bị, không tự cài driver.

### Chatterbox

Nút Cài mô hình cài bản Multilingual từ mã nguồn. Trọng số tải lần đầu. Không chọn tiếng Việt; ứng dụng chỉ hiện các ngôn ngữ được bản này hỗ trợ. Cường độ cảm xúc dùng tham số exaggeration của mô hình.

### IndexTTS

Bộ cài dùng `uv sync --extra webui` và tải `IndexTeam/IndexTTS-2.5` vào thư mục `checkpoints`. Bỏ DeepSpeed để giảm vấn đề cài trên Windows. Chọn giọng mẫu trước khi tạo. Tùy chọn suy luận cảm xúc từ nội dung tải thêm bộ phân tích cảm xúc. Hiệu năng và khả năng CPU phụ thuộc thư viện upstream; CUDA được khuyến nghị khi phần cứng hỗ trợ.

### GPT-SoVITS

Cài tự động tải thư viện, bộ mã hóa và checkpoint v2. API `http://127.0.0.1:9880` tự khởi động khi dùng. `Start-GPT-SoVITS.bat` vẫn giữ để người dùng nâng cao mở thủ công nếu muốn. Giọng mẫu cần lời thoại chính xác và ngôn ngữ tương thích (en/zh/ja/ko/yue); v2 chưa hỗ trợ tiếng Việt.

Nếu bộ thư viện upstream không cài được trên máy, xem log; có thể trỏ cấu hình Python/mã nguồn tới bộ Windows chính thức của dự án. Không đổi endpoint sang máy ngoài; app hiện chỉ kết nối localhost.

### Fish Speech trên Windows qua WSL

Bộ cài tự bật WSL khi cần; Windows có thể yêu cầu quyền quản trị/khởi động lại. Khi WSL sẵn sàng, ứng dụng nhập Ubuntu 24.04 vào distro riêng `QuanVoice-Fish`, cài công cụ Linux, sao chép nguồn đã ghim revision, tạo môi trường Python 3.12 và tải `fishaudio/s2-pro`. API cổng 8080 tự mở khi dùng. Giọng tham chiếu gửi bằng base64 qua API, không cần ánh xạ đường dẫn Windows sang Linux.

Mặc định chạy CPU để không giả định máy có CUDA. Fish S2-Pro nặng và CPU có thể rất chậm hoặc không đủ RAM. GPU cần cấu hình driver và extra CUDA theo upstream; bản tự cài này chưa tự đổi cấu hình GPU trong WSL. Nếu WSL bị khóa bởi chính sách máy hoặc chưa bật ảo hóa, phần Fish báo lỗi và có thể thử lại sau; các engine khác vẫn cài tiếp.

Để tự quản lý server khác, tắt ứng dụng, sửa cấu hình API localhost phù hợp và khởi động server trước. Không xóa distro WSL nếu muốn giữ cache/trọng số. Bộ cài không gọi `wsl --unregister` hoặc tắt các distro khác.

### VibeVoice

Cài bản `streamingtts`; giọng mặc định `Carter`, hoặc giọng được cung cấp trong `demo/voices/streaming_model`. Tích hợp hiện có tiếng Anh cùng các ngôn ngữ của preset: Đức, Pháp, Ý, Nhật, Hàn, Hà Lan, Ba Lan, Bồ Đào Nha và Tây Ban Nha. Một số giọng là thử nghiệm; chất lượng tùy giọng. Checkpoint mặc định `microsoft/VibeVoice-Realtime-0.5B`, lưu cache sau lần tải đầu.

### Whisper

Cài từ Kho mô hình, chọn kích thước `tiny`, `base`, `small`, `medium`, `large`, `turbo`. `base` dễ bắt đầu trên CPU. Mở Âm thanh → văn bản, chọn file, ngôn ngữ và chạy. File nguồn và kết quả được giữ lại. Whisper cần FFmpeg.

## Dữ liệu được lưu ở đâu?

Từ bản 1.4.1, mặc định: `data` nằm cạnh thư mục `desktop` và `BAT_DAU.bat`, cùng ổ giải nén trên Windows/Linux. Biến `QUAN_VOICE_DATA` đặt thủ công vẫn có quyền ưu tiên. Xem hướng dẫn chuyển dữ liệu đầu tài liệu.

- `studio.db`: cấu hình, giọng, lịch sử.
- `voices/`: giọng mẫu và âm thanh nguồn đã chuẩn hóa WAV mono 24 kHz.
- `outputs/`: âm thanh tạo ra, TXT/SRT/JSON chép lời.
- `sources/`: các mã nguồn đã cài.
- `envs/`: môi trường Python riêng. IndexTTS và Fish dùng `.venv` bên trong mã nguồn của chúng.
- `cache/`: cache Hugging Face, PyTorch và Whisper.
- `jobs/`, `logs/`: tham số và nhật ký tác vụ.

Để chuyển ổ đĩa, đóng ứng dụng, sao chép toàn bộ thư mục dữ liệu sang đường dẫn mới, sửa lại đường dẫn môi trường Python/mã nguồn trong cấu hình. Có thể đặt `set QUAN_VOICE_DATA=D:\QuanVoiceData` trước khi chạy. Không cần tải lại trọng số khi cache và đường dẫn còn nguyên. Một số mô hình có tài nguyên phụ hoặc lần clone đầu cần tải thêm dữ liệu; không hứa toàn bộ chạy offline ngay sau khi chỉ cài thư viện.

## Lưu ý vận hành

- Bản web được xuất bản là giao diện và trình soạn dự án; inference chạy trong bản cục bộ. Không tải giọng mẫu lên máy chủ web.
- Các model AI cần nhiều RAM/dung lượng và có thể cần GPU. Dùng BAT_DAU_NHANH.bat để bắt đầu với VieNeu CPU và Whisper base nếu máy ít RAM/dung lượng.
- Đóng ứng dụng giữa tác vụ khiến tác vụ đó được đánh dấu lỗi khi mở lại, tránh lịch sử treo giả.
- Hủy tác vụ dừng tiến trình xử lý cục bộ. Với GPT-SoVITS/Fish API, server bên kia có thể tiếp tục tính toán tới khi hoàn thành; không có cam kết ngắt GPU từ API upstream.
- Nếu cài đặt bị gián đoạn, bấm cài lại để tiếp tục. Không tự cập nhật mã nguồn đã cài; gói này giữ revision trong `desktop/sources.lock.json`.
- Worker giữ model qua các tác vụ liên tiếp, giải phóng khi đổi model hoặc đóng phần mềm. Bộ xử lý ưu tiên một người dùng trên cùng máy.
- Chỉ clone giọng bạn có quyền sử dụng. Giữ nguyên giấy phép upstream. Mã nguồn có thể mở nhưng giấy phép trọng số không nhất thiết cho phép mọi mục đích thương mại.

## Phạm vi kiểm chứng

Đã kiểm tra cú pháp Python/JavaScript/PowerShell, các kiểm thử API và điều phối tự cài và kiểm tra logic dựng 7 màn giao diện; kiểm tra tỷ lệ tương phản chữ/nút với 18 tổ hợp sáng/tối và màu, lựa chọn preset theo phiên bản/ngôn ngữ và lưu cấu hình giao diện. Kiểm thử riêng luồng nghe thử/clone xác nhận đúng engine, giữ nguyên kịch bản, tách bản thu tạm khỏi giọng đã lưu, dùng cache và hủy tác vụ nghe thử. Kiểm thử API bao gồm: lưu dữ liệu, tải âm thanh, chuyển định dạng thực bằng FFmpeg, hàng đợi, hủy tác vụ, xuất phụ đề và chặn yêu cầu không hợp lệ. API adapter được đối chiếu với các revision mã nguồn đi kèm.

Chưa kiểm thử bố cục bằng trình duyệt, suy luận thật trên cả 7 bộ trọng số hoặc trên máy Windows/GPU của bạn. Cài đặt và khả năng chạy còn phụ thuộc phần cứng, driver, truy cập tải trọng số và các phụ thuộc upstream. Đây là bản tích hợp mã nguồn có thể cấu hình, chưa phải file EXE đã đóng gói sẵn mọi mô hình.

## Gói mã nguồn

Gói đầy đủ chứa `upstream/` của cả 7 dự án tại các commit trong `desktop/sources.lock.json`, bao gồm giấy phép và các asset vốn có trong checkout. Không chứa lịch sử `.git`, môi trường Python hoặc bộ trọng số lớn tải riêng từ Hugging Face; không cần tải lại mã nguồn để bắt đầu cài. Bản tải nhanh từ giao diện chỉ chứa ứng dụng và bộ cài; bộ cài tự lấy đúng commit trong lock khi chưa có nguồn đi kèm.

## Khắc phục cài đặt

- Nhật ký bộ cài: `<thư mục app>\data\bootstrap\setup.log`. Log từng engine: `logs/` trong thư mục dữ liệu, xem trực tiếp từ Lịch sử.
- Thiếu mạng: mở lại BAT_DAU.bat khi có mạng; không xóa cache. Model đã kiểm tra thành công với cấu hình không đổi sẽ được bỏ qua.
- Bận cổng 8765: đóng cửa sổ Studio cũ rồi chạy bản mới. Trình cài không tắt tiến trình không thuộc ứng dụng.
- WSL yêu cầu restart/ảo hóa: hoàn tất yêu cầu Windows, mở lại BAT_DAU.bat; xem `bootstrap/wsl.log`.
- Hủy/đóng khi đang cài có thể để lại môi trường dang dở; bấm Thử lại để sửa tiếp. Hủy yêu cầu gửi API bên ngoài không đảm bảo dừng ngay tính toán của API đó.
- Không đủ ổ/RAM: dùng bản khởi động nhanh; engine khác báo lỗi riêng và chưa được xem là đã chuẩn bị.

Nguồn công cụ: [Python 3.11.9](https://www.python.org/downloads/release/python-3119/), [MinGit](https://github.com/git-for-windows/git/releases), [FFmpeg builds](https://www.gyan.dev/ffmpeg/builds/), [Ubuntu WSL](https://cloud-images.ubuntu.com/wsl/releases/24.04/current/), [WSL](https://learn.microsoft.com/en-us/windows/wsl/basic-commands). URL, kích thước và SHA256 bộ cài đi kèm nằm trong `windows/assets-manifest.json`.
