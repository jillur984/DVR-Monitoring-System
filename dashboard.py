import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)

from src.dashboard import app

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
