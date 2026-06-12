# Requirements Document

## Introduction

Batch Video Merger là một công cụ desktop viết bằng Python có giao diện đồ họa (customtkinter/tkinter) dùng để ghép video hàng loạt từ hai thư mục. Thư mục thứ nhất chứa phần đầu (Folder_1), thư mục thứ hai chứa phần sau (Folder_2). Công cụ ghép từng cặp video một-đối-một, cắt đầu/cuối từng video trước khi ghép, chuẩn hóa định dạng đầu ra qua ffmpeg, tùy chọn resize về tỉ lệ 9:16, sau đó di chuyển an toàn các video gốc đã sử dụng sang thư mục lưu trữ riêng.

Mục tiêu chính là cho phép người dùng không rành kỹ thuật có thể ghép video số lượng lớn một cách tự động, an toàn dữ liệu (không xóa file gốc), có khả năng dừng giữa chừng và theo dõi tiến trình ngay trên giao diện. Công cụ không xuất bất kỳ file báo cáo hay log nào; mọi trạng thái xử lý chỉ được hiển thị trực tiếp trong khu vực trạng thái của giao diện theo thời gian thực. Giao diện được thiết kế theo hướng hiện đại, đẳng cấp và chuyên nghiệp để mang lại trải nghiệm trực quan, dễ dùng.

## Glossary

- **System**: Toàn bộ ứng dụng Batch Video Merger, bao gồm giao diện và logic xử lý.
- **GUI**: Thành phần giao diện đồ họa được xây dựng bằng customtkinter/tkinter.
- **Merge_Engine**: Thành phần thực thi việc cắt, chuẩn hóa và ghép video bằng ffmpeg.
- **Folder_1**: Thư mục nguồn chứa các video phần đầu do người dùng chọn.
- **Folder_2**: Thư mục nguồn chứa các video phần sau do người dùng chọn.
- **Output_Folder**: Thư mục đích do người dùng chọn để chứa kết quả.
- **Merged_Folder**: Thư mục con `Output/merged/` chứa các video đã ghép thành công.
- **Used_Folder_1**: Thư mục con `Output/used_folder_1/` chứa video gốc Folder_1 đã được dùng.
- **Used_Folder_2**: Thư mục con `Output/used_folder_2/` chứa video gốc Folder_2 đã được dùng.
- **Video_Pair**: Một cặp gồm một video từ Folder_1 và một video từ Folder_2 được ghép với nhau.
- **Supported_Format**: Các định dạng video được hỗ trợ: `.mp4`, `.mov`, `.mkv`, `.avi`, `.webm`.
- **Trim_Head**: Số giây cắt ở đầu mỗi video trước khi ghép.
- **Trim_Tail**: Số giây cắt ở cuối mỗi video trước khi ghép.
- **Merge_Order**: Chế độ sắp xếp cặp video, gồm "theo thứ tự tên file" (sort) hoặc "ngẫu nhiên" (shuffle).
- **Resize_Mode**: Chế độ xử lý kích thước, gồm "9:16 (1080x1920)" hoặc "giữ nguyên kích thước".
- **Resize_9_16_Submode**: Khi resize 9:16, gồm "Fit with padding" (nền đen/mờ) hoặc "Fill crop".
- **Quality_Preset**: Mức chất lượng đầu ra: Fast (CRF 28), Balanced (CRF 23, mặc định), High Quality (CRF 18).
- **ffmpeg**: Công cụ dòng lệnh dùng để cắt, chuẩn hóa và ghép video.
- **ffprobe**: Công cụ dòng lệnh dùng để đọc thông tin (thời lượng, kích thước) của video.
- **Status_Vocabulary**: Tập trạng thái có kiểm soát hiển thị trên giao diện: "Done", "Failed", "Skipped because video too short", "Skipped because unreadable", "Unused because no pair".
- **Theme_Mode**: Chế độ giao diện sáng/tối, với giao diện tối hiện đại là mặc định.
- **Progress_Bar**: Thanh tiến trình trên GUI hiển thị mức hoàn thành kèm phần trăm dạng văn bản.
- **Status_Area**: Khu vực trạng thái dạng cuộn trên GUI hiển thị diễn biến xử lý theo từng cặp theo thời gian thực.
- **Results_Summary_Panel**: Bảng tổng kết kết quả trên GUI hiển thị khi hoàn tất, gồm số cặp thành công, số cặp lỗi và số video thừa.
- **Stop_Request**: Yêu cầu dừng do người dùng kích hoạt qua nút Stop.

