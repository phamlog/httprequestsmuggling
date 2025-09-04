# app.py
# Backend Flask (server chuẩn giải mã chunked theo HTTP/1.1 => TE-first).
# 3 trang: / (index), /login, /admin
# - alice:alice => hiển thị "Đăng nhập đúng (user thường)"
# - admin:12345 => redirect /admin (chỉ là "gợi ý" đường dẫn; thực vào /admin phải có header nội bộ)
# - /admin chỉ cho vào khi có header X-Internal-Admin: 1 (được proxy chèn cho request "smuggled")

from flask import Flask, request, redirect, url_for, render_template_string

app = Flask(__name__)

TPL_INDEX = """
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <title>Index</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root{
      --bg1:#8EC5FC; --bg2:#E0C3FC;
      --card:#ffffff; --text:#0f172a; --muted:#64748b;
      --primary:#6366f1; --primary-600:#5458f0; --primary-700:#4044ee;
      --ring: rgba(99,102,241,.35);
    }
    *{box-sizing:border-box}
    body{
      margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Inter, "Helvetica Neue", Arial;
      color:var(--text);
      background: linear-gradient(135deg, var(--bg1), var(--bg2)) fixed;
      min-height:100vh; display:grid; place-items:center; padding:24px;
    }
    .card{
      width:min(680px, 92vw); background:var(--card); border-radius:20px;
      box-shadow: 0 20px 60px rgba(2,6,23,.15);
      overflow:hidden; animation:pop .5s ease-out both;
    }
    .hero{
      background: radial-gradient(1200px 400px at 0% 0%, rgba(255,255,255,.6), transparent),
                  radial-gradient(1200px 400px at 100% 0%, rgba(255,255,255,.35), transparent),
                  linear-gradient(135deg,#a78bfa,#60a5fa);
      color:#fff; padding:32px 28px;
    }
    .hero h1{ margin:0 0 8px; font-size:32px; letter-spacing:.3px }
    .hero p{ margin:0; opacity:.95 }
    .body{ padding:28px }
    .lead{ color:var(--muted); margin:0 0 16px; font-size:16px }
    .btn{
      display:inline-block; background:var(--primary); color:#fff; text-decoration:none;
      padding:12px 18px; border-radius:12px; font-weight:600; transition:.2s ease;
      box-shadow:0 8px 24px var(--ring);
    }
    .btn:hover{ background:var(--primary-600); transform:translateY(-1px) }
    .btn:active{ background:var(--primary-700); transform:translateY(0) }
    @keyframes pop{ from{ transform:translateY(8px); opacity:0 } to{ transform:none; opacity:1 } }
  </style>
</head>
<body>
  <main class="card">
    <section class="hero">
      <h1>Trang Index</h1>
      <p>Lab HTTP Request Smuggling (CL.TE) – demo login → admin</p>
    </section>
    <section class="body">
      <p class="lead">Bắt đầu tại trang đăng nhập để kiểm thử luồng.</p>
      <a class="btn" href="/login">Đi tới /login</a>
    </section>
  </main>
</body>
</html>
"""


TPL_LOGIN = """
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <title>Login</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root{
      --bg1:#8EC5FC; --bg2:#E0C3FC;
      --card:#ffffff; --text:#0f172a; --muted:#64748b;
      --border:#e2e8f0; --input:#f8fafc;
      --primary:#22c55e; --primary-600:#16a34a; --primary-700:#15803d;
      --ring: rgba(34,197,94,.35);
    }
    *{box-sizing:border-box}
    body{
      margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Inter, "Helvetica Neue", Arial;
      color:var(--text);
      background: linear-gradient(135deg, var(--bg1), var(--bg2)) fixed;
      min-height:100vh; display:grid; place-items:center; padding:24px;
    }
    .card{
      width:min(720px, 94vw); background:var(--card); border-radius:20px;
      box-shadow: 0 20px 60px rgba(2,6,23,.15); overflow:hidden; animation:pop .5s ease-out both;
      display:grid; grid-template-columns:1.1fr .9fr;
    }
    @media (max-width: 840px){ .card{ grid-template-columns:1fr } .side{ display:none } }
    .header{ padding:28px 28px 0 }
    .header h1{ margin:0 0 6px; font-size:28px }
    .header p{ margin:0; color:var(--muted) }
    form{ padding:20px 28px 28px; display:grid; gap:14px }
    label{ font-weight:600; font-size:14px }
    .field{
      display:flex; gap:12px; align-items:center; background:var(--input);
      border:1px solid var(--border); border-radius:12px; padding:10px 12px;
      transition:border .15s ease, box-shadow .15s ease, transform .05s ease;
    }
    .field:focus-within{ border-color:#a5b4fc; box-shadow:0 0 0 6px rgba(99,102,241,.1) }
    .field input{
      border:none; outline:none; background:transparent; width:100%;
      font-size:16px; padding:4px 2px;
    }
    .hint{ color:var(--muted); font-size:13px; margin-top:2px }
    .btn{
      background:var(--primary); color:#fff; border:none; padding:12px 18px;
      border-radius:12px; font-weight:700; cursor:pointer; transition:.2s ease;
      box-shadow:0 10px 26px var(--ring);
    }
    .btn:hover{ background:var(--primary-600); transform:translateY(-1px) }
    .btn:active{ background:var(--primary-700); transform:translateY(0) }
    .side{
      background: radial-gradient(1200px 400px at 0% 0%, rgba(255,255,255,.6), transparent),
                  linear-gradient(135deg,#34d399,#60a5fa);
      padding:28px; color:#0b1220; display:flex; flex-direction:column; justify-content:center;
    }
    .badge{
      display:inline-block; background:#ecfeff; color:#0e7490; border:1px solid #a5f3fc;
      padding:6px 10px; border-radius:999px; font-weight:700; margin-bottom:10px; font-size:12px;
    }
    ul{ margin:10px 0 0 18px; padding:0; color:#0b1220 }
    li{ margin:4px 0 }
    @keyframes pop{ from{ transform:translateY(8px); opacity:0 } to{ transform:none; opacity:1 } }
  </style>
</head>
<body>
  <main class="card">
    <section>
      <div class="header">
        <h1>Đăng nhập</h1>
        <p>Nhập thông tin để tiếp tục.</p>
      </div>
      <form method="POST" action="/login" autocomplete="off">
        <div>
          <label>Username</label>
          <div class="field"><input name="username" placeholder="alice hoặc admin" /></div>
        </div>
        <div>
          <label>Password</label>
          <div class="field"><input name="password" type="password" placeholder="alice" /></div>
        </div>
        <button class="btn" type="submit">Đăng nhập</button>
        <p class="hint">Tài khoản mẫu: <strong>alice/alice</strong> (user thường), <strong>admin</strong> (redirect /admin)</p>
      </form>
    </section>  

    <aside class="side">
      <span class="badge">Demo Lab • HRS CL.TE</span>
      <h3 style="margin:6px 0 6px">Gợi ý</h3>
      <ul>
        <li>Frontend CL-first, Backend TE-first</li>
        <li>Smuggle request thứ 2 → /admin</li>
      </ul>
    </aside>
  </main>
</body>
</html>
"""


