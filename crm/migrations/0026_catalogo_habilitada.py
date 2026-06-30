"""Migration 0026: Add habilitada field to all Catalogo subclasses."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0025_textchoices_to_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='estadopresentacion',
            name='habilitada',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='faseronda',
            name='habilitada',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='etaparelacion',
            name='habilitada',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='etaparelacioncolaborador',
            name='habilitada',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='estadoma',
            name='habilitada',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='fasema',
            name='habilitada',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='estadocolaboracion',
            name='habilitada',
            field=models.BooleanField(default=True),
        ),
    ]
