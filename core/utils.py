from django.utils.http import url_has_allowed_host_and_scheme


def is_ajax(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def safe_next(request, fallback="/"):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
        return nxt
    return fallback


def int_or(value, default=1, lo=1, hi=99):
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default
