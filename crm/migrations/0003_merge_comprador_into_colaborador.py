"""
Merge Comprador into Colaborador:
- Add tipo flags + relation FK to Colaborador
- Copy every Comprador row to Colaborador (es_comprador=True)
- Migrate CompradorContacto → ColaboradorContacto
- Re-point ContactoMA.comprador FK from Comprador → Colaborador
- Drop Comprador and CompradorContacto tables
"""

import django.db.models.deletion
from django.db import migrations, models


def forward_migrate(apps, schema_editor):
    Comprador = apps.get_model('crm', 'Comprador')
    Colaborador = apps.get_model('crm', 'Colaborador')
    CompradorContacto = apps.get_model('crm', 'CompradorContacto')
    ColaboradorContacto = apps.get_model('crm', 'ColaboradorContacto')
    ContactoMA = apps.get_model('crm', 'ContactoMA')

    id_map = {}  # comprador.id → colaborador.id

    for comp in Comprador.objects.all():
        colab = Colaborador.objects.create(
            name=comp.name,
            type=comp.type,
            country=comp.country,
            sectors=comp.sectors,
            relation_id=comp.relation_id,
            notes=comp.notes,
            es_comprador=True,
        )
        id_map[comp.id] = colab.id

        for c in CompradorContacto.objects.filter(comprador_id=comp.id):
            ColaboradorContacto.objects.create(
                colaborador=colab,
                name=c.name,
                role=c.role,
                email=c.email,
                phone=c.phone,
            )

    for cma in ContactoMA.objects.all():
        new_id = id_map.get(cma.comprador_old_id)
        if new_id:
            cma.comprador_id = new_id
            cma.save(update_fields=['comprador_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0002_colaborador_estadocolaboracion_estadoma_and_more'),
    ]

    operations = [
        # ── 1. Add new fields to Colaborador ────────────────────────────────
        migrations.AddField(
            model_name='colaborador',
            name='es_comprador',
            field=models.BooleanField(default=False, verbose_name='Comprador'),
        ),
        migrations.AddField(
            model_name='colaborador',
            name='es_colaborador',
            field=models.BooleanField(default=False, verbose_name='Colaborador'),
        ),
        migrations.AddField(
            model_name='colaborador',
            name='es_cliente',
            field=models.BooleanField(default=False, verbose_name='Cliente'),
        ),
        migrations.AddField(
            model_name='colaborador',
            name='es_proveedor',
            field=models.BooleanField(default=False, verbose_name='Proveedor'),
        ),
        migrations.AddField(
            model_name='colaborador',
            name='relation',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='colaboradores',
                to='crm.etaparelacion',
            ),
        ),
        migrations.AlterField(
            model_name='colaborador',
            name='type',
            field=models.CharField(
                blank=True, max_length=100,
                verbose_name='Tipo de entidad',
                help_text='Ej: Startup, Corporate, Private Equity, Universidad…',
            ),
        ),

        # ── 2. Add temp FK on ContactoMA pointing to Colaborador ─────────────
        migrations.AddField(
            model_name='contactoma',
            name='comprador_nuevo',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to='crm.colaborador',
                db_column='comprador_nuevo_id',
            ),
        ),

        # ── 3. Data migration ─────────────────────────────────────────────────
        # We rename comprador→comprador_old and comprador_nuevo→comprador
        # via a RunPython that reads comprador_old_id directly from DB.
        migrations.RenameField('contactoma', 'comprador', 'comprador_old'),
        migrations.RenameField('contactoma', 'comprador_nuevo', 'comprador'),

        migrations.RunPython(forward_migrate, migrations.RunPython.noop),

        # ── 4. Remove the old FK (was Comprador, now unused) ─────────────────
        migrations.RemoveField('contactoma', 'comprador_old'),

        # ── 5. Drop Comprador tables ──────────────────────────────────────────
        migrations.DeleteModel('CompradorContacto'),
        migrations.DeleteModel('Comprador'),
    ]
