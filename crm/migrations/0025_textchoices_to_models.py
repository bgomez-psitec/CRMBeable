"""
Migration 0025: Convert 11 TextChoices classes to proper DB models (CatalogoCRUD).

All tables and FK columns already exist in the DB (applied via worktree agent).
Uses SeparateDatabaseAndState to sync Django's migration state without touching the DB.
"""
import django.db.models.deletion
from django.db import migrations, models


def populate_catalogs(apps, schema_editor):
    """Seed initial data only if tables are empty."""
    for model_name, items in [
        ('Fund', ['BIKF', 'BISEF', 'BIGINF']),
        ('Area', [
            'Unknown', 'Worldwide', 'Southern Europe', 'Northern Europe',
            'Western Europe', 'Central & Eastern Europe', 'North America',
            'South & Central America', 'Northeast Asia', 'Southeast Asia',
            'Australia and Oceania', 'Middle East', 'Africa', 'Other',
        ]),
        ('TipoInversor', [
            'Unknown', 'Other', 'FFF', 'Business Angel', 'Intermediary',
            'Family Office', 'Multifamily Office', 'Venture Capital',
            'Corporate Venture Capital', 'Corporate', 'Investment Banking',
            'Patrimonial Banking', 'Private Banking', 'Banking', 'Foundation',
            'Endowments', 'Insurance Company', 'Sovereign Wealth Fund',
            'Pension Fund', 'Fund of Funds',
        ]),
        ('EtapaInversion', [
            'Pre-Seed', 'Seed', 'Pre Series A (VC Early Stage)',
            'Series A (VC)', 'Series B (VC Late Stage)', 'Series C (Growth Capital)',
        ]),
        ('RangoTicket', [
            '<200 k€', '200k€ - 500 k€', '500k€ - 1M€',
            '1M€-2M€', '2M€-5M€', '5M€-10M€', '>10M€',
        ]),
        ('RangoAUM', [
            '<500 k€', '500 k€ - 2 M€', '2 M€ - 20 M€',
            '20 M€ - 50 M€', '50 M€ - 100 M€', '100 M€ - 200 M€', '>200 M€',
        ]),
        ('Nivel', ['1', '2', '3', '4', '5', '6', '7', '8', '9']),
        ('TiempoMercado', [
            'UNKNOWN', '> 6 years', '4-6 years', '2-4 years',
            '1-2 years', '6 months-1 year', 'Inmediatly', 'Already on the market',
        ]),
        ('Facturacion', [
            'UNKNOWN', 'SALES > 10M€', '4M€ > SALES > 10M€', '2M€ > SALES > 5M€',
            '1M€ > SALES > 2M€', '500k > SALES > 1M€', '0 > SALES > 500k€', 'NO SALES',
        ]),
        ('EstadoInversion', [
            'Pre-seed', 'Seed', 'Start-Up', 'Early Stage', 'Venture Capital', 'Growth',
        ]),
        ('Sector', [
            'Advanced Manufacturing and Processing', 'Advanced Materials',
            'Artificial Intelligence', 'Data Mining', 'Industrial Biotechnology',
            'Microelectronics or Nanoelectronics', 'Nanotechnology', 'Other',
            'Other ICT', 'Pharma', 'Photonics',
        ]),
    ]:
        Model = apps.get_model('crm', model_name)
        for i, nombre in enumerate(items):
            Model.objects.get_or_create(nombre=nombre, defaults={'orden': i, 'habilitada': True})


_CATALOG_FIELDS = [
    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
    ('nombre', models.CharField(max_length=200, unique=True)),
    ('orden', models.PositiveIntegerField(default=0)),
    ('habilitada', models.BooleanField(default=True)),
]


