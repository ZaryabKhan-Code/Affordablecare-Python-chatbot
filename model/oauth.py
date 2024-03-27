from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin

db = SQLAlchemy()

class UserInfo(db.Model):
    __tablename__="user_info"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    messenger_id = db.Column(db.String(255))
    email = db.Column(db.String(255))
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    zipCode = db.Column(db.String(10))
    age = db.Column(db.Integer)
    people = db.Column(db.String(255))
    income = db.Column(db.Integer)
    county = db.Column(db.String(255))
    fips = db.Column(db.String(255))
    state = db.Column(db.String(255))
    agent = db.Column(db.String(255))
    agency = db.Column(db.String(255))
    theMetal = db.Column(db.String(255))
    year = db.Column(db.Integer)
    planID = db.Column(db.String(255))
    currentState = db.Column(db.String(255))
    is_sample = db.Column(db.String(255))
    drugName = db.Column(db.String(255))
    facility_name = db.Column(db.String(255))
    issuer_name = db.Column(db.String(255))
    countyCondition = db.Column(db.Boolean)
    benefits_link = db.Column(db.Text)

class ChatbotMemory(db.Model):
    __tablename__ = 'chatbot_memory'
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.String(36))
    workflow = db.Column(db.String(255))
    speaker = db.Column(db.String(10))
    content = db.Column(db.Text)

    
class Agent_Header(db.Model):
    __tablename__='agent_header'
    id = db.Column(db.Integer, primary_key=True)
    header = db.Column(db.Text, nullable=False)
    agent_id = db.Column(db.Integer)

class PDF(db.Model):
    __tablename__ = 'PDF'
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.JSON, nullable=False)
    date = db.Column(db.String(200))
    content = db.Column(db.LargeBinary)
    consenttype = db.Column(db.String(200))
    primaryholderemail = db.Column(db.String(300))
    UUID = db.Column(db.String(200))
    extension = db.Column(db.String(10))



class Admin(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)


