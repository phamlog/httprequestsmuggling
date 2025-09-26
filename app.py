import os
from flask import Flask, request, render_template, redirect, abort

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app = Flask(__name__, template_folder=TEMPLATES_DIR)

USERS = {"alice": "alice", "admin": "12345"}

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("index.html")
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    app.logger.info("login attempt: %s", username)
    if USERS.get(username) == password:
        if username == "admin":
            return redirect("/admin")
        return render_template("ok.html", who=username)
    return "Invalid credentials", 401

@app.route("/admin", methods=["GET"])
def admin():
    if request.headers.get("X-Internal-Admin") == "1":
        return "<h1>ADMIN AREA</h1><p>Secret flag: FLAG{this_is_a_flag_for_research}</p>"
    return abort(403)

if __name__ == "__main__":
    print("Starting backend on 127.0.0.1:9000; templates dir:", TEMPLATES_DIR)
    # debug=False để không restart trong background; set True nếu muốn auto-reload
    app.run(host="127.0.0.1", port=9000, debug=False)
