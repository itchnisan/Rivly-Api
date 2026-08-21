"""add sea and canal water types

Revision ID: dba5ca6df7f6
Revises: 7b4c86929c10
Create Date: 2026-08-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'dba5ca6df7f6'
down_revision: Union[str, None] = '7b4c86929c10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE ne peut pas s'exécuter dans une transaction.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE water_type ADD VALUE IF NOT EXISTS 'sea'")
        op.execute("ALTER TYPE water_type ADD VALUE IF NOT EXISTS 'canal'")


def downgrade() -> None:
    # Postgres ne sait pas retirer une valeur d'un enum : il faudrait recréer
    # le type et migrer la colonne. Pas de chemin de retour automatique.
    raise NotImplementedError("Impossible de retirer une valeur d'un enum Postgres")
