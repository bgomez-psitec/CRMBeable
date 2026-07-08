from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0031_tipo_contacto_colaborador_m2m'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='colaborador',
            name='tipos_contacto',
        ),
        migrations.DeleteModel(
            name='TipoContactoColaborador',
        ),
    ]
