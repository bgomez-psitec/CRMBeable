from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0004_fix_contactoma_comprador_column'),
    ]

    operations = [
        migrations.AlterField(
            model_name='colaboracion',
            name='tipo_relacion',
            field=models.CharField(
                verbose_name='Tipo de relación',
                max_length=50,
                blank=True,
                choices=[
                    ('Colaborador', 'Colaborador'),
                    ('Cliente',     'Cliente'),
                    ('Proveedor',   'Proveedor'),
                    ('Otro',        'Otro'),
                ],
            ),
        ),
    ]
