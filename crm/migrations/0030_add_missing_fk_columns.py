"""
Migration 0030: Add FK columns that 0007 registered only in Django state.

crm_introduction.colaborador_id  → FK to crm_colaborador
crm_contactoma.investor_id       → FK to crm_investor
"""
from django.db import migrations


def _col_exists(cursor, table, col):
    cursor.execute(
        'SELECT COUNT(*) FROM information_schema.COLUMNS '
        'WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s',
        [table, col],
    )
    return cursor.fetchone()[0] > 0


def add_missing_columns(apps, schema_editor):
    conn = schema_editor.connection
    with conn.cursor() as cur:
        if not _col_exists(cur, 'crm_introduction', 'colaborador_id'):
            cur.execute(
                'ALTER TABLE crm_introduction '
                'ADD COLUMN colaborador_id bigint DEFAULT NULL, '
                'ADD CONSTRAINT crm_introduction_colaborador_id_fk '
                'FOREIGN KEY (colaborador_id) REFERENCES crm_colaborador (id) ON DELETE SET NULL'
            )

        if not _col_exists(cur, 'crm_contactoma', 'investor_id'):
            cur.execute(
                'ALTER TABLE crm_contactoma '
                'ADD COLUMN investor_id bigint DEFAULT NULL, '
                'ADD CONSTRAINT crm_contactoma_investor_id_fk '
                'FOREIGN KEY (investor_id) REFERENCES crm_investor (id) ON DELETE SET NULL'
            )


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0029_apply_textchoices_fk_to_db'),
    ]

    operations = [
        migrations.RunPython(add_missing_columns, migrations.RunPython.noop),
    ]
