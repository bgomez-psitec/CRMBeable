from django.urls import path

from . import views

app_name = 'crm'

urlpatterns = [
    path('', views.home, name='home'),
    path('participadas/', views.companies, name='companies'),
    path('participadas/nueva/', views.company_create, name='company_create'),
    path('participadas/<int:pk>/', views.company_detail, name='company_detail'),
    path('participadas/<int:pk>/editar/', views.company_edit, name='company_edit'),
    path('participadas/<int:company_pk>/rondas/nueva/', views.round_create, name='round_create'),
    path('rondas/<int:pk>/', views.round_detail, name='round_detail'),
    path('presentaciones/<int:pk>/estado/', views.intro_set_status, name='intro_set_status'),
    path('inversores/', views.investors, name='investors'),
    path('inversores/<int:pk>/', views.investor_detail, name='investor_detail'),
    path('inversores/<int:pk>/log/', views.investor_log_create, name='investor_log_create'),
    path('presentaciones/', views.presentaciones, name='presentaciones'),
    path('bandeja/', views.inbox, name='inbox'),
    path('informes/', views.reports, name='reports'),
    # M&A
    path('participadas/<int:company_pk>/ma/nuevo/', views.proceso_ma_create, name='proceso_ma_create'),
    path('ma/<int:pk>/', views.proceso_ma_detail, name='proceso_ma_detail'),
    path('ma/contacto/<int:pk>/estado/', views.contacto_ma_set_status, name='contacto_ma_set_status'),
    path('compradores/', views.compradores, name='compradores'),
    path('compradores/<int:pk>/', views.comprador_detail, name='comprador_detail'),
    # Colaboraciones
    path('colaboraciones/', views.colaboraciones_global, name='colaboraciones'),
    path('participadas/<int:company_pk>/colaboraciones/nueva/', views.colaboracion_create, name='colaboracion_create'),
    path('colaboraciones/<int:pk>/', views.colaboracion_detail, name='colaboracion_detail'),
    path('colaboradores/', views.colaboradores, name='colaboradores'),
    path('colaboradores/<int:pk>/', views.colaborador_detail, name='colaborador_detail'),
    # Admin
    path('usuarios/', views.users, name='users'),
    path('ajustes/', views.settings_view, name='settings'),
]
