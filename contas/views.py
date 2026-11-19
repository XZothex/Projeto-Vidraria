from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, connection, transaction
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .forms import ContaForm

Usuario = get_user_model()


def _confirmar_administrador(usuario):
    if not (usuario.is_active and usuario.is_superuser):
        raise PermissionDenied


@login_required
@require_http_methods(["GET", "POST"])
def usuarios(request):
    _confirmar_administrador(request.user)
    form = ContaForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                _confirmar_administrador(Usuario.objects.select_for_update().get(pk=request.user.pk))
                conta = form.save(commit=False)
                conta.is_staff = conta.is_superuser = form.cleaned_data["administrador"]
                conta.save()
                if connection.vendor == "mysql":
                    perfil = "administracao" if conta.is_superuser else form.cleaned_data["perfil_mysql"]
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "INSERT INTO usuario (nome, login, perfil) VALUES (%s, %s, %s)",
                            [conta.get_full_name(), conta.username, perfil],
                        )
        except IntegrityError:
            form.add_error("username", "O nome de usuário já está em uso no Django ou no estoque.")
        else:
            messages.success(request, "Usuário cadastrado.")
            return redirect("contas:usuarios")
    pagina = Paginator(Usuario.objects.order_by("username", "pk"), 25).get_page(request.GET.get("page"))
    return render(request, "contas/usuarios.html", {"form": form, "pagina": pagina})


@login_required
@require_POST
@transaction.atomic
def alternar_status(request, pk):
    _confirmar_administrador(request.user)
    status = request.POST.get("ativo")
    if status not in {"0", "1"}:
        return HttpResponseBadRequest("Status inválido.")
    if pk == request.user.pk:
        messages.error(request, "Você não pode desativar sua própria conta.")
        return redirect("contas:usuarios")

    bloqueados = {
        conta.pk: conta for conta in Usuario.objects.select_for_update()
        .filter(pk__in=[request.user.pk, pk]).order_by("pk")
    }
    _confirmar_administrador(bloqueados[request.user.pk])
    conta = bloqueados.get(pk)
    if conta is None:
        raise Http404("Usuário não encontrado.")
    conta.is_active = status == "1"
    conta.save(update_fields=["is_active"])
    messages.success(request, "Conta ativada." if conta.is_active else "Conta desativada.")
    return redirect("contas:usuarios")
