# TekDT BMC
TekDT BMC là công cụ tạo thiết bị có thể chứa nhiều bộ cài hệ điều hành, tương thích với nhiều loại máy tính có cấu hình khác nhau và quá trình cài đặt hệ điều hành diễn ra một cách tự động.
- Tên phần mềm: TekDT BMC
- Tác giả: TekDT
- Mô tả: Phần mềm tạo USB boot tương thích với nhiều cấu hình máy tính khác nhau, tích hợp cài đặt phần mềm tự động sau khi cài đặt Windows.
- Ngày phát hành: 29-11-2025
- Phiên bản: 1.0.4
- Email: dinhtrungtek@gmail.com
- Telegram: @tekdt1152
- Facebook: @tekdtcom

# Tải xuống
Phiên bản mới nhất tại [https://github.com/tekdt/tekdtbmc/releases/download/v1.0.4/TekDT.BMC_v1.0.4.zip]
Mã hash SHA256 của chữ ký của TekDT là: 4ef06065990138ab401948b95f536272. Nếu đúng mã hash thì mới chính xác từ TekDT.
MD5 cho phiên bản v1.0.4: 7fecbf2cc89167f4af2937d0751bed7e

# Hướng dẫn sử dụng
Ở giao diện chương trình sẽ có tổng cộng 3 bước, bao gồm: CHỌN USB, CHỌN HOẶC TẢI ISO, THÊM PHẦN MỀM ĐƯỢC CÀI ĐẶT TỰ ĐỘNG SAU KHI CÀI WINDOWS
- Bước 1: Chọn thiết bị USB
  + Danh sách sổ xuống: Sẽ hiển thị toàn bộ các thiết bị.
  + Hiển thị ổ cứng: Chức năng này hiện tại chưa hoạt động ổn định (không nên sử dụng, có thể gây mất dữ liệu)

- Bước 2: Chọn ISO
  + Thêm ISO từ máy: Chọn ISO có sẵn trên ổ cứng. Khuyến khích sử dụng ISO được tải chính thức từ Microsoft thay cho ISO tuỳ biến.
  + Xoá ISO đã chọn: Chọn từng ISO và nút này sẽ loại nó khỏi danh sách.
  + Tải tự động từ Microsoft: Nếu như chưa có ISO thì có thể tick chọn và tải hàng loạt các ISO bạn muốn.
  + Tải các mục đã chọn: Sau khi chọn các phiên bản ISO muốn tải, thì nút này sẽ tải lần lượt hết tất cả những phiên bản ISO được tick.

- Bước 3: Chọn phần mềm cài đặt tự động sau khi cài đặt Windows hoàn tất.
  + Dựa vào danh sách phần mềm thì Tải (nếu phần mềm chưa có, cần internet) hoặc thêm vào danh sách được cài tự động. Chương trình sẽ tự động copy TekDT AIS vào thiết bị boot, và tự cấu hình gọi nó để cài đặt phần mềm cần thiết tự động, bạn không cần làm gì thêm.
  + Sau khi hoàn tất mọi thứ thì nhấn Bắt đầu để tạo USB.

Có một số tuỳ chọn thêm ở nút Menu (góc trái trên giao diện):
- Cấu trúc ổ đĩa: Mặc định chọn GPT để tương thích nhiều hơn (theo tài liệu Ventoy), nếu không tương thích hãy chọn MBR.
- Định dạng: Mặc định là ExFAT, bạn cũng có thể chọn các định dạng khác.
- Lấp đầy dung lượng: Mặc định là Có, nếu là Có thì USB của bạn sẽ được lấp đầy để trở thành 0 byte trống. Như vậy sẽ giảm thiệt hại do virus phá dữ liệu bên trong (đặc biệt virus shortcut) và tránh lây nhiêm virus cho máy khác.
- Lược bỏ phiên bản không được chọn trong ISO: Mặc định là Có, nếu là Có thì ở bước 2 khi chọn một phiên bản Windows trong một ISO (chẳng hạn như chọn bản Pro), thì các phiên bản còn lại (như Home, Education,...) sẽ bị loại bỏ hoàn toàn, chỉ giữ lại mỗi phiên bản Pro. Tuy nhiên, điều này sẽ tốn thêm chút thời gian, để chương trình xử lý loại bỏ các phiên bản khác. Điều này sẽ lấy thêm được một ít dung lượng cho thiết bị của bạn, vì đã bỏ bớt các phiên bản không dùng.
- Lọc và chỉ lấy những phần mềm được Thêm: Mặc định là Có, Ở bước thứ 3 của bạn sẽ chọn các phần mềm được Thêm vào danh sách sẽ được cài đặt sau khi cài Windows xong. Chương trình sẽ loại bỏ lại các phần mềm không được Thêm (không cần tự động cài đặt sau khi cài đặt Windows xong), để lấy thêm dung lượng ổ cứng, tránh lấy hết toàn bộ phần mềm không cần thiết.
- Giao diện: Mặc định Không có (không chọn). Đây là tuỳ chọn ở màn hình boot, hỗ trợ cho Ventoy. Nếu bạn có giao diện đẹp hơn, hãy copy vào thư mục Themes của TekDT BMC.

#Lưu ý: Chương trình này cần kết nối internet để hoạt động lần đầu tiên, do cần tải các công cụ cần thiết khác trong thư mục Tools như: Ventoy, 7z, aria2, wimlib, TekDT AIS,... Với giao diện thứ 3, giao diện này sẽ nhúng thêm giao diện chương trình TekDT AIS, cho nên nếu bạn muốn tải phần mềm mới thì cần có kết nối internet để tải, còn nếu trước đó đã tải một vài (hoặc toàn bộ) phần mềm đã đủ dùng thì không cần kết nối internet nữa.

# Trách nhiệm
TekDT không chịu trách nhiệm khi bạn sử dụng phần mềm/script này hoặc tải ở các nguồn khác được tuỳ biến, sửa đổi dựa trên phần mềm/ này. Bạn có thể sử dụng chương phần mềm/script miễn phí thì hãy tin nó. TekDT sẽ không thu thập thông tin hay làm hại đến máy tính của bạn.
Nếu bạn không tin tưởng phần mềm/script này, hãy xoá phần mềm/script đã tải.

# Hỗ trợ:
Mọi liên lạc của bạn với TekDT sẽ rất hoan nghênh và đón nhận để TekDT có thể cải tiến phần mềm/script này tốt hơn. Hãy thử liên hệ với TekDT bằng những cách sau:
- Telegram: @tekdt1152
- Zalo: 0944.095.092
- Email: dinhtrungtek@gmail.com
- Facebook: @tekdtcom

# Đóng góp:
Để phần mềm/script ngày càng hoàn thiện và nhiều tính năng hơn. TekDT cũng cần có động lực để duy trì. Nếu phần mềm/script này có ích với công việc của bạn, hãy đóng góp một chút. TekDT rất cảm kích việc làm chân thành này của bạn.
- MOMO: https://me.momo.vn/TekDT1152
- Biance ID: 877691831
- USDT (BEP20): 0x53a4f3c22de1caf465ee7b5b6ef26aed9749c721
