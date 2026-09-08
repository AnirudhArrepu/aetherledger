from __future__ import with_statement
import os
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# import app models to get metadata
try:
    from app.db import models as models_module
    target_metadata = models_module.Base.metadata
except Exception:
    target_metadata = None

# Get DB URL from env if available
db_url = os.getenv('DATABASE_URL')
if db_url:
    config.set_main_option('sqlalchemy.url', db_url)


def run_migrations_offline():
    url = config.get_main_option('sqlalchemy.url')
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online_async():
    """Run migrations in 'online' mode using an async engine.
    This avoids calling asyncpg/await_only in a sync context which causes MissingGreenlet errors.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    connectable = create_async_engine(config.get_main_option('sqlalchemy.url'), poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        # run migrations in a sync context using the connection.run_sync helper
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online():
    # Fallback for sync DB URLs
    from sqlalchemy import engine_from_config

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    # If using an async DB URL (e.g., postgresql+asyncpg), run the async migration runner.
    url = config.get_main_option('sqlalchemy.url')
    if url and ('+asyncpg' in url or url.startswith('postgresql+async')):
        asyncio.run(run_migrations_online_async())
    else:
        run_migrations_online()
