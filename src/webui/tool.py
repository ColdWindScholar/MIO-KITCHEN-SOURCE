#main.py

from flask import Flask
from flask import render_template

app = Flask(__name__)


@app.route("/")
def hello():
    return render_template('index.html', text="hello, here!")

@app.route("/home", methods=['GET'])
def home():
    return render_template('some_page.html')


if __name__ == "__main__":
    app.run()
  # If you are debugging you can do that in the browser:app.run()
  # If you want to view the flaskwebgui window:
