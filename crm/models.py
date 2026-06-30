from django.db import models


class Catalogo(models.Model):
    """Catálogo editable desde Ajustes (estados, fases de ronda, etapas de relación)."""

    nombre = models.CharField(max_length=120)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True
        ordering = ['orden', 'id']

    def __str__(self):
        return self.nombre


class EstadoPresentacion(Catalogo):
    pass


class FaseRonda(Catalogo):
    pass


class EtapaRelacion(Catalogo):
    pass


class EtapaRelacionColaborador(Catalogo):
    pass


class Fund(models.TextChoices):
    BIKF = 'BIKF', 'BIKF'
    BISEF = 'BISEF', 'BISEF'
    BIGINF = 'BIGINF', 'BIGINF'


class Area(models.TextChoices):
    UNKNOWN = 'Unknown', 'Unknown'
    WORLDWIDE = 'Worldwide', 'Worldwide'
    SOUTHERN_EUROPE = 'Southern Europe', 'Southern Europe'
    NORTHERN_EUROPE = 'Northern Europe', 'Northern Europe'
    WESTERN_EUROPE = 'Western Europe', 'Western Europe'
    CENTRAL_EASTERN_EUROPE = 'Central & Eastern Europe', 'Central & Eastern Europe'
    NORTH_AMERICA = 'North America', 'North America'
    SOUTH_CENTRAL_AMERICA = 'South & Central America', 'South & Central America'
    NORTHEAST_ASIA = 'Northeast Asia', 'Northeast Asia'
    SOUTHEAST_ASIA = 'Southeast Asia', 'Southeast Asia'
    AUSTRALIA_OCEANIA = 'Australia and Oceania', 'Australia and Oceania'
    MIDDLE_EAST = 'Middle East', 'Middle East'
    AFRICA = 'Africa', 'Africa'
    OTHER = 'Other', 'Other'


class TipoInversor(models.TextChoices):
    UNKNOWN = 'Unknown', 'Unknown'
    OTHER = 'Other', 'Other'
    FFF = 'FFF', 'FFF'
    BUSINESS_ANGEL = 'Business Angel', 'Business Angel'
    INTERMEDIARY = 'Intermediary', 'Intermediary'
    FAMILY_OFFICE = 'Family Office', 'Family Office'
    MULTIFAMILY_OFFICE = 'Multifamily Office', 'Multifamily Office'
    VENTURE_CAPITAL = 'Venture Capital', 'Venture Capital'
    CORPORATE_VENTURE_CAPITAL = 'Corporate Venture Capital', 'Corporate Venture Capital'
    CORPORATE = 'Corporate', 'Corporate'
    INVESTMENT_BANKING = 'Investment Banking', 'Investment Banking'
    PATRIMONIAL_BANKING = 'Patrimonial Banking', 'Patrimonial Banking'
    PRIVATE_BANKING = 'Private Banking', 'Private Banking'
    BANKING = 'Banking', 'Banking'
    FOUNDATION = 'Foundation', 'Foundation'
    ENDOWMENTS = 'Endowments', 'Endowments'
    INSURANCE_COMPANY = 'Insurance Company', 'Insurance Company'
    SOVEREIGN_WEALTH_FUND = 'Sovereign Wealth Fund', 'Sovereign Wealth Fund'
    PENSION_FUND = 'Pension Fund', 'Pension Fund'
    FUND_OF_FUNDS = 'Fund of Funds', 'Fund of Funds'


class EtapaInversion(models.TextChoices):
    UNKNOWN = 'Unknown', 'Unknown'
    PRE_SEED = 'Pre-Seed', 'Pre-Seed'
    SEED = 'Seed', 'Seed'
    PRE_SERIES_A = 'Pre Series A (VC Early Stage)', 'Pre Series A (VC Early Stage)'
    SERIES_A = 'Series A (VC)', 'Series A (VC)'
    SERIES_B = 'Series B (VC Late Stage)', 'Series B (VC Late Stage)'
    SERIES_C = 'Series C (Growth Capital)', 'Series C (Growth Capital)'


