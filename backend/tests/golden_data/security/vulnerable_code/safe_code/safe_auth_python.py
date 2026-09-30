# Golden safe fixture (Story 4.14): ownership is verified — must NOT be flagged.
# False-positive guard for the SAST regression suite.


def get_invoice(invoice_id, current_user):
    invoice = Invoice.objects.get(pk=invoice_id)
    if invoice.owner_id != current_user.id:
        raise PermissionDenied("Brak dostępu")
    return invoice
