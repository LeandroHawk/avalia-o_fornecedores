from backend.apps.auditoria.models import Auditoria


def client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def registrar_auditoria(*, usuario, acao, objeto, objeto_id="", request=None, anterior=None, posterior=None, resultado="SUCESSO"):
    return Auditoria.objects.create(
        usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
        acao=acao,
        objeto=objeto,
        objeto_id=str(objeto_id or ""),
        ip=client_ip(request),
        valor_anterior=anterior,
        valor_posterior=posterior,
        resultado=resultado,
    )