class RangoTicket(models.TextChoices):
    UNKNOWN = 'Unknown', 'Unknown'
    LT_200K = '<200 k€', '<200 k€'
    R200_500K = '200k€ - 500 k€', '200k€ - 500 k€'
    R500K_1M = '500k€ - 1M€', '500k€ - 1M€'
    R1M_2M = '1M€-2M€', '1M€-2M€'
    R2M_5M = '2M€-5M€', '2M€-5M€'
    R5M_10M = '5M€-10M€', '5M€-10M€'
    GT_10M = '>10M€', '>10M€'


class RangoAUM(models.TextChoices):
    UNKNOWN = 'Unknown', 'Unknown'
    LT_500K = '<500 k€', '<500 k€'
    R500K_2M = '500 k€ - 2 M€', '500 k€ - 2 M€'
    R2M_20M = '2 M€ - 20 M€', '2 M€ - 20 M€'
    R20M_50M = '20 M€ - 50 M€', '20 M€ - 50 M€'
    R50M_100M = '50 M€ - 100 M€', '50 M€ - 100 M€'
    R100M_200M = '100 M€ - 200 M€', '100 M€ - 200 M€'
    GT_200M = '>200 M€', '>200 M€'


class Provincia(models.TextChoices):
    UNKNOWN = 'Unknown', 'Unknown'
    ALAVA = 'Álava', 'Álava'
    ALBACETE = 'Albacete', 'Albacete'
    ALICANTE = 'Alicante', 'Alicante'
    ALMERIA = 'Almería', 'Almería'
    ASTURIAS = 'Asturias', 'Asturias'
    AVILA = 'Ávila', 'Ávila'
    BADAJOZ = 'Badajoz', 'Badajoz'
    BALEARES = 'Baleares', 'Baleares'
    BARCELONA = 'Barcelona', 'Barcelona'
    BIZKAIA = 'Bizkaia', 'Bizkaia'
    BURGOS = 'Burgos', 'Burgos'
    CACERES = 'Cáceres', 'Cáceres'
    CADIZ = 'Cádiz', 'Cádiz'
    CANTABRIA = 'Cantabria', 'Cantabria'
    CASTELLON = 'Castellón', 'Castellón'
    CIUDAD_REAL = 'Ciudad Real', 'Ciudad Real'
    CORDOBA = 'Córdoba', 'Córdoba'
    CUENCA = 'Cuenca', 'Cuenca'
    GIPUZKOA = 'Gipuzkoa', 'Gipuzkoa'
    GIRONA = 'Girona', 'Girona'
    GRANADA = 'Granada', 'Granada'
    GUADALAJARA = 'Guadalajara', 'Guadalajara'
    HUELVA = 'Huelva', 'Huelva'
    HUESCA = 'Huesca', 'Huesca'
    JAEN = 'Jaén', 'Jaén'
    LA_CORUNA = 'La Coruña', 'La Coruña'
    LA_RIOJA = 'La Rioja', 'La Rioja'
    LAS_PALMAS = 'Las Palmas', 'Las Palmas'
    LEON = 'León', 'León'
    LLEIDA = 'Lleida', 'Lleida'
    LUGO = 'Lugo', 'Lugo'
    MADRID = 'Madrid', 'Madrid'
    MALAGA = 'Málaga', 'Málaga'
    MURCIA = 'Murcia', 'Murcia'
    NAVARRA = 'Navarra', 'Navarra'
    OURENSE = 'Ourense', 'Ourense'
    PALENCIA = 'Palencia', 'Palencia'
    PONTEVEDRA = 'Pontevedra', 'Pontevedra'
    SALAMANCA = 'Salamanca', 'Salamanca'
    SC_TENERIFE = 'Santa Cruz de Tenerife', 'Santa Cruz de Tenerife'
    SEGOVIA = 'Segovia', 'Segovia'
    SEVILLA = 'Sevilla', 'Sevilla'
    SORIA = 'Soria', 'Soria'
    TARRAGONA = 'Tarragona', 'Tarragona'
    TERUEL = 'Teruel', 'Teruel'
    TOLEDO = 'Toledo', 'Toledo'
    VALENCIA = 'Valencia', 'Valencia'
    VALLADOLID = 'Valladolid', 'Valladolid'
    ZAMORA = 'Zamora', 'Zamora'
    ZARAGOZA = 'Zaragoza', 'Zaragoza'
    CEUTA = 'Ceuta', 'Ceuta'
    MELILLA = 'Melilla', 'Melilla'


