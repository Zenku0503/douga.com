from flask import Flask, request, redirect, session, render_template_string
import sqlite3
import os
import uuid
from werkzeug.security import generate_password_hash, check_password_hash

import cloudinary
import cloudinary.uploader

app = Flask(__name__)
app.secret_key = "video-site-secret"

ADMIN="全国空想電鉄"

cloudinary.config(
    cloud_name=os.environ.get("CLOUD_NAME"),
    api_key=os.environ.get("API_KEY"),
    api_secret=os.environ.get("API_SECRET")
)

# Railway用DB
def db():
    return sqlite3.connect("site.db", check_same_thread=False)


conn=db()
c=conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users(
name TEXT PRIMARY KEY,
password TEXT,
deleted INTEGER DEFAULT 0
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


@app.route("/")
def home():

    conn=db()
    videos=conn.execute(
    "SELECT id,title,views FROM videos ORDER BY id DESC LIMIT 5"
    ).fetchall()
    conn.close()

    msg=""
    if "user" not in session:
        msg="<p>ログインしてください</p>"

    return render_template_string("""

    <h1>動画.com</h1>

    """+msg+"""

    <a href="/videos">動画一覧</a>
    <a href="/account">アカウント</a>

    <h2>最新動画</h2>

    {% for v in videos %}
    <p>
    <a href="/watch/{{v[0]}}">{{v[1]}}</a>
    ({{v[2]}}再生)
    </p>
    {% endfor %}

    """,videos=videos)


@app.route("/login",methods=["GET","POST"])
def login():

    msg=""

    if request.method=="POST":

        name=request.form["name"]
        pw=request.form["pw"]

        conn=db()

        user=conn.execute(
        "SELECT password,deleted FROM users WHERE name=?",(name,)
        ).fetchone()

        if not user:
            msg="アカウントが存在しません"

        elif user[1]==1:
            msg="このアカウントは削除されています"

        else:
            if check_password_hash(user[0],pw):
                session["user"]=name
                conn.close()
                return redirect("/")
            else:
                msg="パスワード違い"

        conn.close()

    return render_template_string("""

    <h1>ログイン</h1>

    <form method="post">
    名前<br>
    <input name="name"><br>
    パスワード<br>
    <input name="pw" type="password"><br>
    <button>ログイン</button>
    </form>

    <p>{{msg}}</p>

    <hr>

    <button onclick="location.href='/register'">
    アカウント作成
    </button>

    """,msg=msg)


@app.route("/register",methods=["GET","POST"])
def register():

    msg=""

    if request.method=="POST":

        name=request.form["name"]
        pw=request.form["pw"]

        conn=db()

        user=conn.execute(
        "SELECT name FROM users WHERE name=?",(name,)
        ).fetchone()

        if user:
            msg="既にそのアカウントはあります"

        else:

            hashed=generate_password_hash(pw)

            conn.execute(
            "INSERT INTO users(name,password) VALUES(?,?)",
            (name,hashed)
            )

            conn.commit()
            conn.close()

            return redirect("/login")

        conn.close()

    return render_template_string("""

    <h1>アカウント作成</h1>

    <form method="post">
    名前<br>
    <input name="name"><br>
    パスワード<br>
    <input name="pw" type="password"><br>
    <button>作成</button>
    </form>

    <p>{{msg}}</p>

    """,msg=msg)


@app.route("/account",methods=["GET","POST"])
def account():

    if "user" not in session:
        return redirect("/login")

    msg=""

    if request.method=="POST":

        if "video" in request.files:

            f=request.files["video"]

            filename=str(uuid.uuid4())+".mp4"
            temp="/tmp/"+filename
            f.save(temp)

            result=cloudinary.uploader.upload(
            temp,
            resource_type="video"
            )

            os.remove(temp)

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

            msg="投稿しました"

        if "newpw" in request.form:

            new=request.form["newpw"]

            conn=db()

            conn.execute(
            "UPDATE users SET password=? WHERE name=?",
            (generate_password_hash(new),session["user"])
            )

            conn.commit()
            conn.close()

            msg="パスワード変更しました"

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
    <input type="file" name="video"><br>
    <button>投稿</button>
    </form>

    <h2>パスワード変更</h2>

    <form method="post">
    新しいパスワード<br>
    <input name="newpw" type="password"><br>
    <button>変更</button>
    </form>

    <h2>ログアウト</h2>

    <a href="/logout">ログアウト</a>

    <h2>アカウント削除</h2>

    <a href="/delete_account">削除</a>

    <p>{{msg}}</p>

    """,user=session["user"],msg=msg)


@app.route("/logout")
def logout():

    session.clear()
    return redirect("/")


@app.route("/delete_account")
def delete_account():

    if "user" not in session:
        return redirect("/")

    conn=db()

    conn.execute(
    "UPDATE users SET deleted=1 WHERE name=?",(session["user"],)
    )

    conn.commit()
    conn.close()

    session.clear()

    return redirect("/")


@app.route("/videos")
def videos():

    sort=request.args.get("sort","new")

    order="id DESC"

    if sort=="old":
        order="id ASC"

    if sort=="views":
        order="views DESC"

    conn=db()

    vids=conn.execute(
    "SELECT id,title,views FROM videos ORDER BY "+order
    ).fetchall()

    conn.close()

    return render_template_string("""

    <h1>動画一覧</h1>

    並び替え:
    <a href="/videos?sort=new">最新</a>
    <a href="/videos?sort=old">古い</a>
    <a href="/videos?sort=views">再生数</a>

    <hr>

    {% for v in vids %}
    <p>
    <a href="/watch/{{v[0]}}">{{v[1]}}</a>
    ({{v[2]}}再生)
    </p>
    {% endfor %}

    """,vids=vids)


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
    "SELECT id,user,text FROM comments WHERE video=?",(id,)
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
    <p>
    <b>{{c[1]}}</b>: {{c[2]}}
    </p>
    {% endfor %}

    """,v=v,comments=comments,id=id)


if __name__=="__main__":

    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
