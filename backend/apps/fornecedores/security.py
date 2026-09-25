from backend.apps.accounts.utils import is_admin, is_compras, is_fornecedor


def user_can_access_fornecedor(user, fornecedor):
    if not user.is_authenticated:
        return False
    if is_admin(user) or is_compras(user):
        return True
    if is_fornecedor(user):
        vinculo = getattr(user, "fornecedor_vinculo", None)
        return bool(vinculo and vinculo.ativo and vinculo.fornecedor_id == fornecedor.id)
    return False


def fornecedores_for_user(user):
    from backend.apps.fornecedores.models import Fornecedor

    if is_admin(user) or is_compras(user):
        return Fornecedor.objects.all()
    if is_fornecedor(user) and hasattr(user, "fornecedor_vinculo"):
        return Fornecedor.objects.filter(id=user.fornecedor_vinculo.fornecedor_id)
    return Fornecedor.objects.none()