class Nivel(models.TextChoices):
    UNKNOWN = 'Unknown', 'Unknown'
    L1 = '1', '1'
    L2 = '2', '2'
    L3 = '3', '3'
    L4 = '4', '4'
    L5 = '5', '5'
    L6 = '6', '6'
    L7 = '7', '7'
    L8 = '8', '8'
    L9 = '9', '9'


class TiempoMercado(models.TextChoices):
    UNKNOWN = 'UNKNOWN', 'UNKNOWN'
    GT_6Y = '> 6 years', '> 6 years'
    R4_6Y = '4-6 years', '4-6 years'
    R2_4Y = '2-4 years', '2-4 years'
    R1_2Y = '1-2 years', '1-2 years'
    R6M_1Y = '6 months-1 year', '6 months-1 year'
    INMEDIATLY = 'Inmediatly', 'Inmediatly'
    ON_MARKET = 'Already on the market', 'Already on the market'


class Facturacion(models.TextChoices):
    UNKNOWN = 'UNKNOWN', 'UNKNOWN'
    GT_10M = 'SALES > 10M€', 'SALES > 10M€'
    R4_10M = '4M€ > SALES > 10M€', '4M€ > SALES > 10M€'
    R2_5M = '2M€ > SALES > 5M€', '2M€ > SALES > 5M€'
    R1_2M = '1M€ > SALES > 2M€', '1M€ > SALES > 2M€'
    R500K_1M = '500k > SALES > 1M€', '500k > SALES > 1M€'
    R0_500K = '0 > SALES > 500k€', '0 > SALES > 500k€'
    NO_SALES = 'NO SALES', 'NO SALES'


class EstadoInversion(models.TextChoices):
    PRE_SEED = 'Pre-seed', 'Pre-seed'
    SEED = 'Seed', 'Seed'
    START_UP = 'Start-Up', 'Start-Up'
    EARLY_STAGE = 'Early Stage', 'Early Stage'
    VENTURE_CAPITAL = 'Venture Capital', 'Venture Capital'
    GROWTH = 'Growth', 'Growth'


class Sector(models.TextChoices):
    ADV_MANUFACTURING = 'Advanced Manufacturing and Processing', 'Advanced Manufacturing and Processing'
    ADV_MATERIALS = 'Advanced Materials', 'Advanced Materials'
    AI = 'Artificial Intelligence', 'Artificial Intelligence'
    DATA_MINING = 'Data Mining', 'Data Mining'
    INDUSTRIAL_BIOTECH = 'Industrial Biotechnology', 'Industrial Biotechnology'
    MICRO_NANO_ELECTRONICS = 'Microelectronics or Nanoelectronics', 'Microelectronics or Nanoelectronics'
    NANOTECHNOLOGY = 'Nanotechnology', 'Nanotechnology'
    OTHER = 'Other', 'Other'
    OTHER_ICT = 'Other ICT', 'Other ICT'
    PHARMA = 'Pharma', 'Pharma'
    PHOTONICS = 'Photonics', 'Photonics'


