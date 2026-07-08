import django.db.models.deletion
from django.db import migrations, models


INITIAL_TIPOS = ['Colaborador', 'Cliente', 'Proveedor', 'Otro']


def seed_and_migrate(apps, schema_editor):
    TipoRelacion = apps.get_model('crm', 'TipoRelacionColaboracion')
    Colaboracion = apps.get_model('crm', 'Colaboracion')

    # Crear los tipos iniciales
    tipos = {}
    for i, nombre in enumerate(INITIAL_TIPOS):
        obj, _ = TipoRelacion.objects.get_or_create(nombre=nombre, defaults={'orden': i})
        tipos[nombre] = obj

    # Migrar datos existentes: tipo_relacion_old → FK
    for col in Colaboracion.objects.exclude(tipo_relacion_old=''):
        nombre = col.tipo_relacion_old.strip()
        if nombre in tipos:
            col.tipo_relacion = tipos[nombre]
        else:
            # Valor desconocido: crear entrada nueva
            obj, _ = TipoRelacion.objects.get_or_create(
                nombre=nombre, defaults={'orden': TipoRelacion.objects.count()})
            col.tipo_relacion = obj
        col.save(update_fields=['tipo_relacion'])


def reverse_migrate(apps, schema_editor):
    Colaboracion = apps.get_model('crm', 'Colaboracion')
    for col in Colaboracion.objects.select_related('tipo_relacion'):
        if col.tipo_relacion:
            col.tipo_relacion_old = col.tipo_relacion.nombre
            col.save(update_fields=['tipo_relacion_old'])


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0029_company_notes'),
    ]

    operations = [
        # 1. Crear tabla TipoRelacionColaboracion
        migrations.CreateModel(
            name='TipoRelacionColaboracion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=120)),
                ('orden', models.PositiveIntegerField(default=0)),
                ('habilitada', models.BooleanField(default=True)),
            ],
            options={'ordering': ['orden', 'id'], 'abstract': False},
        ),

        # 2. Renombrar columna antigua a tipo_relacion_old
        migrations.RenameField(
            model_name='colaboracion',
            old_name='tipo_relacion',
            new_name='tipo_relacion_old',
        ),

        # 3. Añadir la nueva columna FK (nullable)
        migrations.AddField(
            model_name='colaboracion',
            name='tipo_relacion',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='colaboraciones',
                to='crm.tiporelacioncolaboracion',
                verbose_name='Tipo de relación',
            ),
        ),

        # 4. Migrar datos existentes
        migrations.RunPython(seed_and_migrate, reverse_migrate),

        # 5. Eliminar columna antigua
        migrations.RemoveField(model_name='colaboracion', name='tipo_relacion_old'),
    ]
