Lab này mô phỏng lỗ hổng HTTP Request Smuggling (HRS)
Backend (app.py): Một ứng dụng Flask có các route:
    index:
    /login → đăng nhập với user alice/alice hoặc admin
    login
    /admin → chỉ dành cho truy cập nội bộ, bình thường sẽ bị chặn

Proxy (proxy_safe.py): Chạy ở port 8888. Proxy này có logic đặc biệt cho phép thực hiện tấn công request smuggling.

Templates (index.html,ok.html): giao diện đẹp, có gợi ý về cách khai thác (smuggle request thứ 2 → /admin)
Khi khai thác thành công, truy cập /admin sẽ hiển thị flag

Mục tiêu của lab là giúp bạn thực hành cách gửi yêu cầu smuggled để vượt qua cơ chế xác thực thông thường, từ đó truy cập được /admin.

(Lab hơi khác 1 tí do kỹ thuật code, vui lòng đọc kỹ code để có hướng khai thác đúng)
