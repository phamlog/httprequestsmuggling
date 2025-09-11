# app.py (refactor dùng templates riêng)
from flask import Flask, request, redirect, url_for, render_template

app = Flask(__name__)

@app.route("/", methods=["GET","POST"])
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username", "")
    password = request.form.get("password", "")

    if username == "alice" and password == "alice":
        return render_template("ok.html", u=username)

    if username == "admin" and password == "12345":
        return redirect(url_for("admin"))

    return "Sai tài khoản hoặc mật khẩu", 403

@app.route("/admin")
def admin():
    if request.headers.get("X-Internal-Admin") == "1":
        return render_template("admin.html")
    return "Forbidden", 403

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=9000, debug=True)
