from django.db import migrations, models
import django.db.models.deletion

FK_NAME = 'crm_colaboracion_colaborador_id_43fc6132_fk_crm_colaborador_id'


def _fix_colaboracion_fk(apps, schema_editor):
    """
    Idempotent: makes colaborador_id nullable and ensures the FK constraint exists
    exactly once, regardless of whether a previous migration already created it.
    """
    conn = schema_editor.connection
    with conn.cursor() as cursor:
        # Make column nullable (safe to run even if already nullable)
        cursor.execute(
            'ALTER TABLE crm_colaboracion MODIFY colaborador_id bigint DEFAULT NULL'
        )
        # Check whether the FK constraint already exists
        cursor.execute(
            '''
            SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
              AND CONSTRAINT_NAME = %s
              AND CONSTRAINT_TYPE = 'FOREIGN KEY'
            ''',
            ['crm_colaboracion', FK_NAME],
        )
        exists = cursor.fetchone()[0]
        if exists:
            cursor.execute(
                f'ALTER TABLE crm_colaboracion DROP FOREIGN KEY `{FK_NAME}`'
            )
        cursor.execute(
            f'ALTER TABLE crm_colaboracion ADD CONSTRAINT `{FK_NAME}` '
            f'FOREIGN KEY (colaborador_id) REFERENCES crm_colaborador (id) ON DELETE SET NULL'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0006_remove_colaborador_type'),
    ]

    operations = [
        # ── Introduction: already in DB, state-only ───────────────────────────

        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='introduction',
                    name='investor',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='introductions',
                        to='crm.investor',
                    ),
                ),
            ],
            database_operations=[],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='introduction',
                    name='colaborador',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='introductions',
                        to='crm.colaborador',
                    ),
                ),
            ],
            database_operations=[],
        ),

        # ── ContactoMA: already in DB, state-only ────────────────────────────

        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='contactoma',
                    name='comprador',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='contactos_ma',
                        to='crm.colaborador',
                    ),
                ),
            ],
            database_operations=[],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='contactoma',
                    name='investor',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='contactos_ma',
                        to='crm.investor',
                    ),
                ),
            ],
            database_operations=[],
        ),

        # ── Colaboracion: partially done; fix remaining via raw SQL ───────────

        # Update state for colaborador field
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='colaboracion',
                    name='colaborador',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='colaboraciones',
                        to='crm.colaborador',
                    ),
                ),
            ],
            database_operations=[
                # FK was dropped in a prior attempt; make column nullable and
                # recreate the FK constraint.
                migrations.RunPython(
                    _fix_colaboracion_fk,
                    reverse_code=migrations.RunPython.noop,
                ),
            ],
        ),
        # investor: add new FK column (not yet in DB)
        migrations.AddField(
            model_name='colaboracion',
            name='investor',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='colaboraciones',
                to='crm.investor',
            ),
        ),
    ]
