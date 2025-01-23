from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
import random
import string
from datetime import datetime, timedelta
from flask_mail import Mail, Message
import threading
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Flask app and database setup
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_default_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///students.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

mail = Mail(app)
db = SQLAlchemy(app)

# Database models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    verified = db.Column(db.Boolean, default=False)
    verification_code = db.Column(db.String(6), nullable=True)
    quiz_answers = db.Column(db.PickleType, nullable=True)

class Pair(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    male_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    female_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pair_number = db.Column(db.String(10), nullable=False)
    meeting_time = db.Column(db.DateTime, nullable=False)
    meeting_place = db.Column(db.String(200), nullable=False)

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name')
    gender = data.get('gender')
    email = data.get('email')

    if not email.endswith('@learner.manipal.edu'):
        return jsonify({'error': 'Invalid email domain'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 400

    verification_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    new_user = User(name=name, gender=gender, email=email, verification_code=verification_code)
    db.session.add(new_user)
    db.session.commit()

    # Send verification email
    send_verification_email(email, verification_code)

    return jsonify({'message': 'Registration successful. Please verify your email.'}), 200

@app.route('/verify', methods=['POST'])
def verify():
    data = request.json
    email = data.get('email')
    code = data.get('code')

    user = User.query.filter_by(email=email).first()
    if not user or user.verification_code != code:
        return jsonify({'error': 'Invalid verification code'}), 400

    user.verified = True
    user.verification_code = None
    db.session.commit()

    return jsonify({'message': 'Email verified successfully'}), 200

@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():
    data = request.json
    email = data.get('email')
    answers = data.get('answers')

    user = User.query.filter_by(email=email, verified=True).first()
    if not user:
        return jsonify({'error': 'User not found or not verified'}), 400

    user.quiz_answers = answers
    db.session.commit()

    return jsonify({'message': 'Quiz submitted successfully'}), 200

# Helper functions
def send_verification_email(email, code):
    msg = Message('Verify Your Email', sender=os.getenv('MAIL_USERNAME'), recipients=[email])
    msg.body = f'Your verification code is {code}. Please enter this code to verify your email.'
    mail.send(msg)

def generate_pairs():
    males = User.query.filter_by(gender='male', verified=True).all()
    females = User.query.filter_by(gender='female', verified=True).all()

    random.shuffle(males)
    random.shuffle(females)

    pairs = []
    for male, female in zip(males, females):
        pair_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        meeting_time = datetime.now() + timedelta(days=5)
        meeting_place = 'Central Library, Room 101'

        pair = Pair(male_id=male.id, female_id=female.id, pair_number=pair_number, meeting_time=meeting_time, meeting_place=meeting_place)
        pairs.append(pair)
        db.session.add(pair)

        # Send email to both participants
        send_pair_email(male.email, female.email, pair_number, meeting_time, meeting_place)

    db.session.commit()

def send_pair_email(male_email, female_email, pair_number, meeting_time, meeting_place):
    subject = 'Your Unique Pairing Details'
    body = f'You have been paired!\n\nPair Number: {pair_number}\nMeeting Time: {meeting_time}\nMeeting Place: {meeting_place}'

    msg_male = Message(subject, sender=os.getenv('MAIL_USERNAME'), recipients=[male_email])
    msg_female = Message(subject, sender=os.getenv('MAIL_USERNAME'), recipients=[female_email])

    msg_male.body = body
    msg_female.body = body

    mail.send(msg_male)
    mail.send(msg_female)

# Countdown Timer Background Thread
def start_timer():
    countdown_time = datetime.now() + timedelta(days=5)
    while datetime.now() < countdown_time:
        remaining = countdown_time - datetime.now()
        print(f'Time left: {remaining}')  # For debugging purposes
        threading.Event().wait(60)

    generate_pairs()

if __name__ == '__main__':
    db.create_all()
    threading.Thread(target=start_timer).start()
    app.run(debug=True)
