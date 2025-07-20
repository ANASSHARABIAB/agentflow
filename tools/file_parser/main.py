import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello():
    return "AgentFlow file-parser is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # Use Cloud Run's PORT env variable
    app.run(host="0.0.0.0", port=port)
