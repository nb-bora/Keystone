"""
Driver SQLAlchemy & Persistance PostgreSQL 16 pour Aegis.

Implémente le port SubjectRepository avec persistance relationnelle sur PostgreSQL/SQLite
et gestion des migrations de schéma en utilisant l'Anti-Corruption Layer (ACL).
"""

from typing import Any, Optional

from aegis.core.application.acl import MapperFactory, SubjectDataMapper, UnitOfWork
from aegis.core.application.ports import SubjectRepository
from aegis.core.domain.entities import HumanIdentity, Subject
from aegis.core.domain.values import EmailAddress, SubjectId

try:
    from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, create_engine
    from sqlalchemy.orm import declarative_base, sessionmaker

    SQLALCHEMY_AVAILABLE = True
    Base = declarative_base()

    class SubjectORM(Base):  # type: ignore
        """Modèle ORM relationnel pour la table `aegis_subjects`."""

        __tablename__ = "aegis_subjects"

        # Champs communs à tous les sujets
        id = Column(String(64), primary_key=True, index=True)
        tenant_id = Column(String(64), nullable=True, index=True)
        subject_type = Column(String(32), nullable=False, index=True)
        is_active = Column(Boolean, default=True, index=True)
        created_at = Column(DateTime(timezone=True), nullable=False)
        updated_at = Column(DateTime(timezone=True), nullable=False)

        # Champs spécifiques à HumanIdentity
        email = Column(String(255), nullable=True, unique=True, index=True)
        first_name = Column(String(128), default="")
        last_name = Column(String(128), default="")
        is_email_verified = Column(Boolean, default=False)

        # Champs spécifiques à ServiceAccount
        client_id = Column(String(128), nullable=True, index=True)

        # Champs spécifiques à ApiKeyActor
        key_prefix = Column(String(32), nullable=True)
        key_name = Column(String(128), nullable=True)  # Renommé pour éviter conflit avec 'name' réservé
        expires_at = Column(DateTime(timezone=True), nullable=True)

        # Champs spécifiques à AIAgentActor
        agent_name = Column(String(128), nullable=True)
        owner_identity_id = Column(String(64), nullable=True, index=True)
        max_autonomy_level = Column(Integer, default=1)

        # JSON pour les permissions et scopes (flexibilité pour différents types)
        permissions = Column(JSON, nullable=True)  # type: ignore
        allowed_scopes = Column(JSON, nullable=True)  # type: ignore

except ImportError:
    SQLALCHEMY_AVAILABLE = False
    Base = None


class SQLAlchemyUnitOfWork(UnitOfWork):
    """Implémentation Unit of Work pour SQLAlchemy."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory
        self._session = None

    def begin(self) -> None:
        """Démarre une nouvelle transaction."""
        if self._session is None:
            self._session = self._session_factory()

    def commit(self) -> None:
        """Valide la transaction en cours."""
        if self._session is not None:
            self._session.commit()

    def rollback(self) -> None:
        """Annule la transaction en cours."""
        if self._session is not None:
            self._session.rollback()

    def __enter__(self) -> "SQLAlchemyUnitOfWork":
        """Context manager entry."""
        self.begin()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit avec gestion automatique des exceptions."""
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        if self._session is not None:
            self._session.close()
            self._session = None


class SQLAlchemySubjectRepository(SubjectRepository):
    """Implémentation du SubjectRepository via SQLAlchemy ORM avec ACL."""

    def __init__(self, db_url: str = "sqlite:///./aegis.db") -> None:
        if not SQLALCHEMY_AVAILABLE:
            raise RuntimeError("SQLAlchemy n'est pas installé sur cet environnement.")
        self.engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self._data_mapper: SubjectDataMapper = MapperFactory.create_subject_mapper()
        self._uow = SQLAlchemyUnitOfWork(self.SessionLocal)

    def get_by_id(self, subject_id: SubjectId) -> Optional[Subject]:
        """Récupère un sujet par son ID en utilisant le Data Mapper."""
        session = self.SessionLocal()
        try:
            orm_obj = session.query(SubjectORM).filter(SubjectORM.id == subject_id.value).first()
            if not orm_obj:
                return None
            # Utilisation du Data Mapper pour la conversion
            return self._data_mapper.to_domain(orm_obj)
        except Exception:
            # Les erreurs de mapping sont isolées ici et ne propagent pas les exceptions ORM
            return None
        finally:
            session.close()

    def get_by_email(self, email: EmailAddress) -> Optional[HumanIdentity]:
        """Récupère une identité humaine par son email en utilisant le Data Mapper."""
        session = self.SessionLocal()
        try:
            orm_obj = session.query(SubjectORM).filter(SubjectORM.email == email.value).first()
            if not orm_obj:
                return None
            # Utilisation du Data Mapper pour la conversion
            domain_obj = self._data_mapper.to_domain(orm_obj)
            if isinstance(domain_obj, HumanIdentity):
                return domain_obj
            return None
        except Exception:
            # Les erreurs de mapping sont isolées ici
            return None
        finally:
            session.close()

    def save(self, subject: Subject) -> None:
        """Sauvegarde un sujet en utilisant le Data Mapper et Unit of Work."""
        with self._uow:
            session = self._uow._session
            try:
                orm_obj = session.query(SubjectORM).filter(SubjectORM.id == subject.id.value).first()

                # Utilisation du Data Mapper pour la conversion Domain -> ORM
                orm_data = self._data_mapper.to_orm(subject)

                if not orm_obj:
                    # Création d'un nouvel ORM object avec les données mappées
                    orm_obj = SubjectORM(**orm_data)
                    session.add(orm_obj)
                else:
                    # Mise à jour de l'ORM object existant
                    for key, value in orm_data.items():
                        if hasattr(orm_obj, key):
                            setattr(orm_obj, key, value)

                session.flush()  # Flush pour validation mais pas de commit (géré par UoW)
            except Exception:
                # L'exception sera gérée par le Unit of Work qui fera un rollback
                raise

    def delete(self, subject_id: SubjectId) -> bool:
        """Supprime un sujet par son ID avec gestion transactionnelle."""
        with self._uow:
            session = self._uow._session
            try:
                orm_obj = session.query(SubjectORM).filter(SubjectORM.id == subject_id.value).first()
                if orm_obj:
                    session.delete(orm_obj)
                    session.flush()
                    return True
                return False
            except Exception:
                raise