def _catalog_model(name, verbose, verbose_plural):
    return migrations.CreateModel(
        name=name,
        fields=list(_CATALOG_FIELDS),
        options={
            'verbose_name': verbose,
            'verbose_name_plural': verbose_plural,
            'ordering': ['orden', 'nombre'],
            'abstract': False,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0024_provincia_model'),
    ]

    operations = [
        # ── 1. Create the 11 catalog tables (idempotent via RunPython check) ──
        _catalog_model('Fund', 'Fondo', 'Fondos'),
        _catalog_model('Area', 'Área', 'Áreas'),
        _catalog_model('TipoInversor', 'Tipo de inversor', 'Tipos de inversor'),
        _catalog_model('EtapaInversion', 'Etapa de inversión', 'Etapas de inversión'),
        _catalog_model('RangoTicket', 'Rango de ticket', 'Rangos de ticket'),
        _catalog_model('RangoAUM', 'Rango AUM', 'Rangos AUM'),
        _catalog_model('Nivel', 'Nivel', 'Niveles'),
        _catalog_model('TiempoMercado', 'Tiempo al mercado', 'Tiempos al mercado'),
        _catalog_model('Facturacion', 'Facturación', 'Facturaciones'),
        _catalog_model('EstadoInversion', 'Estado de inversión', 'Estados de inversión'),
        _catalog_model('Sector', 'Sector', 'Sectores'),

        # ── 2. Seed initial data (safe: get_or_create) ────────────────────────
        migrations.RunPython(populate_catalogs, migrations.RunPython.noop),

        # ── 3. Register all FK fields in Django state (columns already in DB) ──
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                # Company.fund
                migrations.RenameField('Company', 'fund', 'fund_text'),
                migrations.AddField(
                    model_name='Company', name='fund',
                    field=models.ForeignKey(blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='companies', to='crm.fund'),
                ),
                migrations.RemoveField('Company', 'fund_text'),

                # Company.stage
                migrations.RenameField('Company', 'stage', 'stage_text'),
                migrations.AddField(
                    model_name='Company', name='stage',
                    field=models.ForeignKey(blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='companies', to='crm.estadoinversion'),
                ),
                migrations.RemoveField('Company', 'stage_text'),

                # Company.trl
                migrations.RenameField('Company', 'trl', 'trl_text'),
                migrations.AddField(
                    model_name='Company', name='trl',
                    field=models.ForeignKey(blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='trl_companies', to='crm.nivel',
                        verbose_name='TRL'),
                ),
                migrations.RemoveField('Company', 'trl_text'),

                # Company.mrl
                migrations.RenameField('Company', 'mrl', 'mrl_text'),
                migrations.AddField(
                    model_name='Company', name='mrl',
                    field=models.ForeignKey(blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='mrl_companies', to='crm.nivel',
                        verbose_name='MRL'),
                ),
                migrations.RemoveField('Company', 'mrl_text'),

                # Company.ttm
                migrations.RenameField('Company', 'ttm', 'ttm_text'),
                migrations.AddField(
                    model_name='Company', name='ttm',
                    field=models.ForeignKey(blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='companies', to='crm.tiempomercado',
                        verbose_name='Time to market'),
                ),
                migrations.RemoveField('Company', 'ttm_text'),

                # Company.revenue
                migrations.RenameField('Company', 'revenue', 'revenue_text'),
                migrations.AddField(
                    model_name='Company', name='revenue',
                    field=models.ForeignKey(blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='companies', to='crm.facturacion',
                        verbose_name='Facturación'),
                ),
                migrations.RemoveField('Company', 'revenue_text'),

                # Investor.type
                migrations.RenameField('Investor', 'type', 'type_text'),
                migrations.AddField(
                    model_name='Investor', name='type',
                    field=models.ForeignKey(blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='investors', to='crm.tipoinversor'),
                ),
                migrations.RemoveField('Investor', 'type_text'),

                # Investor.ticket_range
                migrations.RenameField('Investor', 'ticket_range', 'ticket_range_text'),
                migrations.AddField(
                    model_name='Investor', name='ticket_range',
                    field=models.ForeignKey(blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='investors', to='crm.rangoticket',
                        verbose_name='Rango de ticket'),
                ),
                migrations.RemoveField('Investor', 'ticket_range_text'),

                # Investor.aum
                migrations.RenameField('Investor', 'aum', 'aum_text'),
                migrations.AddField(
                    model_name='Investor', name='aum',
                    field=models.ForeignKey(blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='investors', to='crm.rangoaum',
                        verbose_name='AUM'),
                ),
                migrations.RemoveField('Investor', 'aum_text'),

                # Round.rstage
                migrations.RenameField('Round', 'rstage', 'rstage_text'),
                migrations.AddField(
                    model_name='Round', name='rstage',
                    field=models.ForeignKey(blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='rounds', to='crm.etapainversion',
                        verbose_name='Etapa de la ronda'),
                ),
                migrations.RemoveField('Round', 'rstage_text'),
            ],
        ),
    ]
