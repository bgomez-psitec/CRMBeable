import django.db.models.deletion
from django.db import migrations, models


def seed_grado_actividad(apps, schema_editor):
    GradoActividad = apps.get_model('crm', 'GradoActividad')
    for i, nombre in enumerate(['No Activo', 'Poco Activo', 'Medio Activo', 'Muy Activo']):
        GradoActividad.objects.get_or_create(nombre=nombre, defaults={'orden': i})


def migrate_colaborador_relation(apps, schema_editor):
    """Map Colaborador.relation from EtapaRelacionColaborador to EtapaRelacion by nombre."""
    Colaborador = apps.get_model('crm', 'Colaborador')
    EtapaRelacion = apps.get_model('crm', 'EtapaRelacion')
    EtapaRelacionColaborador = apps.get_model('crm', 'EtapaRelacionColaborador')

    etapa_map = {}
    for erc in EtapaRelacionColaborador.objects.all():
        er = EtapaRelacion.objects.filter(nombre=erc.nombre).first()
        if er:
            etapa_map[erc.pk] = er.pk

    for col in Colaborador.objects.filter(relation__isnull=False):
        new_pk = etapa_map.get(col.relation_id)
        col.relation_new_id = new_pk
        col.save(update_fields=['relation_new_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0033_tipo_inversion_estado_publico_inversores'),
    ]

    operations = [
        # 1. Crear GradoActividad con seeds
        migrations.CreateModel(
            name='GradoActividad',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=200, unique=True)),
                ('orden', models.PositiveIntegerField(default=0)),
                ('habilitada', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Grado de actividad',
                'verbose_name_plural': 'Grados de actividad',
                'ordering': ['orden', 'nombre'],
                'abstract': False,
            },
        ),
        migrations.RunPython(seed_grado_actividad, migrations.RunPython.noop),

        # 2. Campo temporal para migrar datos de relation antes de borrar EtapaRelacionColaborador
        migrations.AddField(
            model_name='colaborador',
            name='relation_new',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='colaboradores_new', to='crm.etaparelacion'),
        ),
        migrations.RunPython(migrate_colaborador_relation, migrations.RunPython.noop),

        # 3. Borrar campo antiguo y renombrar el nuevo
        migrations.RemoveField(model_name='colaborador', name='relation'),
        migrations.RenameField(model_name='colaborador', old_name='relation_new', new_name='relation'),

        # 4. Ajustar related_name en el campo renombrado
        migrations.AlterField(
            model_name='colaborador',
            name='relation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='colaboradores', to='crm.etaparelacion'),
        ),

        # 5. Añadir grado_actividad a Colaborador e Investor
        migrations.AddField(
            model_name='colaborador',
            name='grado_actividad',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='colaboradores', to='crm.gradoactividad'),
        ),
        migrations.AddField(
            model_name='investor',
            name='grado_actividad',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='investors', to='crm.gradoactividad'),
        ),

        # 6. Borrar EtapaRelacionColaborador
        migrations.DeleteModel(name='EtapaRelacionColaborador'),
    ]
