from django.db import migrations, models


INITIAL_TIPOS = [
    ('comprador',           'Comprador',           'amber', 0),
    ('colaborador',         'Colaborador',          'blue',  1),
    ('cliente',             'Cliente',              'green', 2),
    ('proveedor',           'Proveedor',            'grey',  3),
    ('inversor_esporadico', 'Inversor esporádico',  'amber', 4),
]


def seed_and_migrate(apps, schema_editor):
    TipoContacto = apps.get_model('crm', 'TipoContactoColaborador')
    Colaborador  = apps.get_model('crm', 'Colaborador')

    # Crear tipos iniciales
    tipos = {}
    for slug, nombre, color, orden in INITIAL_TIPOS:
        obj, _ = TipoContacto.objects.get_or_create(
            slug=slug, defaults={'nombre': nombre, 'color': color, 'orden': orden, 'habilitada': True}
        )
        tipos[slug] = obj

    # Migrar datos de booleanos a M2M
    BOOL_SLUGS = [
        ('es_comprador',           'comprador'),
        ('es_colaborador',         'colaborador'),
        ('es_cliente',             'cliente'),
        ('es_proveedor',           'proveedor'),
        ('es_inversor_esporadico', 'inversor_esporadico'),
    ]
    for col in Colaborador.objects.all():
        for field, slug in BOOL_SLUGS:
            if getattr(col, field, False):
                col.tipos_contacto.add(tipos[slug])


def reverse_migrate(apps, schema_editor):
    TipoContacto = apps.get_model('crm', 'TipoContactoColaborador')
    Colaborador  = apps.get_model('crm', 'Colaborador')
    SLUG_BOOL = {
        'comprador':           'es_comprador',
        'colaborador':         'es_colaborador',
        'cliente':             'es_cliente',
        'proveedor':           'es_proveedor',
        'inversor_esporadico': 'es_inversor_esporadico',
    }
    for col in Colaborador.objects.prefetch_related('tipos_contacto'):
        for tipo in col.tipos_contacto.all():
            field = SLUG_BOOL.get(tipo.slug)
            if field:
                setattr(col, field, True)
        col.save()


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0030_tipo_relacion_colaboracion_catalogo'),
    ]

    operations = [
        # 1. Crear tabla TipoContactoColaborador
        migrations.CreateModel(
            name='TipoContactoColaborador',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=120)),
                ('orden', models.PositiveIntegerField(default=0)),
                ('habilitada', models.BooleanField(default=True)),
                ('slug', models.SlugField(blank=True, unique=True)),
                ('color', models.CharField(
                    choices=[('amber', 'Ámbar'), ('blue', 'Azul'),
                             ('green', 'Verde'), ('grey', 'Gris')],
                    default='blue', max_length=10)),
            ],
            options={
                'verbose_name': 'Tipo de contacto',
                'verbose_name_plural': 'Tipos de contacto',
                'ordering': ['orden', 'id'],
            },
        ),

        # 2. Añadir M2M (mientras aún existen los booleanos)
        migrations.AddField(
            model_name='colaborador',
            name='tipos_contacto',
            field=models.ManyToManyField(blank=True, related_name='colaboradores',
                                         to='crm.tipocontactocolaborador',
                                         verbose_name='Tipo de contacto'),
        ),

        # 3. Sembrar tipos y migrar datos boolean → M2M
        migrations.RunPython(seed_and_migrate, reverse_migrate),

        # 4. Eliminar campos booleanos
        migrations.RemoveField(model_name='colaborador', name='es_cliente'),
        migrations.RemoveField(model_name='colaborador', name='es_colaborador'),
        migrations.RemoveField(model_name='colaborador', name='es_comprador'),
        migrations.RemoveField(model_name='colaborador', name='es_inversor_esporadico'),
        migrations.RemoveField(model_name='colaborador', name='es_proveedor'),
    ]
