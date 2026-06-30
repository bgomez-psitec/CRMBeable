from django.db import migrations, models
import django.db.models.deletion

PROVINCIAS = [
    'Álava', 'Albacete', 'Alicante', 'Almería', 'Asturias', 'Ávila',
    'Badajoz', 'Baleares', 'Barcelona', 'Bizkaia', 'Burgos', 'Cáceres',
    'Cádiz', 'Cantabria', 'Castellón', 'Ciudad Real', 'Córdoba', 'Cuenca',
    'Gipuzkoa', 'Girona', 'Granada', 'Guadalajara', 'Huelva', 'Huesca',
    'Jaén', 'La Coruña', 'La Rioja', 'Las Palmas', 'León', 'Lleida',
    'Lugo', 'Madrid', 'Málaga', 'Murcia', 'Navarra', 'Ourense',
    'Palencia', 'Pontevedra', 'Salamanca', 'Santa Cruz de Tenerife',
    'Segovia', 'Sevilla', 'Soria', 'Tarragona', 'Teruel', 'Toledo',
    'Valencia', 'Valladolid', 'Zamora', 'Zaragoza', 'Ceuta', 'Melilla',
]


def populate_provincias(apps, schema_editor):
    Provincia = apps.get_model('crm', 'Provincia')
    for i, nombre in enumerate(PROVINCIAS):
        Provincia.objects.create(nombre=nombre, orden=i + 1, habilitada=True)


def migrate_company_provincia(apps, schema_editor):
    Company = apps.get_model('crm', 'Company')
    Provincia = apps.get_model('crm', 'Provincia')
    prov_map = {p.nombre: p for p in Provincia.objects.all()}
    for company in Company.objects.exclude(provincia_text=''):
        prov = prov_map.get(company.provincia_text)
        if prov:
            company.provincia = prov
            company.save(update_fields=['provincia'])


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0023_inbox_colaborador_proceso'),
    ]

    operations = [
        # 1. Create the new Provincia model
        migrations.CreateModel(
            name='Provincia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100, unique=True)),
                ('orden', models.PositiveIntegerField(default=0)),
                ('habilitada', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Provincia',
                'verbose_name_plural': 'Provincias',
                'ordering': ['orden', 'nombre'],
            },
        ),

        # 2. Populate initial data
        migrations.RunPython(populate_provincias, migrations.RunPython.noop),

        # 3. Rename old CharField to a temporary name so we can read it during data migration
        migrations.RenameField(
            model_name='company',
            old_name='provincia',
            new_name='provincia_text',
        ),

        # 4. Add new FK column (nullable)
        migrations.AddField(
            model_name='company',
            name='provincia',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='companies',
                to='crm.provincia',
            ),
        ),

        # 5. Migrate existing text values to FK
        migrations.RunPython(migrate_company_provincia, migrations.RunPython.noop),

        # 6. Remove the old text column
        migrations.RemoveField(
            model_name='company',
            name='provincia_text',
        ),
    ]
