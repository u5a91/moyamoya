import os
from dotenv import load_dotenv

from datetime import datetime, timezone

from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False # 省エネ

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login" # ログインしていないときのリダイレクト先

class User(UserMixin, db.Model):
    # UserMixin で Flask-Login に必要な属性を読み込み
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    # User モデルは複数 Entry を持つよ. 逆方向参照. 
    # lazy で使うときに読み込むようにするよ
    entries = db.relationship("Entry", backref="author", lazy=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
    
class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    # User テーブルとの紐づけ
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/")
@login_required
def index():
    entries = Entry.query.filter_by(user_id=current_user.id).order_by(Entry.created_at.desc()).all() 
    # ??
    return render_template("index.html", entries=entries)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("index"))
        flash("ユーザ名またはパスワードが違います. ")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if User.query.filter_by(username=username).first():
            flash("そのユーザ名はすでに使われています. ")
            return redirect(url_for("register"))

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("登録完了しました. ログインしてください. ")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/new", methods=["GET", "POST"])
@login_required
def new_entry():
    if request.method == "POST":
        title = request.form["title"]
        body = request.form["body"]
        entry = Entry(title=title, body=body, author=current_user)
        db.session.add(entry)
        db.session.commit()
        return redirect(url_for("index"))
    return render_template("new_entry.html")

# DELETE. form は GET / POST しかサポートしないので POST で代用
@app.route("/delete/<int:entry_id>", methods=["POST"])
@login_required
def delete_entry(entry_id):
    # None ならば 404
    entry = Entry.query.get_or_404(entry_id)
    
    if entry.user_id != current_user.id:
        abort(403)

    db.session.delete(entry)
    db.session.commit()
    flash("削除が完了しました. ")
    return redirect(url_for("index"))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)