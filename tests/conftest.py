import os, tempfile
from pathlib import Path
# Tests intentionally use a separate SQL database from regular application data.
TEST_DB=Path(tempfile.gettempdir()) / 'scenegraph_tests_v2.sqlite3'
if TEST_DB.exists(): TEST_DB.unlink()
os.environ['DATABASE_URL']='sqlite:///'+str(TEST_DB)
from models import create_tables, Base, engine
create_tables()
import pytest
from fastapi.testclient import TestClient
from app import app

@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    create_tables()
    with TestClient(app) as tc:yield tc

@pytest.fixture
def alice(client):
    res=client.post('/api/auth/register',json={'display_name':'Alice Camera','email':'alice@example.test','password':'MyStrongPass2026!'})
    assert res.status_code==200,res.text
    return {'Authorization':'Bearer '+res.json()['token']}

@pytest.fixture
def bob(client):
    res=client.post('/api/auth/register',json={'display_name':'Bob Camera','email':'bob@example.test','password':'AnotherSecret2026!'})
    assert res.status_code==200,res.text
    return {'Authorization':'Bearer '+res.json()['token']}
