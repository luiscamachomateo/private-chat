import os
import secrets
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")  # PostgreSQL
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
app.secret_key = secrets.token_hex(16)

db = SQLAlchemy(app)

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
    reactions = db.Column(db.Text, default="{}")
    created = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.drop_all()       # only for now to reset broken schema
    db.create_all()

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        name = request.form['topic'].strip()
        if name:
            slug = secrets.token_urlsafe(8)
            db.session.add(Topic(slug=slug, name=name))
            db.session.commit()
            return redirect(url_for('topic', slug=slug))
    topics = Topic.query.order_by(Topic.created.desc()).all()
    return render_template('index.html', topics=topics)

@app.route('/t/<slug>', methods=['GET', 'POST'])
def topic(slug):
    topic = Topic.query.filter_by(slug=slug).first()
    if not topic:
        abort(404)
    if request.method == 'POST':
        sender = request.form.get('sender', 'Anonymous').strip()
        body = request.form.get('body', '').strip()
        file = request.files.get('file')
        filename = None

        if file and allowed_file(file.filename):
            filename = secrets.token_hex(8) + '_' + secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        if body or filename:
            db.session.add(Message(topic_id=topic.id, sender=sender, body=body or '', filename=filename))
            db.session.commit()
            return redirect(url_for('topic', slug=slug))

    msgs = Message.query.filter_by(topic_id=topic.id).order_by(Message.created).all()
    return render_template('topic.html', topic=topic, msgs=msgs)

@app.route('/react/<int:msg_id>/<emoji>', methods=["POST"])
def react(msg_id, emoji):
    msg = Message.query.get_or_404(msg_id)
    current = json.loads(msg.reactions or "{}")
    current[emoji] = current.get(emoji, 0) + 1
    msg.reactions = json.dumps(current)
    db.session.commit()
    return redirect(request.referrer or url_for('index'))

@app.route('/delete/message/<int:id>')
def delete_message(id):
    msg = Message.query.get_or_404(id)
    if msg.filename:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], msg.filename))
        except:
            pass
    db.session.delete(msg)
    db.session.commit()
    return redirect(request.referrer)

@app.route('/delete/topic/<slug>')
def delete_topic(slug):
    topic = Topic.query.filter_by(slug=slug).first_or_404()
    messages = Message.query.filter_by(topic_id=topic.id).all()
    for msg in messages:
        if msg.filename:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], msg.filename))
            except:
                pass
        db.session.delete(msg)
    db.session.delete(topic)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
