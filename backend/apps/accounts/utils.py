from backend.apps.accounts.models import UserProfile


def get_role(user):
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return UserProfile.Role.ADMINISTRADOR
    profile = getattr(user, "profile", None)
    return profile.role if profile else None


def is_admin(user):
    return get_role(user) == UserProfile.Role.ADMINISTRADOR


def is_compras(user):
    return get_role(user) == UserProfile.Role.COMPRAS


def is_fornecedor(user):
    return get_role(user) == UserProfile.Role.FORNECEDOR
