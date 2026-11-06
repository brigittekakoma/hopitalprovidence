from app import create_app
def test_health():
    app=create_app({"TESTING":True,"SQLALCHEMY_DATABASE_URI":"sqlite:///:memory:","WTF_CSRF_ENABLED":False})
    r=app.test_client().get("/health")
    assert r.status_code==200 and r.json["status"]=="ok"
