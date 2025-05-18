import os
import secrets
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort, session
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room
import cloudinary
import cloudinary.uploader

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.secret_key = secrets.token_hex(16)

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

PASSWORD = "letmein"
db = SQLAlchemy(app)
socketio = SocketIO(app, async_mode='eventlet')

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
    image_url = db.Column(db.String(500))
    created = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

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

@app.route('/delete/message/<int:id>')
def delete_message(id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    msg = Message.query.get_or_404(id)
    db.session.delete(msg)
    db.session.commit()
    return redirect(request.referrer)

@app.route('/delete/topic/<slug>')
def delete_topic(slug):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    topic = Topic.query.filter_by(slug=slug).first_or_404()
    messages = Message.query.filter_by(topic_id=topic.id).all()
    for msg in messages:
        db.session.delete(msg)
    db.session.delete(topic)
    db.session.commit()
    return redirect(url_for('index'))

@socketio.on('join')
def handle_join(data):
    join_room(data['room'])

@socketio.on('send_message')
def handle_send_message(data):
    topic_id = data['topic_id']
    sender = data['sender'].strip() or "Anonymous"
    body = data.get('body', '').strip()
    image_url = data.get('image_url')

    msg = Message(topic_id=topic_id, sender=sender, body=body, image_url=image_url)
    db.session.add(msg)
    db.session.commit()

    emit('new_message', {
        'id': msg.id,
        'sender': sender,
        'body': body,
        'image_url': image_url,
        'time': msg.created.strftime('%H:%M %Y-%m-%d')
    }, room=data['room'])

@socketio.on('delete_message')
def handle_delete_message(data):
    msg = Message.query.get(data['id'])
    if msg:
        db.session.delete(msg)
        db.session.commit()
        emit('remove_message', {'id': msg.id}, room=data['room'])

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if not session.get("logged_in"):
        return "Unauthorized", 401

    file = request.files['file']
    if file:
        upload_result = cloudinary.uploader.upload(file)
        return {'url': upload_result['secure_url']}, 200
    return {'error': 'Upload failed'}, 400

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
