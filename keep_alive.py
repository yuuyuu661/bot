import os
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route("/", methods=["GET", "HEAD"])
def home():
    return "I'm alive!", 200

def run():
    port = int(os.environ.get("PORT", 8080))  # ここが重要！
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()
