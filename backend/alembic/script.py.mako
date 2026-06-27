## -----------------------------------------------------------------------------
## backend/alembic/script.py.mako
##
## Mako template used by `alembic revision --autogenerate` to scaffold new
## migration files. Alembic substitutes ${message}, ${up_revision}, and other
## variables at generation time. The file that gets written lands in
## alembic/versions/ with the timestamp-prefixed filename defined in alembic.ini.
## To add project-wide boilerplate to every migration (e.g. extra imports or a
## reviewer checklist), edit this template rather than each migration file.
## -----------------------------------------------------------------------------
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
