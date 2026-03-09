from flask import Flask, request, redirect, session, send_from_directory, render_template_string
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "video-site-secret"

UPLOAD_FOLDER = "videos"
MAX_SIZE = 100 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def db():
    return sqlite3.connect("site.db")

# DB作成
conn = db()
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users(
name TEXT PRIMARY KEY,
password TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS videos(
id INTEGER PRIMARY KEY AUTOINCREMENT,
title TEXT,
desc TEXT,
tags TEXT,
filename TEXT,
user TEXT,
views INTEGER DEFAULT 0,
likes INTEGER DEFAULT 0
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS comments(
id INTEGER PRIMARY KEY AUTOINCREMENT,
video INTEGER,
user TEXT,
text TEXT
)
""")

conn.commit()
conn.close()


# トップページ
@app.route("/")
def home():

    conn = db()
    videos = conn.execute(
        "SELECT id,title,views FROM videos ORDER BY id DESC LIMIT 5"
    ).fetchall()
    conn.close()

    login_message = ""
    if "user" not in session:
        login_message = "<p>ログインしてください</p>"

    return render_template_string("""
    <h1>動画.com</h1>

    <button onclick="location.href='/videos'">すべての動画</button>
    <button onclick="location.href='/account'">アカウント</button>

    """ + login_message + """

    <h2>最新動画</h2>

    {% for v in videos %}
    <p>
    <a href="/watch/{{v[0]}}">{{v[1]}}</a>
    ({{v[2]}}再生)
    </p>
    {% endfor %}
    """, videos=videos)


# ログイン / 作成
@app.route("/login", methods=["GET","POST"])
def login():

    msg=""

    if request.method=="POST":
        name=request.form["name"]
        pw=request.form["pw"]

        conn=db()
        user=conn.execute(
        "SELECT password FROM users WHERE name=?",(name,)
        ).fetchone()

        if user:
            if check_password_hash(user[0], pw):
                session["user"]=name
                return redirect("/")
            else:
                msg="パスワードが違います"
        else:
            hashed = generate_password_hash(pw)
            conn.execute(
            "INSERT INTO users VALUES(?,?)",(name,hashed)
            )
            conn.commit()
            session["user"]=name
            return redirect("/")

        conn.close()

    return render_template_string("""
    <h1>ログイン / アカウント作成</h1>

    <form method="post">
    名前 <input name="name"><br>
    パスワード <input name="pw" type="password"><br>
    <button>送信</button>
    </form>

    {{msg}}
    """,msg=msg)


# アカウント画面
@app.route("/account",methods=["GET","POST"])
def account():

    if "user" not in session:
        return redirect("/login")

    if request.method=="POST":

        f=request.files["video"]

        if f:

            filename = secure_filename(f.filename)

            path=os.path.join(UPLOAD_FOLDER,filename)

            f.save(path)

            if os.path.getsize(path) > MAX_SIZE:
                os.remove(path)
                return "動画サイズが大きすぎます（100MBまで）"

            title=request.form["title"]
            desc=request.form["desc"]
            tags=request.form["tags"]

            conn=db()

            conn.execute(
            "INSERT INTO videos(title,desc,tags,filename,user) VALUES(?,?,?,?,?)",
            (title,desc,tags,filename,session["user"])
            )

            conn.commit()
            conn.close()

    return render_template_string("""
    <h1>アカウント: {{user}}</h1>

    <h2>動画投稿</h2>

    <form method="post" enctype="multipart/form-data">

    動画名<br>
    <input name="title"><br>

    説明<br>
    <textarea name="desc"></textarea><br>

    ハッシュタグ<br>
    <input name="tags"><br>

    動画<br>
    <input type="file" name="video"><br>

    <button>投稿</button>

    </form>
    """,user=session["user"])


# 動画一覧
@app.route("/videos")
def videos():

    sort=request.args.get("sort","new")

    query="ORDER BY id DESC"

    if sort=="old":
        query="ORDER BY id ASC"
    if sort=="views":
        query="ORDER BY views DESC"

    conn=db()
    vids=conn.execute(
        "SELECT id,title,views FROM videos "+query
    ).fetchall()
    conn.close()

    return render_template_string("""

    <h1>動画一覧</h1>

    並び替え
    <a href="?sort=new">最新</a>
    <a href="?sort=old">最古</a>
    <a href="?sort=views">再生数</a>

    <hr>

    {% for v in vids %}
    <p>
    <a href="/watch/{{v[0]}}">{{v[1]}}</a>
    ({{v[2]}}再生)
    </p>
    {% endfor %}

    """,vids=vids)


# 動画再生
@app.route("/watch/<int:id>")
def watch(id):

    conn=db()

    v=conn.execute(
        "SELECT title,desc,filename,views FROM videos WHERE id=?",(id,)
    ).fetchone()

    conn.execute(
        "UPDATE videos SET views=views+1 WHERE id=?",(id,)
    )

    comments=conn.execute(
        "SELECT user,text FROM comments WHERE video=?",(id,)
    ).fetchall()

    conn.commit()
    conn.close()

    return render_template_string("""

    <h1>{{v[0]}}</h1>

    <video width="500" controls>
    <source src="/video/{{v[2]}}">
    </video>

    <p>{{v[1]}}</p>
    <p>{{v[3]}}再生</p>

    <h2>コメント</h2>

    {% for c in comments %}
    <p><b>{{c[0]}}</b>: {{c[1]}}</p>
    {% endfor %}

    <form method="post" action="/comment/{{id}}">
    <input name="text">
    <button>投稿</button>
    </form>

    """,v=v,comments=comments,id=id)


@app.route("/comment/<int:id>",methods=["POST"])
def comment(id):

    if "user" not in session:
        return redirect("/login")

    text=request.form["text"]

    conn=db()
    conn.execute(
    "INSERT INTO comments(video,user,text) VALUES(?,?,?)",
    (id,session["user"],text)
    )
    conn.commit()
    conn.close()

    return redirect("/watch/"+str(id))


@app.route("/video/<name>")
def video(name):
    return send_from_directory("videos",name)


app.run(host="0.0.0.0", port=10000)
