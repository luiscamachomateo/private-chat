import os
import secrets
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort, session
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
app.secret_key = secrets.token_hex(16)

db = SQLAlchemy(app)
socketio = SocketIO(app, async_mode='eventlet')

PASSWORD = "letmein"  # set your password

class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(16), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    created = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    sender = db.Column(db.String(30), nullable=False)
    body = db.Column(db.Text, nullable=False)
    filename = db.Column(db.String(255))
    created = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    if request.method == 'POST':
        name = request.form['topic'].strip()
        if name:
            slug = secrets.token_urlsafe(8)
            db.session.add(Topic(slug=slug, name=name))
            db.session.commit()
            return redirect(url_for('topic', slug=slug))
    topics = Topic.query.order_by(Topic.created.desc()).all()
    return render_template('index.html', topics=topics)

@app.route('/t/<slug>')
def topic(slug):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    topic = Topic.query.filter_by(slug=slug).first_or_404()
    msgs = Message.query.filter_by(topic_id=topic.id).order_by(Message.created).all()
    return render_template('topic.html', topic=topic, msgs=msgs)

@socketio.on('join')
def handle_join(data):
    join_room(data['room'])

@socketio.on('send_message')
def handle_send_message(data):
    topic_id = data['topic_id']
    sender = data['sender'].strip() or "Anonymous"
    body = data['body'].strip()
    if body:
        msg = Message(topic_id=topic_id, sender=sender, body=body)
        db.session.add(msg)
        db.session.commit()
        emit('new_message', {
            'sender': sender,
            'body': body,
            'time': msg.created.strftime('%H:%M %Y-%m-%d')
        }, room=data['room'])

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