## Requirements

### Requirement 1: Chọn thư mục nguồn và thư mục xuất

**User Story:** Là người dùng, tôi muốn chọn Folder_1, Folder_2 và Output_Folder qua giao diện, để công cụ biết nguồn video và nơi lưu kết quả.

#### Acceptance Criteria

1. THE GUI SHALL cung cấp nút chọn Folder_1, nút chọn Folder_2 và nút chọn Output_Folder.
2. WHEN ứng dụng khởi động, THE GUI SHALL hiển thị trạng thái "chưa chọn" cho Folder_1, Folder_2 và Output_Folder.
3. WHEN người dùng chọn một thư mục cho Folder_1, THE GUI SHALL hiển thị đường dẫn tuyệt đối đầy đủ của Folder_1 trong vòng 1 giây.
4. WHEN người dùng chọn một thư mục cho Folder_2, THE GUI SHALL hiển thị đường dẫn tuyệt đối đầy đủ của Folder_2 trong vòng 1 giây.
5. WHEN người dùng chọn một thư mục cho Output_Folder, THE GUI SHALL hiển thị đường dẫn tuyệt đối đầy đủ của Output_Folder trong vòng 1 giây.
6. IF người dùng nhấn Start khi chưa chọn đủ Folder_1, Folder_2 và Output_Folder, THEN THE System SHALL hiển thị thông báo lỗi nêu rõ những thư mục còn thiếu, SHALL giữ nguyên các đường dẫn đã chọn và SHALL không bắt đầu xử lý.
7. IF người dùng nhấn Start khi Folder_1 trùng với Folder_2, hoặc khi Output_Folder trùng với hoặc nằm bên trong Folder_1 hoặc Folder_2, THEN THE System SHALL hiển thị thông báo lỗi nêu rõ xung đột thư mục và SHALL không bắt đầu xử lý.
8. IF người dùng nhấn Start khi một trong các thư mục đã chọn không còn tồn tại hoặc không thể truy cập, THEN THE System SHALL hiển thị thông báo lỗi nêu rõ thư mục không hợp lệ và SHALL không bắt đầu xử lý.

### Requirement 2: Thiết lập tham số cắt, thứ tự, resize và chất lượng

**User Story:** Là người dùng, tôi muốn thiết lập số giây cắt, chế độ ghép, chế độ resize và mức chất lượng, để kiểm soát cách video được xử lý.

#### Acceptance Criteria

1. THE GUI SHALL cung cấp ô nhập Trim_Head và Trim_Tail riêng cho Folder_1 và cho Folder_2, mỗi ô nhận giá trị số tính bằng giây.
2. WHEN ứng dụng khởi động, THE GUI SHALL đặt giá trị mặc định cho mỗi ô Trim_Head và Trim_Tail bằng 1 giây.
3. IF người dùng nhập vào bất kỳ ô Trim_Head hoặc Trim_Tail nào một giá trị không phải số thực không âm, hoặc nằm ngoài khoảng từ 0 đến 3600 giây, THEN THE System SHALL hiển thị thông báo lỗi nêu rõ ô nhập không hợp lệ và khoảng giá trị cho phép, SHALL giữ nguyên giá trị đã nhập và SHALL không bắt đầu xử lý.
4. THE GUI SHALL cung cấp tùy chọn Merge_Order gồm "theo thứ tự tên file" và "ngẫu nhiên", với "theo thứ tự tên file" là giá trị mặc định.
5. THE GUI SHALL cung cấp tùy chọn Resize_Mode gồm "9:16 (1080x1920)" và "giữ nguyên kích thước", với "giữ nguyên kích thước" là giá trị mặc định.
6. WHERE Resize_Mode là "9:16 (1080x1920)", THE GUI SHALL kích hoạt lựa chọn Resize_9_16_Submode gồm "Fit with padding" và "Fill crop", với "Fit with padding" là giá trị mặc định.
7. WHERE Resize_Mode là "giữ nguyên kích thước", THE GUI SHALL vô hiệu hóa lựa chọn Resize_9_16_Submode.
8. THE GUI SHALL cung cấp tùy chọn Quality_Preset gồm Fast, Balanced và High Quality, với Balanced là giá trị mặc định.

