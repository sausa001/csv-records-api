"""How the database URL is built from settings."""
from sqlalchemy.engine import make_url

from app.config import Settings


def test_no_database_means_csv():
    assert Settings(database_url="", db_host="").sqlalchemy_url == ""


def test_full_url_wins():
    s = Settings(database_url="postgresql+psycopg://a:b@h:5432/d", db_host="other")
    assert s.sqlalchemy_url == "postgresql+psycopg://a:b@h:5432/d"


def test_parts_build_url_and_escape_password():
    # RDS-generated passwords can contain characters like @ : / # ?
    s = Settings(database_url="", db_host="mydb.abc.ap-south-1.rds.amazonaws.com",
                 db_user="app", db_password="p@ss:w/rd#?x", db_name="records")
    url = make_url(s.sqlalchemy_url)
    assert url.host == "mydb.abc.ap-south-1.rds.amazonaws.com"
    assert url.password == "p@ss:w/rd#?x"
    assert url.username == "app" and url.database == "records" and url.port == 5432
