from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0005_colaboracion_tipo_relacion_choices'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='colaborador',
            name='type',
        ),
    ]
