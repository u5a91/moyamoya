import os
from dotenv import load_dotenv

import bleach
import calendar 
from datetime import datetime, date, timedelta, timezone
from markdown import markdown
from sqlalchemy.sql import func

from flask import Flask, render_template, redirect, url_for, request, flash, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    logout_user, login_required, current_user
)
from flask_migrate import Migrate

from werkzeug.security import generate_password_hash, check_password_hash

from zoneinfo import ZoneInfo
JST = ZoneInfo("Asia/Tokyo")

# UTC の現在時刻を返す
def utcnow():
    return datetime.now(timezone.utc)

def to_utc(dt: datetime) -> datetime:
    """
    DB からもってきた datetime を zonetime-aware な UTC とする
    なお SQLite なのでデフォは UTC 想定とする
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def to_jst(dt: datetime) -> datetime:
    """
    DB からもってきた datetime を zonetime-aware な JST とする
    """
    dt_utc = to_utc(dt)
    return dt_utc.astimezone(JST) if dt_utc else None

# サニタイジング
# <img> などはまだ許可していないことに注意

ALLOWED_TAGS = bleach.sanitizer.ALLOWED_TAGS.union({
    "p","br","pre","code","blockquote",
    "ul","ol","li",
    "strong","em","del",
    "h1","h2","h3","h4",
    "table","thead","tbody","tr","th","td","a",
    "div", "span"
})
ALLOWED_ATTRS = {
    "a": ["href", "title", "rel"],
    "code": ["class"],
    "span": ["class"],
    "pre": ["class"],
    "div": ["class"]
}
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

def sanitize_html(html: str) -> str:
    cleaned = bleach.clean(
        html,
        tags=list(ALLOWED_TAGS),
        attributes=ALLOWED_ATTRS,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
    cleaned = bleach.linkify(cleaned)
    return cleaned

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False # 省エネ

db = SQLAlchemy(app)
migrate = Migrate()
migrate.init_app(app, db)
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

    # datetime を timezone-aware にして, 関数 utcnow によりデフォルトは UTC を指定
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow
    )

    # User テーブルとの紐づけ
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/")
@login_required
def index():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)

    if not year or not month:
        today = datetime.now(JST).date()
        year, month = today.year, today.month

    cal = calendar.Calendar(firstweekday=6) # 6: Sunday
    weeks = cal.monthdatescalendar(year, month)

    # JST で月の範囲指定
    start_jst = datetime(year, month, 1, 0, 0, tzinfo=JST)
    if month == 12:
        end_jst = datetime(year + 1, 1, 1, 0, 0, tzinfo=JST)
    else:
        end_jst = datetime(year, month + 1, 1, 0, 0, tzinfo=JST)

    # UTC で
    start_dt = start_jst.astimezone(timezone.utc)
    end_dt   = end_jst.astimezone(timezone.utc)

    month_entries = (
        Entry.query.filter(
            Entry.user_id == current_user.id,
            Entry.created_at >= start_dt,
            Entry.created_at < end_dt
        )
        .all()
    )

    # 日付でまとめる
    entries_by_date: dict[date, list[Entry]] = {}
    for e in month_entries:
        # 保存されている datetime.datetime 型を datetime.date 型へ変換
        d = to_jst(e.created_at).date()
        entries_by_date.setdefault(d, []).append(e)

    return render_template(
        "index.html",
        year=year,
        month=month,
        weeks=weeks,
        entries_by_date=entries_by_date
    )

# ログイン

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

# 登録

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

# 日のエントリ一覧

@app.route("/day/<date_str>")
@login_required
def day_view(date_str: str):
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        abort(404)

    start_jst = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=JST)
    end_jst = start_jst + timedelta(days=1)

    start_dt = start_jst.astimezone(timezone.utc)
    end_dt = end_jst.astimezone(timezone.utc)

    day_entries = (
        Entry.query.filter(
            Entry.user_id == current_user.id,
            Entry.created_at >= start_dt,
            Entry.created_at < end_dt
        )
        .order_by(Entry.created_at.asc())
        .all()
    )

    return render_template(
        "day_view.html",
        target_date=target_date,
        day_entries=day_entries,
    )

# エントリ

@app.route("/day/<date_str>/entry/<int:entry_id>/")
@login_required
def entry_view(date_str: str, entry_id: int):
    try: 
        target_date = date.fromisoformat(date_str)
    except ValueError:
        abort(404)
    
    entry = Entry.query.get_or_404(entry_id)

    if entry.user_id != current_user.id:
        abort(403)

    # 標準時の指定 tzinfo は昔のデータだと存在しないかも
    if entry.created_at.tzinfo is None:
        entry.created_at = entry.created_at.replace(tzinfo=timezone.utc)
    if entry.updated_at and entry.updated_at.tzinfo is None:
        entry.updated_at = entry.updated_at.replace(tzinfo=timezone.utc)

    created_jst = to_jst(entry.created_at)
    updated_jst = to_jst(entry.updated_at) if entry.updated_at else None

    correct_date_str = created_jst.date().isoformat()
    if correct_date_str != date_str:
        return redirect(url_for("entry_view", date_str=correct_date_str, entry_id=entry.id))

    raw_html = markdown(
        entry.body,
        extensions = [
            "fenced_code",
            "tables",
            "sane_lists",
            "pymdownx.superfences",
            "pymdownx.highlight",
            "pymdownx.tilde",
            "pymdownx.tasklist"
        ], 
        # コードブロックまわり
        extension_configs={
            "pymdownx.highlight": {
                "use_pygments": True,
                "noclasses": False,
                "css_class": "highlight",
                "linenums": True
            }
        }
    )
    body_html = sanitize_html(raw_html)

    entry.created_at = created_jst
    entry.updated_at = updated_jst

    return render_template(
        "entry_view.html",
        target_date=target_date,
        entry=entry,
        body_html=body_html
    )

@app.route("/day/<date_str>/entry/<int:entry_id>/edit", methods=["GET", "POST"])
@login_required
def edit_entry(date_str: str, entry_id: int):
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        abort(404)

    entry = Entry.query.get_or_404(entry_id)

    if entry.user_id != current_user.id:
        abort(403)

    if entry.created_at.tzinfo is None:
        entry.created_at = entry.created_at.replace(tzinfo=timezone.utc)

    created_jst = to_jst(entry.created_at)
    if created_jst.date() != target_date:
        abort(404)
    
    if request.method == "POST":
        entry.title = request.form["title"]
        entry.body = request.form["body"]
        db.session.commit()

        # コミット後, 日付取得
        return redirect(url_for("entry_view", date_str=created_jst.date().isoformat(), entry_id=entry.id))

    return render_template(
        "edit_entry.html",
        target_date=target_date,
        entry=entry,
    )

# Markdown のプレビュー
@app.route("/markdown_preview", methods=["POST"])
@login_required
def markdown_preview():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "") or ""

    raw_html = markdown(
        text,
        extensions = [
            "fenced_code",
            "tables",
            "sane_lists",
            "pymdownx.superfences",
            "pymdownx.highlight",
            "pymdownx.tilde",
            "pymdownx.tasklist"
        ]
    )
    html = sanitize_html(raw_html)

    return jsonify({"html": html})

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

        # コミット後, 日付取得
        date_str = entry.created_at.astimezone(JST).date().isoformat()
        return redirect(url_for("entry_view", date_str=date_str, entry_id=entry.id))
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
    # 重要: 以下は初期化のため, はじめの 1 回のみ行う (以降はコメントアウト)
    # with app.app_context():
    #    db.create_all()
    app.run(debug=True)