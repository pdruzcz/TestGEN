"""Celery task: PDF faktury VAT — Story 7.6 (AC2/AC3).

Asynchroniczne dokończenie generowania faktury po webhooku płatności:
render HTML→PDF (WeasyPrint) → upload do MinIO → email z załącznikiem do
Ownera. Nie blokuje przetwarzania webhooka (AC2). Kontekst RLS admina
(NIL UUID) jak w WebhookProcessor/billing_tasks (przepływ systemowy).
"""

import asyncio
import logging
import uuid

from sqlalchemy import text

from app.core.constants import NIL_UUID
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _generate_invoice_pdf_impl(invoice_id: str) -> dict:
    from app.core.database import task_session
    from app.services.billing.invoice_service import InvoiceService

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{NIL_UUID}'"))
        invoice = await InvoiceService(session).render_and_deliver(uuid.UUID(invoice_id))
        await session.commit()
    return {"invoice_id": invoice_id, "invoice_number": invoice.invoice_number, "pdf_path": invoice.pdf_path}


@celery_app.task(
    name="app.workers.tasks.generate_invoice_pdf.generate_invoice_pdf",
    bind=True,
    max_retries=3,
)
def generate_invoice_pdf(self, invoice_id: str) -> dict:
    """PDF + email dla faktury — enqueue z WebhookProcessor po `paid`."""
    try:
        return asyncio.run(_generate_invoice_pdf_impl(invoice_id))
    except Exception as exc:
        logger.exception("Generowanie PDF faktury %s nie powiodło się", invoice_id)
        raise self.retry(exc=exc, countdown=60) from exc
