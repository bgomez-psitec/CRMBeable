from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.shortcuts import redirect, render

User = get_user_model()


def login_view(request):
    if request.user.is_authenticated:
        return redirect('crm:home')

    error = None
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        user = None
        try:
            candidate = User.objects.get(email__iexact=email)
            user = authenticate(request, username=candidate.username, password=password)
        except User.DoesNotExist:
            pass
        if user is not None and user.is_active:
            login(request, user)
            return redirect('crm:home')
        error = 'Email o contraseña incorrectos.'

    demo_users = User.objects.filter(is_active=True, is_superuser=False).order_by('role', 'first_name')
    return render(request, 'accounts/login.html', {'error': error, 'demo_users': demo_users})


def quick_login_view(request, user_id):
    if request.method != 'POST':
        return redirect('accounts:login')
    try:
        user = User.objects.get(id=user_id, is_active=True, is_superuser=False)
    except User.DoesNotExist:
        return redirect('accounts:login')
    user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, user)
    return redirect('crm:home')


def logout_view(request):
    logout(request)
    return redirect('accounts:login')