class Company(models.Model):
    name = models.CharField(max_length=200)
    int_code = models.CharField('Código interno', max_length=50, blank=True)
    fund = models.CharField(max_length=20, choices=Fund.choices, blank=True)
    country = models.CharField(max_length=100, blank=True)
    provincia = models.CharField(max_length=50, choices=Provincia.choices, blank=True)
    sectors = models.CharField('Sectores', max_length=500, blank=True, help_text='Lista separada por comas')
    stage = models.CharField(max_length=50, choices=EstadoInversion.choices, blank=True)
    trl = models.CharField('TRL', max_length=20, choices=Nivel.choices, blank=True)
    mrl = models.CharField('MRL', max_length=20, choices=Nivel.choices, blank=True)
    ttm = models.CharField('Time to market', max_length=30, choices=TiempoMercado.choices, blank=True)
    revenue = models.CharField('Facturación', max_length=30, choices=Facturacion.choices, blank=True)
    valuation = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    valuation_date = models.DateField(null=True, blank=True)
    logo = models.ImageField('Logo', upload_to='logos/', null=True, blank=True)

    class Meta:
        verbose_name = 'Participada'
        verbose_name_plural = 'Participadas'
        ordering = ['name']

    def __str__(self):
        return self.name


class CompanyContact(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f'{self.name} ({self.company})'


class Round(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='rounds')
    type = models.CharField('Tipo', max_length=120)
    target = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    status = models.ForeignKey(FaseRonda, on_delete=models.SET_NULL, null=True, blank=True, related_name='rounds')
    rstage = models.CharField('Etapa de la ronda', max_length=50, choices=EtapaInversion.choices, blank=True)
    start = models.DateField(null=True, blank=True)
    close = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'Ronda'
        verbose_name_plural = 'Rondas'
        ordering = ['-start']

    def __str__(self):
        return f'{self.type} — {self.company}'


class Investor(models.Model):
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=50, choices=TipoInversor.choices, blank=True)
    country = models.CharField(max_length=100, blank=True)
    sectors = models.CharField(max_length=500, blank=True, help_text='Lista separada por comas')
    areas = models.CharField(max_length=500, blank=True, help_text='Lista separada por comas')
    tipo_inversion = models.CharField('Tipo de inversión', max_length=100, blank=True)
    inv_stage = models.CharField('Etapa de inversión', max_length=500, blank=True)
    ticket_range = models.CharField('Rango de ticket', max_length=30, choices=RangoTicket.choices, blank=True)
    aum = models.CharField('AUM', max_length=30, choices=RangoAUM.choices, blank=True)
    pub_status = models.CharField('Estado público', max_length=100, blank=True)
    relation = models.ForeignKey(EtapaRelacion, on_delete=models.SET_NULL, null=True, blank=True, related_name='investors')
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Inversor'
        verbose_name_plural = 'Inversores'
        ordering = ['name']

    def __str__(self):
        return self.name


