"""Validadores e utilitários simples (CPF/CNPJ, telefone, números positivos)."""
import re
from decimal import Decimal

from django.core.exceptions import ValidationError


def somente_digitos(valor):
    return re.sub(r"\D", "", valor or "")


def validar_positivo(valor):
    """Medidas e valores, quando preenchidos, devem ser maiores que zero."""
    if valor is not None and valor <= Decimal("0"):
        raise ValidationError("Informe um valor maior que zero.")


def _dv(digitos, pesos):
    soma = sum(int(d) * p for d, p in zip(digitos, pesos))
    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


_PESOS_CNPJ_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_PESOS_CNPJ_2 = [6] + _PESOS_CNPJ_1


def completar_cnpj(base12):
    """Recebe 12 dígitos e devolve o CNPJ de 14 dígitos com os verificadores."""
    d1 = _dv(base12, _PESOS_CNPJ_1)
    d2 = _dv(base12 + d1, _PESOS_CNPJ_2)
    return base12 + d1 + d2


def completar_cpf(base9):
    """Recebe 9 dígitos e devolve o CPF de 11 dígitos com os verificadores."""
    d1 = _dv(base9, range(10, 1, -1))
    d2 = _dv(base9 + d1, range(11, 1, -1))
    return base9 + d1 + d2


def cpf_valido(digitos):
    return (
        len(digitos) == 11
        and digitos != digitos[0] * 11
        and completar_cpf(digitos[:9]) == digitos
    )


def cnpj_valido(digitos):
    return (
        len(digitos) == 14
        and digitos != digitos[0] * 14
        and completar_cnpj(digitos[:12]) == digitos
    )


def validar_cpf_cnpj(valor):
    """Aceita CPF (11 dígitos) ou CNPJ (14 dígitos), com ou sem máscara."""
    if not re.fullmatch(r"[0-9. /\-]+", valor or ""):
        raise ValidationError("Informe um CPF/CNPJ válido, usando apenas números e pontuação de documento.")
    digitos = somente_digitos(valor)
    if len(digitos) == 11:
        if not cpf_valido(digitos):
            raise ValidationError("CPF inválido.")
    elif len(digitos) == 14:
        if not cnpj_valido(digitos):
            raise ValidationError("CNPJ inválido.")
    else:
        raise ValidationError("Informe um CPF (11 dígitos) ou CNPJ (14 dígitos).")


def validar_telefone(valor):
    digitos = somente_digitos(valor)
    if len(digitos) not in (10, 11):
        raise ValidationError("Informe o telefone com DDD (10 ou 11 dígitos).")


def formatar_cpf_cnpj(digitos):
    if digitos and len(digitos) == 11:
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
    if digitos and len(digitos) == 14:
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"
    return digitos or ""


def formatar_telefone(digitos):
    if digitos and len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    if digitos and len(digitos) == 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    return digitos or ""
