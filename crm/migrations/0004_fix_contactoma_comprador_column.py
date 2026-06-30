from django.db import migrations


class Migration(migrations.Migration):
    """Rename crm_contactoma.comprador_nuevo_id → comprador_id, fixing the FK constraint."""

    dependencies = [
        ('crm', '0003_merge_comprador_into_colaborador'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "ALTER TABLE crm_contactoma DROP FOREIGN KEY crm_contactoma_comprador_nuevo_id_254ec7d0_fk_crm_colaborador_id;",
                "ALTER TABLE crm_contactoma CHANGE comprador_nuevo_id comprador_id bigint DEFAULT NULL;",
                "ALTER TABLE crm_contactoma ADD CONSTRAINT crm_contactoma_comprador_id_fk_crm_colaborador_id FOREIGN KEY (comprador_id) REFERENCES crm_colaborador (id);",
            ],
            reverse_sql=[
                "ALTER TABLE crm_contactoma DROP FOREIGN KEY crm_contactoma_comprador_id_fk_crm_colaborador_id;",
                "ALTER TABLE crm_contactoma CHANGE comprador_id comprador_nuevo_id bigint DEFAULT NULL;",
                "ALTER TABLE crm_contactoma ADD CONSTRAINT crm_contactoma_comprador_nuevo_id_254ec7d0_fk_crm_colaborador_id FOREIGN KEY (comprador_nuevo_id) REFERENCES crm_colaborador (id);",
            ],
        ),
    ]
