from flask import *
from model.oauth import db
from flask_session import Session
from view.home import home
from datetime import timedelta
from view.conset_form import consent_form
from view.bot import bot
from dotenv import load_dotenv
from view.admin import *
from model.celery import celery
from flask_cors import CORS
import secrets

load_dotenv()
app = Flask(__name__)
CORS(app)
secret_key = secrets.token_hex(16)
app.config["SECRET_KEY"] = secret_key

app.config["SESSION_TYPE"] = "sqlalchemy"
app.config["SESSION_SQLALCHEMY"] = db
app.config["SESSION_PERMANENT"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_NAME"] = "my_custom_session_cookie"

app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

app.config["SQLALCHEMY_DATABASE_URI"] = (
    "mysql+mysqlconnector://dbmasteruser:_UV$Gg;;0Jjg9=IN0r.$OVx[Dx-_]i#X@ls-a466f0bd2e9193f15c4425507403b1cd0f51f70c.caj2twqxym1d.us-east-1.rds.amazonaws.com/AffordableCare"
)

sample_users = [
    {"id": 1, "username": "mike", "password": "mikemoore"},
]

db.init_app(app)
login_manager.init_app(app)
Session(app)


celery.conf.update(app.config)

app.register_blueprint(home)
app.register_blueprint(admin)
app.register_blueprint(consent_form)
app.register_blueprint(bot)


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


if __name__ == "__main__":
    # with app.app_context():
    #     db.create_all()
    # for user_data in sample_users:
    #     user = Admin(**user_data)
    #     db.session.add(user)
    # db.session.commit()
    app.run(debug=True, port=8080)