### Requirement 3: Quét và ghép cặp video

**User Story:** Là người dùng, tôi muốn công cụ quét video trong hai thư mục và ghép từng cặp một-đối-một, để mỗi video Folder_1 đứng trước video Folder_2 tương ứng.

#### Acceptance Criteria

1. WHEN quá trình xử lý bắt đầu, THE Merge_Engine SHALL quét các file nằm trực tiếp trong thư mục gốc của Folder_1 và Folder_2 (không quét đệ quy vào thư mục con) và chỉ chọn các file có phần mở rộng thuộc Supported_Format, với việc so khớp phần mở rộng không phân biệt chữ hoa chữ thường.
2. WHERE Merge_Order là "theo thứ tự tên file", THE Merge_Engine SHALL sắp xếp danh sách video của mỗi thư mục theo tên file tăng dần theo thứ tự bảng chữ cái không phân biệt chữ hoa chữ thường trước khi ghép cặp.
3. WHERE Merge_Order là "ngẫu nhiên", THE Merge_Engine SHALL xáo trộn ngẫu nhiên độc lập danh sách video của Folder_1 và danh sách video của Folder_2 trước khi ghép cặp.
4. THE Merge_Engine SHALL ghép cặp theo vị trí một-đối-một, trong đó video tại vị trí thứ N của Folder_1 đứng trước video tại vị trí thứ N của Folder_2.
5. THE Merge_Engine SHALL sử dụng mỗi video nguồn nhiều nhất một lần.
6. IF số lượng video của Folder_1 khác số lượng video của Folder_2, THEN THE Merge_Engine SHALL ghép số cặp bằng số lượng video của thư mục có ít video hơn.
7. THE Merge_Engine SHALL giữ nguyên tại thư mục gốc các video thừa không được ghép cặp và SHALL hiển thị trạng thái "Unused because no pair" cho từng video thừa đó trong Status_Area.

### Requirement 4: Cắt đầu/cuối và bỏ qua video quá ngắn

**User Story:** Là người dùng, tôi muốn công cụ cắt đầu/cuối mỗi video theo tham số tôi nhập, để loại bỏ phần thừa trước khi ghép.

#### Acceptance Criteria

1. WHEN xử lý một video, THE Merge_Engine SHALL đọc thời lượng gốc của video đó bằng ffprobe trước khi cắt.
2. WHEN xử lý một video, THE Merge_Engine SHALL cắt số giây Trim_Head ở đầu và Trim_Tail ở cuối theo tham số Trim_Head và Trim_Tail của thư mục chứa video đó (Folder_1 hoặc Folder_2).
3. IF thời lượng còn lại của một video sau khi cắt — được tính bằng thời lượng gốc đo bằng ffprobe trừ đi Trim_Head và Trim_Tail của thư mục chứa video đó — nhỏ hơn hoặc bằng 0 giây, THEN THE Merge_Engine SHALL bỏ qua cặp chứa video đó, SHALL hiển thị trạng thái "Skipped because video too short" cho cặp đó trong Status_Area và SHALL tiếp tục với cặp kế tiếp.
4. IF ffprobe trả về lỗi hoặc không xác định được thời lượng của một video, THEN THE Merge_Engine SHALL coi video đó là không đọc được, SHALL bỏ qua cặp chứa video đó, SHALL hiển thị trạng thái "Skipped because unreadable" kèm lý do lỗi cho cặp đó trong Status_Area và SHALL tiếp tục với cặp kế tiếp.

### Requirement 5: Chuẩn hóa và resize đầu ra

**User Story:** Là người dùng, tôi muốn video ghép được chuẩn hóa định dạng và tùy chọn resize 9:16, để các video xuất ra đồng nhất và phát được trên nhiều nền tảng.

#### Acceptance Criteria

1. THE Merge_Engine SHALL xuất mỗi video đã ghép ở định dạng `.mp4` với video codec libx264, audio codec AAC và pixel format yuv420p.
2. THE Merge_Engine SHALL đặt khung hình của mọi video xuất ra là đúng 30 FPS.
3. THE Merge_Engine SHALL đặt tần số lấy mẫu âm thanh của mọi video xuất ra là đúng 44100 Hz.
4. THE Merge_Engine SHALL áp dụng Quality_Preset đã chọn bằng giá trị CRF tương ứng: 28 cho Fast, 23 cho Balanced, 18 cho High Quality.
5. WHERE Resize_Mode là "9:16 (1080x1920)" và Resize_9_16_Submode là "Fit with padding", THE Merge_Engine SHALL co video về vừa khung 1080x1920 trong khi giữ nguyên tỉ lệ khung hình gốc, đặt video vào chính giữa khung và lấp đầy phần trống còn lại bằng nền đen.
6. WHERE Resize_Mode là "9:16 (1080x1920)" và Resize_9_16_Submode là "Fill crop", THE Merge_Engine SHALL phóng video để phủ đầy khung 1080x1920 trong khi giữ nguyên tỉ lệ khung hình gốc, rồi cắt cân giữa phần dư vượt khung sao cho kích thước cuối cùng đúng 1080x1920.
7. WHERE Resize_Mode là "giữ nguyên kích thước", THE Merge_Engine SHALL chuẩn hóa video Folder_2 của cặp về đúng chiều rộng và chiều cao của video Folder_1 trong cùng cặp trước khi ghép, trong khi giữ nguyên tỉ lệ khung hình gốc và lấp phần trống bằng nền đen nếu có.

### Requirement 6: Đặt tên file đầu ra và file gốc đã dùng

**User Story:** Là người dùng, tôi muốn file kết quả và file gốc đã dùng được đặt tên theo quy ước rõ ràng, để dễ tra cứu và tránh ghi đè.

#### Acceptance Criteria

1. WHEN một cặp được ghép thành công, THE Merge_Engine SHALL đặt tên file kết quả theo định dạng `merged_<STT>__<ten-f1>__<ten-f2>.mp4`, trong đó `<ten-f1>` và `<ten-f2>` là tên file gốc của video Folder_1 và Folder_2 sau khi loại bỏ phần mở rộng, và `<STT>` là số thứ tự của cặp được biểu diễn bằng ba chữ số có số 0 ở đầu, bắt đầu từ 001 và tăng dần 1 đơn vị cho mỗi cặp.
2. IF số thứ tự cặp vượt quá 999, THEN THE Merge_Engine SHALL biểu diễn `<STT>` bằng đủ số chữ số cần thiết mà không cắt bớt giá trị số thứ tự.
3. WHEN di chuyển video gốc Folder_1 đã dùng, THE Merge_Engine SHALL đổi tên thành `<STT>_F1_<ten>.mp4` trong Used_Folder_1, trong đó `<STT>` là số thứ tự ba chữ số của cặp tương ứng và `<ten>` là tên file gốc sau khi loại bỏ phần mở rộng.
4. WHEN di chuyển video gốc Folder_2 đã dùng, THE Merge_Engine SHALL đổi tên thành `<STT>_F2_<ten>.mp4` trong Used_Folder_2, trong đó `<STT>` là số thứ tự ba chữ số của cặp tương ứng và `<ten>` là tên file gốc sau khi loại bỏ phần mở rộng.
5. THE Merge_Engine SHALL sử dụng cùng một giá trị `<STT>` cho file kết quả và cho hai file gốc đã dùng thuộc cùng một cặp.
6. IF tên file đích đã tồn tại trong thư mục đích, THEN THE Merge_Engine SHALL thêm hậu tố `_<n>` ngay trước phần mở rộng, trong đó `<n>` là số nguyên bắt đầu từ 1 và tăng dần 1 đơn vị cho đến khi tạo được tên file chưa tồn tại trong thư mục đích.

### Requirement 7: Cấu trúc thư mục đầu ra và di chuyển an toàn

**User Story:** Là người dùng, tôi muốn kết quả được sắp xếp theo cấu trúc cố định và video gốc chỉ bị di chuyển khi đã ghép thành công, để dữ liệu của tôi luôn an toàn.

#### Acceptance Criteria

