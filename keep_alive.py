from flask import Flask
from threading import Thread
import os

app = Flask(__name__)

@app.route("/", methods=["GET", "HEAD"])
def home():
    return "I'm alive!", 200

def run():
    port = int(os.environ.get("PORT", 8080))  # ← 必ずPORT環境変数を使う
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
    
def keep_alive():
    t = Thread(target=run)
    t.start()
