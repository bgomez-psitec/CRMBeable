from django.contrib.auth.mixins import LoginRequiredMixin

from accounts.models import Role
from crm.models import Company


def allowed_company_ids(user):
    if not user.is_authenticated:
        return Company.objects.none().values_list('id', flat=True)
    if user.role == Role.ADMIN:
        return Company.objects.values_list('id', flat=True)
    if user.role == Role.EMPLEADO:
        return user.assigned_companies.values_list('id', flat=True)
    if user.role == Role.CEO:
        return [user.company_id] if user.company_id else []
    return []


def can_see_company(user, company_id):
    return company_id in set(allowed_company_ids(user))


def can_edit(user):
    return user.is_authenticated and user.role in (Role.ADMIN, Role.EMPLEADO)


def visible_companies(user):
    return Company.objects.filter(id__in=allowed_company_ids(user))


def visible_introductions(user):
    from crm.models import Introduction
    return Introduction.objects.filter(company_id__in=allowed_company_ids(user))


def visible_investors(user):
    from crm.models import Investor
    if user.is_authenticated and user.role == Role.CEO:
        investor_ids = visible_introductions(user).values_list('investor_id', flat=True)
        return Investor.objects.filter(id__in=investor_ids)
    return Investor.objects.all()


class CompanyAccessMixin(LoginRequiredMixin):
    """Restricts a view's Company queryset to the ones the request.user can see."""

    def get_queryset(self):
        return super().get_queryset().filter(id__in=allowed_company_ids(self.request.user))


class AdminOnlyMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != Role.ADMIN:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
