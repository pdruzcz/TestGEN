"""Email service — Microsoft Graph API (OAuth2 Client Credentials)."""

import base64
import html
import logging
import time

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_GRAPH_TOKEN_URL = "https://login.microsoftonline.com/{}/oauth2/v2.0/token"
_GRAPH_SCOPE = "https://graph.microsoft.com/.default"
_GRAPH_SEND_URL = "https://graph.microsoft.com/v1.0/users/{}/sendMail"

_cached_token: str | None = None
_token_expires_at: float = 0


def _acquire_token() -> str:
    """Get OAuth2 access token via Client Credentials flow."""
    global _cached_token, _token_expires_at

    if _cached_token and time.monotonic() < _token_expires_at:
        return _cached_token

    settings = get_settings()
    url = _GRAPH_TOKEN_URL.format(settings.ms_tenant_id)

    resp = httpx.post(
        url,
        data={
            "client_id": settings.ms_client_id,
            "client_secret": settings.ms_client_secret.get_secret_value(),
            "scope": _GRAPH_SCOPE,
            "grant_type": "client_credentials",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    _cached_token = data["access_token"]
    _token_expires_at = time.monotonic() + data.get("expires_in", 3600) - 60
    logger.info("MS Graph OAuth2 token acquired, expires in %ds", data.get("expires_in", 3600))
    return _cached_token


def _build_payload(
    to: str,
    subject: str,
    body: str,
    attachment: tuple[str, bytes, str] | None = None,
) -> dict:
    """Payload sendMail. ``attachment`` = (nazwa pliku, zawartość, content type)
    — Graph fileAttachment z base64 (Story 7.6, AC3: faktura PDF)."""
    settings = get_settings()
    message: dict = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": body},
        "toRecipients": [{"emailAddress": {"address": to}}],
        "from": {"emailAddress": {"address": settings.smtp_from_email}},
    }
    if attachment is not None:
        name, content, content_type = attachment
        message["attachments"] = [
            {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": name,
                "contentType": content_type,
                "contentBytes": base64.b64encode(content).decode("ascii"),
            }
        ]
    return {"message": message}


def _send(to: str, subject: str, body: str, attachment: tuple[str, bytes, str] | None = None) -> None:
    settings = get_settings()
    if not settings.ms_client_id:
        logger.warning("MS OAuth not configured — email to %s will not be sent", to)
        return

    token = _acquire_token()
    url = _GRAPH_SEND_URL.format(settings.smtp_user)

    resp = httpx.post(
        url,
        json=_build_payload(to, subject, body, attachment=attachment),
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )

    if resp.status_code == 202:
        logger.info("Email sent to %s via Graph API", to)
        return

    resp.raise_for_status()


def send_html(to: str, subject: str, body: str) -> None:
    """Wysyłka gotowego HTML (Story 7.11) — treść renderowana przez usługę
    wywołującą (szablony Jinja2), transport jak wszystkie emaile TestGEN."""
    _send(to, subject, body)


def send_verification_email(email: str, token: str, name: str) -> None:
    settings = get_settings()
    url = settings.email_verification_url_template.format(token=token)
    safe_name = html.escape(name) if name else "Użytkowniku"
    body = (
        f"<h2>Witaj, {safe_name}!</h2>"
        f"<p>Kliknij poniższy link, aby aktywować swoje konto TestGEN:</p>"
        f'<p><a href="{html.escape(url)}">Aktywuj konto</a></p>'
        f"<p>Link jest ważny przez 24 godziny.</p>"
    )
    _send(email, "TestGEN — Aktywacja konta", body)


def send_invitation_email(email: str, token: str, inviter_name: str, company_name: str) -> None:
    settings = get_settings()
    url = settings.email_invitation_url_template.format(token=token)
    safe_inviter = html.escape(inviter_name)
    safe_company = html.escape(company_name)
    body = (
        f"<h2>Zaproszenie do TestGEN</h2>"
        f"<p>{safe_inviter} zaprasza Cię do zespołu <b>{safe_company}</b> na platformie TestGEN.</p>"
        f'<p><a href="{html.escape(url)}">Ustaw hasło i dołącz</a></p>'
        f"<p>Link jest ważny przez 24 godziny.</p>"
    )
    _send(email, f"TestGEN — Zaproszenie do {company_name}", body)


def send_password_reset_email(email: str, token: str, name: str) -> None:
    settings = get_settings()
    url = settings.email_password_reset_url_template.format(token=token)
    safe_name = html.escape(name) if name else "Użytkowniku"
    body = (
        f"<h2>Reset hasła — TestGEN</h2>"
        f"<p>Witaj, {safe_name}.</p>"
        f"<p>Administrator zresetował Twoje hasło. Kliknij poniższy link, aby ustawić nowe hasło:</p>"
        f'<p><a href="{html.escape(url)}">Ustaw nowe hasło</a></p>'
        f"<p>Link jest ważny przez 1 godzinę.</p>"
    )
    _send(email, "TestGEN — Reset hasła", body)


def send_payment_confirmation_email(email: str, plan_display: str, amount: str, period_end: str) -> None:
    """Potwierdzenie opłacenia subskrypcji (Story 7.4, AC5) — wywoływane
    z WebhookProcessor po aktywacji planu (best-effort)."""
    safe_plan = html.escape(plan_display)
    safe_amount = html.escape(amount)
    body = (
        f"<h2>Dziękujemy za płatność — TestGEN</h2>"
        f"<p>Subskrypcja planu <b>{safe_plan}</b> została aktywowana.</p>"
        f"<p>Kwota: <b>{safe_amount}</b> (rozliczenie miesięczne).</p>"
    )
    if period_end:
        body += f"<p>Plan aktywny do: {html.escape(period_end)}.</p>"
    body += "<p>Zarządzaj subskrypcją w panelu TestGEN (Billing).</p>"
    _send(email, "TestGEN — Potwierdzenie płatności", body)


def send_payment_failed_email(email: str, attempt: int, attempts_total: int, retry_in_days: int) -> None:
    """Nieudane obciążenie cykliczne (Story 7.2, AC6) — przy każdej porażce.

    Wywoływane z dunningu (SubscriptionService.register_failed_charge),
    best-effort — nie przerywa przepływu."""
    body = (
        f"<h2>Płatność nie powiodła się — TestGEN</h2>"
        f"<p>Nie udało się pobrać opłaty za subskrypcję "
        f"(próba {attempt} z {attempts_total + 1}).</p>"
        f"<p>Spróbujemy ponownie za {retry_in_days} "
        f"{'dzień' if retry_in_days == 1 else 'dni'}. Sprawdź metodę płatności "
        f"w panelu billingowym — jeśli karta wygasła lub brakuje środków, "
        f"zaktualizuj ją, aby uniknąć przerwania subskrypcji.</p>"
    )
    _send(email, "TestGEN — Płatność nie powiodła się", body)


def send_subscription_downgraded_email(email: str, grace_days: int) -> None:
    """Downgrade do Freemium po wyczerpaniu ponowień (Story 7.2, AC6, CR#2)."""
    body = (
        f"<h2>Subskrypcja obniżona do planu Freemium — TestGEN</h2>"
        f"<p>Po trzech nieudanych próbach pobrania opłaty Twoja subskrypcja "
        f"została obniżona do planu Freemium.</p>"
        f"<p>Przez najbliższe <b>{grace_days} dni</b> zachowujesz limity "
        f"dotychczasowego planu. Po tym okresie zaczną obowiązywać limity "
        f"Freemium.</p>"
        f"<p>Możesz w każdej chwili ponownie wykupić plan płatny w panelu "
        f"TestGEN (Billing) — wystarczy zaktualizować metodę płatności.</p>"
    )
    _send(email, "TestGEN — Subskrypcja obniżona do Freemium", body)


def send_payment_method_expired_email(email: str, method: str) -> None:
    """Metoda płatności wygasła/usunięta (Story 7.3, AC3) — notyfikacja
    ``ALIAS_EXPIRED``/``ALIAS_UNREGISTER`` przy aktywnej subskrypcji cyklicznej.
    Best-effort — nie przerywa przetwarzania webhooka."""
    safe_method = html.escape(method)
    body = (
        f"<h2>Metoda płatności wygasła — TestGEN</h2>"
        f"<p>Twoja metoda płatności (<b>{safe_method}</b>) używana do odnowień "
        f"subskrypcji wygasła lub została wyrejestrowana.</p>"
        f"<p>Dodaj kartę lub ponów rejestrację BLIK w panelu TestGEN "
        f"(Billing → Metody płatności), aby odnowienia następowały "
        f"automatycznie.</p>"
    )
    _send(email, "TestGEN — Metoda płatności wygasła", body)


def send_plan_changed_email(email: str, from_plan: str, to_plan: str) -> None:
    """Zmiana planu efektywna (Story 7.5, AC6) — po egzekucji zaplanowanego
    downgradu przez scheduler (best-effort, nie przerywa przebiegu)."""
    safe_from = html.escape(from_plan)
    safe_to = html.escape(to_plan)
    body = (
        f"<h2>Plan subskrypcji zmieniony — TestGEN</h2>"
        f"<p>Twój plan został zmieniony z <b>{safe_from}</b> na <b>{safe_to}</b> "
        f"zgodnie z zaplanowaną zmianą (koniec okresu rozliczeniowego).</p>"
        f"<p>Od teraz obowiązują limity planu {safe_to}. Szczegóły i historia "
        f"zmian dostępne w panelu TestGEN (Billing).</p>"
    )
    _send(email, "TestGEN — Zmiana planu subskrypcji", body)


def send_invoice_email(
    email: str,
    invoice_number: str,
    plan_display: str,
    amount: str,
    period: str,
    pdf_bytes: bytes,
) -> None:
    """Faktura VAT z załącznikiem PDF (Story 7.6, AC3) — po wygenerowaniu
    pliku w MinIO (asynchronicznie z Celery). Temat wg AC3:
    „Faktura VAT nr {numer} — TestGEN"; podsumowanie: plan, kwota, okres."""
    safe_number = html.escape(invoice_number)
    safe_plan = html.escape(plan_display)
    safe_amount = html.escape(amount)
    body = (
        f"<h2>Faktura VAT nr {safe_number} — TestGEN</h2>"
        f"<p>W załączniku przesyłamy fakturę VAT za subskrypcję TestGEN:</p>"
        f"<ul>"
        f"<li>Plan: <b>{safe_plan}</b></li>"
        f"<li>Kwota: <b>{safe_amount}</b></li>"
        f"<li>Okres: {html.escape(period)}</li>"
        f"</ul>"
        f"<p>Faktury znajdują się także w panelu TestGEN (Billing → Faktury).</p>"
    )
    filename = f"Faktura_{invoice_number.replace('/', '_')}.pdf"
    _send(
        email, f"Faktura VAT nr {invoice_number} — TestGEN", body, attachment=(filename, pdf_bytes, "application/pdf")
    )


def send_sync_degraded_email(email: str, provider: str, project_name: str, error: str) -> None:
    """Synchronizacja z TMS w stanie „degraded" (Story 8.11, AC6).

    Wysyłane raz — przy przejściu w ten stan, nie przy każdej nieudanej
    próbie. Powtarzanie maila co kwadrans przy dłuższej awarii TMS-a
    nauczyłoby odbiorcę go ignorować.
    """
    body = (
        f"<h2>Synchronizacja z {provider} przestała działać — TestGEN</h2>"
        f"<p>Trzy kolejne próby synchronizacji projektu <b>{project_name}</b> "
        f"zakończyły się błędem, więc synchronizacja została oznaczona jako "
        f"wymagająca uwagi.</p>"
        f"<p>Ostatni błąd: <code>{error}</code></p>"
        f"<p>Próby są ponawiane automatycznie — synchronizacja wróci do stanu "
        f"aktywnego sama, gdy tylko połączenie z {provider} zostanie "
        f"przywrócone. Jeśli błąd dotyczy poświadczeń albo uprawnień, popraw "
        f"konfigurację integracji w ustawieniach TestGEN.</p>"
    )
    _send(email, f"TestGEN — Synchronizacja z {provider} wymaga uwagi", body)
