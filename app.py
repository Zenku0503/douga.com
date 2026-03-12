from flask import Flask, request, redirect, session, render_template_string
import sqlite3
import os
import uuid
from werkzeug.security import generate_password_hash, check_password_hash

import cloudinary
import cloudinary.uploader

app = Flask(__name__)
app.secret_key = "video-site-secret"

# Cloudinary設定
cloudinary.config(
    cloud_name=os.environ.get("CLOUD_NAME"),
    api_key=os.environ.get("API_KEY"),
    api_secret=os.environ.get("API_SECRET")
)

def db():
    return sqlite3.connect("site.db")


# データベース作成
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
views INTEGER DEFAULT 0
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

    return render_template_string("""

    <h1>動画.com</h1>

    <a href="/videos">動画一覧</a>
    <a href="/account">アカウント</a>

    <h2>最新動画</h2>

    {% for v in videos %}
    <p>
    <a href="/watch/{{v[0]}}">{{v[1]}}</a>
    ({{v[2]}}再生)
    </p>
    {% endfor %}

    """, videos=videos)


# ログイン
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
                conn.close()
                return redirect("/")

            else:
                msg="パスワード違い"

        else:

            hashed=generate_password_hash(pw)

            conn.execute(
            "INSERT INTO users VALUES(?,?)",(name,hashed)
            )

            conn.commit()

            session["user"]=name
            conn.close()

            return redirect("/")

        conn.close()

    return render_template_string("""

    <h1>ログイン</h1>

    <form method="post">

    名前<br>
    <input name="name"><br>

    パスワード<br>
    <input name="pw" type="password"><br>

    <button>送信</button>

    </form>

    <p>{{msg}}</p>

    """,msg=msg)


# アカウント
@app.route("/account",methods=["GET","POST"])
def account():

    if "user" not in session:
        return redirect("/login")

    error=""

    if request.method=="POST":

        try:

            f=request.files["video"]

            filename=str(uuid.uuid4())+".mp4"
            temp_path="/tmp/"+filename

            f.save(temp_path)

            result = cloudinary.uploader.upload(
                temp_path,
                resource_type="video"
            )

            os.remove(temp_path)

            url=result["secure_url"]

            title=request.form["title"]
            desc=request.form["desc"]
            tags=request.form["tags"]

            conn=db()

            conn.execute(
            "INSERT INTO videos(title,desc,tags,filename,user) VALUES(?,?,?,?,?)",
            (title,desc,tags,url,session["user"])
            )

            conn.commit()
            conn.close()

            return redirect("/")

        except Exception as e:

            error=str(e)

    return render_template_string("""

    <h1>アカウント: {{user}}</h1>

    <h2>動画投稿</h2>

    <form method="post" enctype="multipart/form-data">

    タイトル<br>
    <input name="title"><br>

    説明<br>
    <textarea name="desc"></textarea><br>

    タグ<br>
    <input name="tags"><br>

    動画<br>
    <input type="file" name="video"><br><br>

    <button>投稿</button>

    </form>

    <p style="color:red">{{error}}</p>

    """,user=session["user"],error=error)


# 動画一覧
@app.route("/videos")
def videos():

    conn=db()

    vids=conn.execute(
        "SELECT id,title,views FROM videos ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return render_template_string("""

    <h1>動画一覧</h1>

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
        "SELECT title,desc,filename,views,user FROM videos WHERE id=?",(id,)
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

    <p>投稿者: {{v[4]}}</p>

    <video width="500" controls>
    <source src="{{v[2]}}">
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


if __name__ == "__main__":

    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