1. WHEN quá trình xử lý bắt đầu, THE System SHALL tạo các thư mục Merged_Folder, Used_Folder_1 và Used_Folder_2 bên trong Output_Folder nếu chưa tồn tại.
2. IF System không tạo được một trong các thư mục con do thiếu quyền ghi, THEN THE System SHALL hiển thị thông báo lỗi nêu rõ thư mục không tạo được và SHALL không bắt đầu xử lý.
3. WHEN một cặp được ghép, THE Merge_Engine SHALL xác nhận file kết quả tồn tại trong Merged_Folder và có kích thước lớn hơn 0 byte trước khi coi cặp đó là thành công.
4. WHEN một cặp được xác nhận thành công, THE Merge_Engine SHALL di chuyển hai video gốc sang Used_Folder_1 và Used_Folder_2 bằng thao tác move, và SHALL xác nhận cả hai file đã tồn tại tại thư mục đích sau khi di chuyển.
5. IF việc ghép một cặp thất bại, THEN THE Merge_Engine SHALL giữ nguyên hai video gốc tại thư mục gốc và SHALL không di chuyển chúng.
6. IF System không có đủ quyền để di chuyển một video gốc, THEN THE Merge_Engine SHALL giữ nguyên hai video gốc tại thư mục gốc, SHALL hiển thị trạng thái "Failed" kèm lý do lỗi di chuyển cho cặp đó trong Status_Area và SHALL tiếp tục với cặp kế tiếp.

### Requirement 8: Giao diện chuyên nghiệp, hiển thị tiến trình và trạng thái

**User Story:** Là người dùng, tôi muốn một giao diện hiện đại, đẳng cấp và chuyên nghiệp hiển thị tiến trình cùng trạng thái xử lý theo thời gian thực, để biết công cụ đang làm gì và còn bao nhiêu việc.

#### Acceptance Criteria

1. THE GUI SHALL được xây dựng bằng customtkinter và SHALL hỗ trợ Theme_Mode sáng/tối, với giao diện tối hiện đại là mặc định.
2. THE GUI SHALL sắp xếp các điều khiển thành các nhóm trực quan tách biệt rõ ràng gồm: nhóm nguồn (Sources), nhóm thiết lập cắt (Trim settings), nhóm tùy chọn đầu ra (Output options) và nhóm hành động kèm tiến trình (Actions/Progress).
3. THE GUI SHALL cung cấp Progress_Bar, Status_Area, Results_Summary_Panel, nút Start và nút Stop, trong đó nút Start được tạo kiểu là nút chính (primary) và nút Stop được tạo kiểu là nút phụ (secondary).
4. THE GUI SHALL đặt kích thước cửa sổ tối thiểu là 900x650 pixel và SHALL duy trì bố cục rộng rãi, gọn gàng với typography dễ đọc khi cửa sổ được phóng lớn hơn kích thước tối thiểu.
5. WHEN quá trình xử lý bắt đầu, THE GUI SHALL đặt lại Progress_Bar về 0%, hiển thị phần trăm hoàn thành dạng văn bản và hiển thị tổng số cặp dự kiến.
6. WHEN một cặp được xử lý xong, THE GUI SHALL cập nhật Progress_Bar và phần trăm dạng văn bản trong vòng 1 giây bằng tỉ lệ số cặp đã xử lý chia cho tổng số cặp dự kiến.
7. WHILE quá trình xử lý đang chạy, THE GUI SHALL hiển thị trong Status_Area có khả năng cuộn dòng diễn biến cho cặp đang xử lý hiện tại gồm số thứ tự cặp, tên file Folder_1, tên file Folder_2 và trạng thái thuộc Status_Vocabulary, và cập nhật thông tin này trong vòng 1 giây sau khi chuyển sang cặp mới.
8. WHILE quá trình xử lý đang chạy, THE GUI SHALL vô hiệu hóa nút Start và kích hoạt nút Stop.
9. WHEN toàn bộ quá trình xử lý kết thúc, THE GUI SHALL đặt Progress_Bar về 100% và hiển thị trong Results_Summary_Panel số cặp thành công, số cặp lỗi và số video thừa, mỗi giá trị là một số nguyên không âm.
10. WHILE quá trình xử lý đang chạy, THE System SHALL thực thi việc xử lý trên một luồng (thread) tách biệt với luồng giao diện để GUI không bị treo.

### Requirement 9: Dừng xử lý an toàn

**User Story:** Là người dùng, tôi muốn dừng quá trình giữa chừng một cách an toàn, để không làm hỏng video đang xuất.

#### Acceptance Criteria

