import os
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = "secret-key-change-this"

# ---------------------------
# HOME PAGE
# ---------------------------
@app.route("/")
def home():
    return render_template("index.html")

# ---------------------------
# LOGIN PAGE
# ---------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # simple dummy check
        if username == "admin" and password == "1234":
            session["user"] = username
            return redirect(url_for("home"))
        else:
            flash("Invalid credentials")

    return render_template("login.html")

# ---------------------------
# REGISTER PAGE
# ---------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        flash("Registered successfully (dummy)")
        return redirect(url_for("login"))

    return render_template("register.html")

# ---------------------------
# LOGOUT
# ---------------------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))

# ---------------------------
# RUN SERVER (RAILWAY FIX)
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



   
