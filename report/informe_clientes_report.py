from odoo import api, models

class ReportClientes(models.AbstractModel):
    _name = "report.insumar_estadopagos.report_clientes"
    _description = "Informe de Clientes (QWeb)"

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        move_ids = data.get("move_ids", [])
        docs = self.env["account.move"].browse(move_ids)
        # asegurar orden por fecha ascendente
        docs = docs.sorted(lambda m: (m.invoice_date or m.create_date or m.id, m.name or ""))

        partner = self.env["res.partner"].browse(data.get("partner_id")) if data.get("partner_id") else False

        return {
            "doc_ids": move_ids,
            "doc_model": "account.move",
            "docs": docs,
            "partner": partner,
            "partner_display": data.get("partner_display") or "",
            "invoice_scope": data.get("invoice_scope"),
            "date_scope": data.get("date_scope"),
            "date_from": data.get("date_from"),
            "date_to": data.get("date_to"),
        }