class InvestorContact(models.Model):
    investor = models.ForeignKey(Investor, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f'{self.name} ({self.investor})'


class InvestorLog(models.Model):
    CONTEXT_CHOICES = [
        ('', 'General'),
        ('ronda', 'Ronda de Inversión'),
        ('ma', 'Proceso M&A'),
        ('colaboracion', 'Colaboración'),
    ]
    investor = models.ForeignKey(Investor, on_delete=models.CASCADE, related_name='logs')
    round = models.ForeignKey(Round, on_delete=models.SET_NULL, null=True, blank=True, related_name='investor_logs')
    proceso_ma = models.ForeignKey('ProcesoMA', on_delete=models.SET_NULL, null=True, blank=True, related_name='investor_logs')
    colaboracion = models.ForeignKey('Colaboracion', on_delete=models.SET_NULL, null=True, blank=True, related_name='investor_logs')
    date = models.DateField(null=True, blank=True)
    type = models.CharField(max_length=50, blank=True)
    summary = models.TextField(blank=True)
    created_by = models.CharField(max_length=150, blank=True)
    attachment_url = models.CharField(max_length=500, blank=True)
    context = models.CharField(max_length=20, blank=True, choices=CONTEXT_CHOICES)

    def process_label(self):
        if self.round:
            return f'{self.round.company.name} · {self.round.type}'
        if self.proceso_ma:
            return f'{self.proceso_ma.nombre} (M&A)'
        if self.colaboracion:
            return str(self.colaboracion.descripcion or self.colaboracion.company.name)
        return ''

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'{self.investor} — {self.date}'


class ColaboradorLog(models.Model):
    CONTEXT_CHOICES = [
        ('', 'General'),
        ('ronda', 'Ronda de Inversión'),
        ('ma', 'Proceso M&A'),
        ('colaboracion', 'Colaboración'),
    ]
    colaborador = models.ForeignKey('Colaborador', on_delete=models.CASCADE, related_name='logs')
    round = models.ForeignKey(Round, on_delete=models.SET_NULL, null=True, blank=True, related_name='colaborador_logs')
    proceso_ma = models.ForeignKey('ProcesoMA', on_delete=models.SET_NULL, null=True, blank=True, related_name='colaborador_logs')
    colaboracion = models.ForeignKey('Colaboracion', on_delete=models.SET_NULL, null=True, blank=True, related_name='colaborador_logs')
    date = models.DateField(null=True, blank=True)
    type = models.CharField(max_length=50, blank=True)
    summary = models.TextField(blank=True)
    created_by = models.CharField(max_length=150, blank=True)
    attachment_url = models.CharField(max_length=500, blank=True)
    context = models.CharField(max_length=20, blank=True, choices=CONTEXT_CHOICES)

    def process_label(self):
        if self.round:
            return f'{self.round.company.name} · {self.round.type}'
        if self.proceso_ma:
            return f'{self.proceso_ma.nombre} (M&A)'
        if self.colaboracion:
            return str(self.colaboracion.descripcion or self.colaboracion.company.name)
        return ''

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'{self.colaborador} — {self.date}'


class Introduction(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='introductions')
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='introductions')
    investor = models.ForeignKey(Investor, on_delete=models.SET_NULL, null=True, blank=True, related_name='introductions')
    colaborador = models.ForeignKey('Colaborador', on_delete=models.SET_NULL, null=True, blank=True, related_name='introductions')
    status = models.ForeignKey(EstadoPresentacion, on_delete=models.SET_NULL, null=True, blank=True, related_name='introductions')
    ticket = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    intro_by = models.CharField('Presentado por', max_length=150, blank=True)
    next_action = models.CharField(max_length=255, blank=True)
    next_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Presentación'
        verbose_name_plural = 'Presentaciones'
        ordering = ['-date']

    @property
    def contact(self):
        return self.investor or self.colaborador

    def __str__(self):
        return f'{self.contact} → {self.company}'


