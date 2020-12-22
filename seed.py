from app import app
from models import db, User

from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()


db.drop_all()
db.create_all()


hashed = bcrypt.generate_password_hash("testing").decode('utf8')

user = User(username="test",
            password=hashed,
            email="davidlee980804@gmail.com",
            first_name="David",
            last_name="Lee",
            is_admin=True)

db.session.add(user)
db.session.commit()
