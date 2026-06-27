# -----------------------------------------------------------------------------
# backend/app/models/base.py
#
# Defines the single SQLAlchemy DeclarativeBase that every ORM model inherits.
# Alembic's env.py imports Base.metadata from here to discover all tables for
# migration autogeneration — every model file must subclass Base or its table
# won't appear in migrations. Keeping this file minimal avoids circular imports
# when models reference each other via foreign keys.
# -----------------------------------------------------------------------------

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
