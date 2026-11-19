import os
from flask import Flask, jsonify, request
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
app = Flask(__name__)
requests_total = Counter('clover_http_requests_total', 'HTTP requests', ['endpoint'])
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./clover.db')
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

def init_db():
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY, subject VARCHAR(200) NOT NULL, status VARCHAR(30) NOT NULL)'))

@app.get('/health')
def health():
    requests_total.labels('health').inc()
    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        return jsonify(status='ok', version=os.getenv('RELEASE_SHA', 'local')), 200
    except SQLAlchemyError:
        return jsonify(status='unhealthy'), 503

@app.get('/tickets')
def tickets():
    requests_total.labels('tickets').inc()
    with engine.connect() as conn:
        rows = conn.execute(text('SELECT id, subject, status FROM tickets ORDER BY id')).mappings().all()
    return jsonify([dict(row) for row in rows])

@app.post('/tickets')
def create_ticket():
    requests_total.labels('create_ticket').inc()
    data = request.get_json(silent=True) or {}
    subject = data.get('subject')
    if not isinstance(subject, str) or not 1 <= len(subject.strip()) <= 200:
        return jsonify(error='subject must contain 1-200 characters'), 400
    with engine.begin() as conn:
        conn.execute(text('INSERT INTO tickets (subject, status) VALUES (:subject, :status)'), {'subject':subject.strip(), 'status':'open'})
    return jsonify(status='created'), 201

@app.get('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

init_db()