TPL_USER_OK = """
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <title>OK</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root{ --bg:#f8fafc; --card:#ffffff; --text:#0f172a; --muted:#64748b; --primary:#0ea5e9 }
    *{box-sizing:border-box}
    body{
      margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Inter, Arial;
      color:var(--text); background:var(--bg); min-height:100vh; display:grid; place-items:center; padding:24px;
    }
    .card{
      width:min(640px, 92vw); background:var(--card); border-radius:20px; padding:28px;
      box-shadow: 0 20px 60px rgba(2,6,23,.1); animation:pop .5s ease-out both;
    }
    h1{ margin:0 0 10px }
    p{ margin:0 0 12px; color:var(--muted) }
    a{ color:#fff; text-decoration:none; background:var(--primary); padding:10px 14px; border-radius:12px; font-weight:700 }
    a:hover{ filter:brightness(.95) }
    @keyframes pop{ from{ transform:translateY(8px); opacity:0 } to{ transform:none; opacity:1 } }
  </style>
</head>
<body>
  <main class="card">
    <h1>Đăng nhập đúng (user thường)</h1>
    <p>Xin chào, <strong>{{u}}</strong>.</p>
    <a href="/">Về trang chủ</a>
  </main>
</body>
</html>
"""


TPL_ADMIN = """
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <title>Admin</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root{
      --bg1:#ffecd2; --bg2:#fcb69f; --card:#ffffff; --text:#0f172a;
      --accent:#f97316; --accent-600:#ea580c;
    }
    *{box-sizing:border-box}
    body{
      margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Inter, Arial;
      color:var(--text);
      background: linear-gradient(135deg, var(--bg1), var(--bg2)) fixed;
      min-height:100vh; display:grid; place-items:center; padding:24px;
    }
    .card{
      width:min(720px, 94vw); background:var(--card); border-radius:20px; overflow:hidden;
      box-shadow: 0 24px 70px rgba(2,6,23,.18); animation:pop .5s ease-out both;
    }
    .hero{ padding:28px; background:linear-gradient(135deg, #fb923c, #fca5a5); color:#0b1220 }
    .hero h1{ margin:0 0 6px }
    .body{ padding:26px }
    .flag{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      background:#0b1220; color:#e2e8f0; padding:14px 16px; border-radius:12px; margin:8px 0 16px; overflow:auto;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,.08);
    }
    a.btn{ display:inline-block; background:var(--accent); color:#fff; text-decoration:none; padding:10px 14px; border-radius:12px; font-weight:700 }
    a.btn:hover{ background:var(--accent-600) }
    @keyframes pop{ from{ transform:translateY(8px); opacity:0 } to{ transform:none; opacity:1 } }
  </style>
</head>
<body>
  <main class="card">
    <section class="hero">
      <h1>Trang Admin</h1>
      <p>Truy cập nội bộ hợp lệ (được proxy chèn header).</p>
    </section>
    <section class="body">
      <div class="flag">flag:"you_successful_exploit_HRS_CL.TE"</div>
      <a class="btn" href="/">Về trang chủ</a>
    </section>
  </main>
</body>
</html>
"""


@app.route("/", methods=["GET","POST"])
def index():
    return render_template_string(TPL_INDEX)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template_string(TPL_LOGIN)

    username = request.form.get("username", "")
    password = request.form.get("password", "")

    if username == "alice" and password == "alice":
        return render_template_string(TPL_USER_OK, u=username)

    if username == "admin" and password == "12345":
        # Đúng đặc tả: gợi ý /admin (302). Vào được hay không do proxy có chèn header nội bộ không.
        return redirect(url_for("admin"))

    return "Sai tài khoản hoặc mật khẩu", 403

@app.route("/admin")
def admin():
    # KHÓA /admin: chỉ cho vào nếu có header nội bộ do proxy chèn cho request "smuggled"
    if request.headers.get("X-Internal-Admin") == "1":
        return render_template_string(TPL_ADMIN)
    return "Forbidden", 403

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=9000, debug=True)
