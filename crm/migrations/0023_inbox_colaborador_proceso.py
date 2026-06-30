from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0022_fase_logs'),
    ]

    operations = [
        migrations.AddField(
            model_name='inboxmessage',
            name='colaborador',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='inbox_messages', to='crm.colaborador'),
        ),
        migrations.AddField(
            model_name='inboxmessage',
            name='proceso_ma',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='inbox_messages', to='crm.procesoma'),
        ),
    ]
