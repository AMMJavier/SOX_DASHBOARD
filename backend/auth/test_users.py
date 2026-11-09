from oracle_database import SessionLocal
from models import Usuario


db = SessionLocal()


usuarios = (
    db.query(Usuario)
    .limit(5)
    .all()
)


for u in usuarios:
    print(
        u.username,
        u.rol,
        u.auth_provider
    )


db.close()