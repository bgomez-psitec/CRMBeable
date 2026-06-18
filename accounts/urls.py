from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('login/quick/<int:user_id>/', views.quick_login_view, name='quick_login'),
    path('logout/', views.logout_view, name='logout'),
]
