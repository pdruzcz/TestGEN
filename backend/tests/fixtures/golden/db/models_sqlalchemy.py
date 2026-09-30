"""Golden SQLAlchemy ORM models — Story 1.53 (FR70).

Referencyjny model declarative SQLAlchemy używany do walidacji ekstraktora ORM
(§Test 2/13). Odpowiada tabelom ze schema.sql (auto-detekcja warstwy danych).
"""

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    code = Column(String(32), nullable=False, unique=True)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True)
    age = Column(Integer, nullable=False)
    role = Column(String(32), nullable=False)
    org_id = Column(Integer, ForeignKey("organizations.id"))