class Interaction(models.Model):
    introduction = models.ForeignKey(Introduction, on_delete=models.CASCADE, related_name='interactions')
    date = models.DateField(null=True, blank=True)
    type = models.CharField(max_length=50, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'{self.introduction} — {self.date}'


# ─── M&A ─────────────────────────────────────────────────────────────────────

class EstadoMA(Catalogo):
    pass


class FaseMA(Catalogo):
    pass


class ProcesoMA(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='procesos_ma')
    nombre = models.CharField('Nombre del proceso', max_length=200)
    fase = models.ForeignKey(FaseMA, on_delete=models.SET_NULL, null=True, blank=True, related_name='procesos')
    precio_pedido = models.DecimalField('Precio pedido (€)', max_digits=14, decimal_places=2, null=True, blank=True)
    cerrado = models.BooleanField('Proceso cerrado', default=False)
    start = models.DateField('Inicio', null=True, blank=True)
    close = models.DateField('Cierre estimado', null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Proceso M&A'
        verbose_name_plural = 'Procesos M&A'
        ordering = ['-start']

    def __str__(self):
        return f'{self.nombre} — {self.company}'


class ContactoMA(models.Model):
    proceso = models.ForeignKey(ProcesoMA, on_delete=models.CASCADE, related_name='contactos')
    comprador = models.ForeignKey('Colaborador', on_delete=models.SET_NULL, null=True, blank=True, related_name='contactos_ma')
    investor = models.ForeignKey('Investor', on_delete=models.SET_NULL, null=True, blank=True, related_name='contactos_ma')
    status = models.ForeignKey(EstadoMA, on_delete=models.SET_NULL, null=True, blank=True, related_name='contactos')
    oferta_precio = models.DecimalField('Oferta (€)', max_digits=14, decimal_places=2, null=True, blank=True)
    nda_firmado = models.BooleanField('NDA firmado', default=False)
    dd_iniciado = models.BooleanField('DD iniciada', default=False)
    date = models.DateField('Fecha contacto', null=True, blank=True)
    intro_by = models.CharField('Presentado por', max_length=150, blank=True)
    next_action = models.CharField('Próximo paso', max_length=255, blank=True)
    next_date = models.DateField('Fecha próximo paso', null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Contacto M&A'
        verbose_name_plural = 'Contactos M&A'
        ordering = ['-date']

    @property
    def contact(self):
        return self.comprador or self.investor

    def __str__(self):
        return f'{self.contact} → {self.proceso}'


class InteraccionMA(models.Model):
    contacto = models.ForeignKey(ContactoMA, on_delete=models.CASCADE, related_name='interactions')
    date = models.DateField(null=True, blank=True)
    type = models.CharField(max_length=50, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'{self.contacto} — {self.date}'


# ─── Colaboraciones ───────────────────────────────────────────────────────────

class EstadoColaboracion(Catalogo):
    pass


class Colaborador(models.Model):
    name = models.CharField('Nombre', max_length=200)
    country = models.CharField('País', max_length=100, blank=True)
    sectors = models.CharField('Sectores', max_length=500, blank=True)
    relation = models.ForeignKey(EtapaRelacionColaborador, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='colaboradores')
    # Tipo de contacto (múltiple selección)
    es_comprador          = models.BooleanField('Comprador',           default=False)
    es_colaborador        = models.BooleanField('Colaborador',         default=False)
    es_cliente            = models.BooleanField('Cliente',             default=False)
    es_proveedor          = models.BooleanField('Proveedor',           default=False)
    es_inversor_esporadico = models.BooleanField('Inversor esporádico', default=False)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Colaborador'
        verbose_name_plural = 'Colaboradores'
        ordering = ['name']

    def __str__(self):
        return self.name


class ColaboradorContacto(models.Model):
    colaborador = models.ForeignKey(Colaborador, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f'{self.name} ({self.colaborador})'


class Colaboracion(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='colaboraciones')
    colaborador = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True, blank=True, related_name='colaboraciones')
    investor = models.ForeignKey('Investor', on_delete=models.SET_NULL, null=True, blank=True, related_name='colaboraciones')
    status = models.ForeignKey(EstadoColaboracion, on_delete=models.SET_NULL, null=True, blank=True, related_name='colaboraciones')
    TIPO_RELACION_CHOICES = [
        ('Colaborador', 'Colaborador'),
        ('Cliente',     'Cliente'),
        ('Proveedor',   'Proveedor'),
        ('Otro',        'Otro'),
    ]
    tipo_relacion = models.CharField('Tipo de relación', max_length=50,
                                     choices=TIPO_RELACION_CHOICES, blank=True)
    descripcion = models.TextField('Descripción', blank=True)
    date = models.DateField('Fecha inicio', null=True, blank=True)
    intro_by = models.CharField('Presentado por', max_length=150, blank=True)
    next_action = models.CharField('Próximo paso', max_length=255, blank=True)
    next_date = models.DateField('Fecha próximo paso', null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Colaboración'
        verbose_name_plural = 'Colaboraciones'
        ordering = ['-date']

    @property
    def contact(self):
        return self.colaborador or self.investor

    def __str__(self):
        return f'{self.contact} ↔ {self.company}'


class InteraccionColaboracion(models.Model):
    colaboracion = models.ForeignKey(Colaboracion, on_delete=models.CASCADE, related_name='interactions')
    date = models.DateField(null=True, blank=True)
    type = models.CharField(max_length=50, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'{self.colaboracion} — {self.date}'


# ─── Logs de fase/estado de proceso ──────────────────────────────────────────

class ProcesoMAFaseLog(models.Model):
    proceso    = models.ForeignKey(ProcesoMA, on_delete=models.CASCADE, related_name='fase_logs')
    fase       = models.ForeignKey(FaseMA, on_delete=models.SET_NULL, null=True, related_name='proceso_logs')
    date       = models.DateField()
    created_by = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ['date', 'pk']

    def __str__(self):
        return f'{self.proceso} → {self.fase} ({self.date})'


class RoundFaseLog(models.Model):
    round      = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='fase_logs')
    fase       = models.ForeignKey(FaseRonda, on_delete=models.SET_NULL, null=True, related_name='round_logs')
    date       = models.DateField()
    created_by = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ['date', 'pk']

    def __str__(self):
        return f'{self.round} → {self.fase} ({self.date})'


# ─── Bandeja ──────────────────────────────────────────────────────────────────

class InboxMessage(models.Model):
    from_name = models.CharField(max_length=200)
    from_email = models.EmailField(blank=True)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    date = models.DateField(null=True, blank=True)
    unread = models.BooleanField(default=True)
    saved = models.BooleanField(default=False)
    investor    = models.ForeignKey(Investor,     on_delete=models.SET_NULL, null=True, blank=True, related_name='inbox_messages')
    colaborador = models.ForeignKey('Colaborador', on_delete=models.SET_NULL, null=True, blank=True, related_name='inbox_messages')
    round       = models.ForeignKey(Round,        on_delete=models.SET_NULL, null=True, blank=True, related_name='inbox_messages')
    proceso_ma  = models.ForeignKey(ProcesoMA,    on_delete=models.SET_NULL, null=True, blank=True, related_name='inbox_messages')

    class Meta:
        verbose_name = 'Mensaje de bandeja'
        verbose_name_plural = 'Bandeja de entrada'
        ordering = ['-date']

    def __str__(self):
        return self.subject or f'Mensaje de {self.from_name}'


# ─── Documentación ────────────────────────────────────────────────────────────

import os, re

def _slug(text):
    return re.sub(r'[^\w]+', '_', text.strip(), flags=re.ASCII).strip('_') or 'doc'

def documento_upload_path(instance, filename):
    company_slug = _slug(instance.company.name)
    if instance.round_id:
        sub = f'Ronda_{_slug(instance.round.type)}'
    elif instance.proceso_ma_id:
        sub = f'MA_{_slug(instance.proceso_ma.nombre)}'
    elif instance.carpeta and instance.carpeta != 'general':
        sub = instance.carpeta.capitalize()
    else:
        sub = 'General'
    return f'docs/{company_slug}/{sub}/{filename}'


class Documento(models.Model):
    CARPETA_CHOICES = [
        ('general',   'General'),
        ('emails',    'Emails'),
        ('reuniones', 'Reuniones'),
        ('notas',     'Notas'),
    ]
    company    = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='documentos')
    round      = models.ForeignKey(Round, null=True, blank=True, on_delete=models.SET_NULL, related_name='documentos')
    proceso_ma = models.ForeignKey(ProcesoMA, null=True, blank=True, on_delete=models.SET_NULL, related_name='documentos')
    carpeta    = models.CharField(max_length=20, choices=CARPETA_CHOICES, default='general')
    file       = models.FileField(upload_to=documento_upload_path)
    name       = models.CharField('Nombre', max_length=255, blank=True)
    description = models.TextField('Descripción', blank=True)
    uploaded_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Documento'
        verbose_name_plural = 'Documentos'
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.name or os.path.basename(self.file.name)

    @property
    def carpeta_label(self):
        if self.round_id:
            return self.round.type
        if self.proceso_ma_id:
            return self.proceso_ma.nombre
        return self.get_carpeta_display()
