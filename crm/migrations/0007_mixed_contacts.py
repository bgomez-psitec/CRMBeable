from django.db import migrations, models
import django.db.models.deletion


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
                migrations.RunSQL(
                    sql=[
                        'ALTER TABLE crm_colaboracion MODIFY colaborador_id bigint DEFAULT NULL;',
                        'ALTER TABLE crm_colaboracion ADD CONSTRAINT crm_colaboracion_colaborador_id_43fc6132_fk_crm_colaborador_id '
                        'FOREIGN KEY (colaborador_id) REFERENCES crm_colaborador (id) ON DELETE SET NULL;',
                    ],
                    reverse_sql=migrations.RunSQL.noop,
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
