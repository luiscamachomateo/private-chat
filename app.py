from flask import Flask, render_template, request, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os, secrets

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = secrets.token_hex(16)

db = SQLAlchemy(app)

class Topic(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    slug      = db.Column(db.String(16), unique=True, nullable=False)
    name      = db.Column(db.String(120), nullable=False)
    created   = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    topic_id  = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    sender    = db.Column(db.String(30), nullable=False)      # “Me” / “Them”
    body      = db.Column(db.Text, nullable=False)
    created   = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        name  = request.form['topic'].strip()
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
        sender = request.form['sender'].strip() or "Anonymous"
        body   = request.form['body'].strip()
        if body:
            db.session.add(Message(topic_id=topic.id, sender=sender, body=body))
            db.session.commit()
            return redirect(url_for('topic', slug=slug))
    msgs = Message.query.filter_by(topic_id=topic.id).order_by(Message.created).all()
    return render_template('topic.html', topic=topic, msgs=msgs)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

