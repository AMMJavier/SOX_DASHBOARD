from sqlalchemy import Column, Integer, String, Date, TIMESTAMP
from oracle_database import Base


class Validation(Base):
    __tablename__ = "validations"

    id = Column(Integer, primary_key=True, index=True)
    #vpn = Column(String(150), nullable=False)
    req = Column(String(50), nullable=True)
    #solicitante = Column(String(50), nullable=True)
    manager = Column(String(150), nullable=False)
    department = Column(String(150), nullable=True)
    status = Column(String(50), default="Pendiente")
    decision = Column(String(50), nullable=True)
    observation = Column(String(255), nullable=True)
    deadline = Column(Date, nullable=True)
    campaign_id = Column(Integer, nullable=True)


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    period = Column(String(100))
    status = Column(String(20), default="ACTIVA")

class Usuario(Base):

    __tablename__ = "USUARIOS"

    __table_args__ = {
        "schema": "AUTOM"
    }

    id = Column(Integer, primary_key=True)
    username = Column(String(100))
    password_hash = Column(String(255))
    auth_provider = Column(String(10))
    rol = Column(String(20))  # (SOX: 'administrador', 'genrencial') / (ASSETS: 'assets_admin', 'assets_viewer') 
    activo = Column(Integer)
    creado_en = Column(TIMESTAMP)
    actualizado_en = Column(TIMESTAMP)

class SoxGerenteContacto(Base):
    __tablename__ = "SOX_GERENTES_CONTACTO"
    __table_args__ = {"schema": "AUTOM"}

    id = Column(Integer, primary_key=True)

    nombre_completo = Column(
        String(150),
        nullable=False
    )

    correo = Column(
        String(150),
        nullable=False
    )

    ldap_cn = Column(
        String(150),
        nullable=True
    )

    activo = Column(
        Integer,
        default=1
    )

    fecha_sync = Column(
        TIMESTAMP
    )

    fecha_actualizacion = Column(
        TIMESTAMP
    )

class SoxSesion(Base):
    __tablename__ = "SOX_SESIONES"
    __table_args__ = {"schema": "AUTOM"}

    session_id = Column(String(64), primary_key=True)
    usuario_id = Column(Integer, nullable=False)
    creado_en = Column(TIMESTAMP, nullable=False)
    ultima_actividad = Column(TIMESTAMP, nullable=False)
    expira_en = Column(TIMESTAMP, nullable=False)
    revocado = Column(Integer, nullable=False, default=0)