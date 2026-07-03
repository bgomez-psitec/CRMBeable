"""
Migration 0029: Apply the TextChoices→FK schema changes to the actual DB.

Migration 0025 only updated Django's state (SeparateDatabaseAndState with
database_operations=[]) assuming the DB columns already existed in the
developer's environment. On a fresh DB they don't, so this migration does
the real work: adds the *_id FK columns, migrates text values to FK IDs,
and drops the old text columns.

State changes are NOT needed (already done by 0025), so only database work
is performed here.
"""
from django.db import migrations


# (db_table, old_col, new_col, catalog_table, catalog_col)
_FIELDS = [
    ('crm_company',  'fund',         'fund_id',          'crm_fund',           'nombre'),
    ('crm_company',  'stage',        'stage_id',         'crm_estadoinversion', 'nombre'),
    ('crm_company',  'trl',          'trl_id',           'crm_nivel',           'nombre'),
    ('crm_company',  'mrl',          'mrl_id',           'crm_nivel',           'nombre'),
    ('crm_company',  'ttm',          'ttm_id',           'crm_tiempomercado',   'nombre'),
    ('crm_company',  'revenue',      'revenue_id',       'crm_facturacion',     'nombre'),
    ('crm_investor', 'type',         'type_id',          'crm_tipoinversor',    'nombre'),
    ('crm_investor', 'ticket_range', 'ticket_range_id',  'crm_rangoticket',     'nombre'),
    ('crm_investor', 'aum',          'aum_id',           'crm_rangoaum',        'nombre'),
    ('crm_round',    'rstage',       'rstage_id',        'crm_etapainversion',  'nombre'),
]

# FK references for each catalog table
_FK_REF = {
    'crm_fund':            'crm_fund',
    'crm_estadoinversion': 'crm_estadoinversion',
    'crm_nivel':           'crm_nivel',
    'crm_tiempomercado':   'crm_tiempomercado',
    'crm_facturacion':     'crm_facturacion',
    'crm_tipoinversor':    'crm_tipoinversor',
    'crm_rangoticket':     'crm_rangoticket',
    'crm_rangoaum':        'crm_rangoaum',
    'crm_etapainversion':  'crm_etapainversion',
}


def _col_exists(cursor, table, col):
    cursor.execute(
        'SELECT COUNT(*) FROM information_schema.COLUMNS '
        'WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s',
        [table, col],
    )
    return cursor.fetchone()[0] > 0


def apply_fk_columns(apps, schema_editor):
    conn = schema_editor.connection
    with conn.cursor() as cur:
        for table, old_col, new_col, cat_table, cat_col in _FIELDS:
            # Skip if new FK column already exists (idempotent)
            if _col_exists(cur, table, new_col):
                continue

            # Skip if old text column no longer exists either (nothing to do)
            if not _col_exists(cur, table, old_col):
                continue

            # 1. Add the new FK column as nullable bigint
            cur.execute(
                f'ALTER TABLE `{table}` ADD COLUMN `{new_col}` bigint DEFAULT NULL'
            )

            # 2. Build a lookup dict: text value → catalog id
            cur.execute(f'SELECT id, `{cat_col}` FROM `{cat_table}`')
            lookup = {nombre: pk for pk, nombre in cur.fetchall()}

            # 3. Migrate text values to FK ids row by row
            cur.execute(f'SELECT id, `{old_col}` FROM `{table}`')
            for row_id, text_val in cur.fetchall():
                fk_id = lookup.get(text_val) if text_val else None
                cur.execute(
                    f'UPDATE `{table}` SET `{new_col}` = %s WHERE id = %s',
                    [fk_id, row_id],
                )

            # 4. Add FK constraint
            fk_name = f'{table}_{new_col}_{cat_table}_fk'[:64]
            cur.execute(
                f'ALTER TABLE `{table}` ADD CONSTRAINT `{fk_name}` '
                f'FOREIGN KEY (`{new_col}`) REFERENCES `{cat_table}` (id) ON DELETE SET NULL'
            )

            # 5. Drop old text column
            cur.execute(f'ALTER TABLE `{table}` DROP COLUMN `{old_col}`')


def reverse_fk_columns(apps, schema_editor):
    pass  # Non-reversible; data migration forward-only


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0028_add_website_phone_linkedin_to_company'),
    ]

    operations = [
        migrations.RunPython(apply_fk_columns, reverse_fk_columns),
    ]
