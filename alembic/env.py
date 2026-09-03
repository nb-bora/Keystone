"""
Configuration Alembic pour Aegis IAM.

Système de migrations de schéma avec support pour différents backends de stockage.
"""

import asyncio
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import async_engine_from_config, async_sessionmaker, AsyncSession
from alembic import context

# Importer les modèles ORM
from aegis.drivers.sqlalchemy.driver import Base, SQLALCHEMY_AVAILABLE

# Configuration Alembic
config = context.config

# Interpréter le fichier de configuration pour Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Ajouter l'objet MetaData du modèle pour le support autogenerate
target_metadata = Base.metadata

# Autres valeurs du config, définies par les besoins env.py
# peuvent être acquises par mypy-alembic, etc.
# 
# from mypy_alembic.config import Config as MyPyConfig
# mypy_config = MyPyConfig.from_ini(config.config_file_name)
# target_metadata = mypy_config.generate_target_metadata()


def get_engine():
    """Crée le moteur de base de données depuis la configuration."""
    if SQLALCHEMY_AVAILABLE:
        try:
            # Essayer d'abord avec async
            from aegis.core.config import settings
            return async_engine_from_config(
                {"sqlalchemy.url": settings.database_url},
                prefix="sqlalchemy.",
                poolclass=pool.NullPool,
            )
        except Exception:
            # Fallback sur sync
            return engine_from_config(
                config.get_section(config.config_ini_section),
                prefix="sqlalchemy.",
                poolclass=pool.NullPool,
            )
    return None


def run_migrations_offline() -> None:
    """Exécute les migrations en mode 'offline'.
    
    Cela configure le contexte avec juste une URL et non un Engine,
    bien qu'un Engine soit acceptable ici également. En évitant de créer
    un Engine, nous n'avons même pas besoin de DBAPI disponible.
    
    Les appels à context.execute() ici émettent la chaîne donnée au
    sortie du script.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Exécute les migrations avec la connexion donnée."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Exécute les migrations en mode asynchrone."""
    from aegis.core.config import settings
    
    connectable = async_engine_from_config(
        {"sqlalchemy.url": settings.database_url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Exécute les migrations en mode 'online'.
    
    Dans ce scénario, nous devons créer un Engine et associer une connexion
    avec le contexte.
    """
    if SQLALCHEMY_AVAILABLE:
        try:
            # Essayer d'abord avec async
            asyncio.run(run_async_migrations())
        except Exception:
            # Fallback sur sync
            connectable = get_engine()
            
            with connectable.connect() as connection:
                do_run_migrations(connection)
    else:
        raise RuntimeError("SQLAlchemy n'est pas disponible pour les migrations")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