1. WHILE quá trình xử lý đang chạy, WHEN người dùng nhấn nút Stop, THE System SHALL ghi nhận Stop_Request và hiển thị trong Status_Area trạng thái đang chờ dừng trong vòng 1 giây.
2. WHILE đang có Stop_Request, THE Merge_Engine SHALL hoàn tất xử lý cặp hiện tại rồi dừng trước khi bắt đầu cặp kế tiếp.
3. WHEN dừng do Stop_Request, THE Merge_Engine SHALL không di chuyển video gốc của bất kỳ cặp nào chưa ghép xong.
4. WHEN dừng do Stop_Request, THE System SHALL giữ nguyên tại thư mục gốc toàn bộ video của các cặp chưa được xử lý hoàn tất.
5. WHEN dừng do Stop_Request, THE System SHALL giữ lại file kết quả và các video gốc đã di chuyển của những cặp đã hoàn tất thành công trước thời điểm dừng.
6. WHEN dừng do Stop_Request, THE System SHALL hiển thị trong GUI thông báo đã dừng kèm số cặp thành công, số cặp lỗi và số cặp chưa xử lý, mỗi giá trị là một số nguyên không âm.
7. WHEN quá trình đã dừng hoàn toàn do Stop_Request, THE GUI SHALL kích hoạt lại nút Start.

### Requirement 10: Kiểm tra ffmpeg/ffprobe và xử lý lỗi không dừng toàn bộ

**User Story:** Là người dùng, tôi muốn công cụ kiểm tra ffmpeg/ffprobe và xử lý lỗi gọn gàng, để một lỗi đơn lẻ không làm hỏng toàn bộ tiến trình.

#### Acceptance Criteria

1. WHEN người dùng nhấn Start, THE System SHALL kiểm tra sự hiện diện của ffmpeg và ffprobe và hoàn tất việc kiểm tra trong vòng 10 giây trước khi bắt đầu xử lý.
2. IF ffmpeg hoặc ffprobe không khả dụng, THEN THE System SHALL hiển thị trong Status_Area thông báo nêu rõ công cụ còn thiếu (ffmpeg và/hoặc ffprobe) kèm hướng dẫn cài đặt và SHALL không bắt đầu xử lý.
3. IF Folder_1 hoặc Folder_2 không chứa ít nhất một video thuộc Supported_Format, THEN THE System SHALL hiển thị trong Status_Area thông báo nêu rõ thư mục nào rỗng và SHALL không bắt đầu xử lý.
4. IF việc ghép một cặp khiến ffmpeg kết thúc với mã thoát khác 0 hoặc không tạo được file kết quả hợp lệ (file không tồn tại hoặc có kích thước bằng 0 byte), THEN THE Merge_Engine SHALL giữ nguyên hai video gốc tại thư mục gốc, SHALL hiển thị trạng thái "Failed" kèm lý do lỗi cho cặp đó trong Status_Area và SHALL tiếp tục với cặp kế tiếp.
5. WHILE xử lý nhiều cặp, IF một cặp bất kỳ gặp lỗi, THEN THE System SHALL tiếp tục xử lý toàn bộ các cặp còn lại và SHALL không kết thúc toàn bộ tiến trình do lỗi của một cặp đơn lẻ.

### Requirement 11: Tài liệu hướng dẫn cài đặt và đóng gói

**User Story:** Là người dùng, tôi muốn có hướng dẫn cài đặt và đóng gói, để có thể cài và chạy công cụ kể cả khi không rành kỹ thuật.

#### Acceptance Criteria

1. THE System SHALL kèm theo một tài liệu hướng dẫn ở dạng văn bản, trong đó liệt kê tên tất cả thư viện Python cần thiết và lệnh cài đặt cụ thể cho từng thư viện.
2. THE System SHALL trong tài liệu hướng dẫn cung cấp các bước cài đặt ffmpeg và ffprobe trên Windows, kèm bước kiểm tra xác nhận cả ffmpeg và ffprobe đã khả dụng.
3. THE System SHALL trong tài liệu hướng dẫn cung cấp các bước chạy công cụ từ mã nguồn.
4. THE System SHALL trong tài liệu hướng dẫn cung cấp các bước đóng gói công cụ thành file `.exe` bằng PyInstaller.
5. THE System SHALL trong tài liệu hướng dẫn giải thích cấu trúc các thư mục con Merged_Folder, Used_Folder_1 và Used_Folder_2 bên trong Output_Folder, cùng cách công cụ xử lý các video thừa không có cặp.
