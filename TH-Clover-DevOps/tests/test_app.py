import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
from app.main import app

def test_health():
    response = app.test_client().get('/health')
    assert response.status_code == 200
    assert response.json['status'] == 'ok'

def test_ticket_validation():
    assert app.test_client().post('/tickets', json={}).status_code == 400

def test_ticket_lifecycle():
    client = app.test_client()
    assert client.post('/tickets', json={'subject':'Demo support request'}).status_code == 201
    assert any(t['subject'] == 'Demo support request' for t in client.get('/tickets').json)

def test_metrics():
    assert b'clover_http_requests_total' in app.test_client().get('/metrics').data
