"""Start the Dhwani web app:  python run.py   then open http://127.0.0.1:5000"""
from __future__ import annotations

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
