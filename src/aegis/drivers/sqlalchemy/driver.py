"""
Driver SQLAlchemy & Persistance PostgreSQL 16 pour Aegis.

Implémente le port SubjectRepository avec persistance relationnelle sur PostgreSQL/SQLite
et gestion des migrations de schéma.
"""

from typing import Any, Optional

from aegis.core.application.ports import SubjectRepository
from aegis.core.domain.entities import HumanIdentity, Subject
from aegis.core.domain.values import EmailAddress, SubjectId

try:
    from sqlalchemy import Boolean, Column, DateTime, String, create_engine
    from sqlalchemy.orm import declarative_base, sessionmaker

    SQLALCHEMY_AVAILABLE = True
    Base = declarative_base()

    class SubjectORM(Base):  # type: ignore
        """Modèle ORM relationnel pour la table `aegis_subjects`."""

        __tablename__ = "aegis_subjects"

        id = Column(String(64), primary_key=True, index=True)
        tenant_id = Column(String(64), nullable=True, index=True)
        subject_type = Column(String(32), nullable=False)
        email = Column(String(255), nullable=True, unique=True, index=True)
        first_name = Column(String(128), default="")
        last_name = Column(String(128), default="")
        is_active = Column(Boolean, default=True)
        created_at = Column(DateTime(timezone=True), nullable=False)
        updated_at = Column(DateTime(timezone=True), nullable=False)

except ImportError:
    SQLALCHEMY_AVAILABLE = False
    Base = None


class SQLAlchemySubjectRepository(SubjectRepository):
    """Implémentation du SubjectRepository via SQLAlchemy ORM."""

    def __init__(self, db_url: str = "sqlite:///./aegis.db") -> None:
        if not SQLALCHEMY_AVAILABLE:
            raise RuntimeError("SQLAlchemy n'est pas installé sur cet environnement.")
        self.engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def get_by_id(self, subject_id: SubjectId) -> Optional[Subject]:
        session = self.SessionLocal()
        try:
            orm_obj = session.query(SubjectORM).filter(SubjectORM.id == subject_id.value).first()
            if not orm_obj:
                return None
            return self._to_domain(orm_obj)
        finally:
            session.close()

    def get_by_email(self, email: EmailAddress) -> Optional[HumanIdentity]:
        session = self.SessionLocal()
        try:
            orm_obj = session.query(SubjectORM).filter(SubjectORM.email == email.value).first()
            if not orm_obj:
                return None
            domain_obj = self._to_domain(orm_obj)
            if isinstance(domain_obj, HumanIdentity):
                return domain_obj
            return None
        finally:
            session.close()

    def save(self, subject: Subject) -> None:
        session = self.SessionLocal()
        try:
            orm_obj = session.query(SubjectORM).filter(SubjectORM.id == subject.id.value).first()
            email_str = None
            first_name = ""
            last_name = ""

            if isinstance(subject, HumanIdentity):
                email_str = subject.email.value if subject.email else None
                first_name = subject.first_name
                last_name = subject.last_name

            if not orm_obj:
                orm_obj = SubjectORM(
                    id=subject.id.value,
                    tenant_id=subject.tenant_id.value if subject.tenant_id else None,
                    subject_type=subject.subject_type,
                    email=email_str,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=subject.is_active,
                    created_at=subject.created_at,
                    updated_at=subject.updated_at,
                )
                session.add(orm_obj)
            else:
                orm_obj.is_active = subject.is_active
                orm_obj.updated_at = subject.updated_at
                orm_obj.email = email_str

            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete(self, subject_id: SubjectId) -> bool:
        session = self.SessionLocal()
        try:
            orm_obj = session.query(SubjectORM).filter(SubjectORM.id == subject_id.value).first()
            if orm_obj:
                session.delete(orm_obj)
                session.commit()
                return True
            return False
        finally:
            session.close()

    def _to_domain(self, orm: Any) -> Subject:
        if orm.subject_type == "HUMAN":
            email = EmailAddress(orm.email) if orm.email else None
            return HumanIdentity(
                id=SubjectId(orm.id),
                tenant_id=orm.tenant_id,
                is_active=orm.is_active,
                email=email,
                first_name=orm.first_name,
                last_name=orm.last_name,
            )
        raise ValueError(f"Subject type inconnu: {orm.subject_type}")
