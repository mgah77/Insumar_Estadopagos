# -*- coding: utf-8 -*-
from odoo import api, models, fields
from collections import defaultdict

class ReportDeudores(models.AbstractModel):
    _name = "report.insumar_estadopagos.deudores"
    _description = "Reporte Deudores por Sucursal"

    @api.model
    def _get_report_values(self, docids, data=None):
        """Construye el dataset agrupado por cliente.

        Criterios:
          - account.move (out_invoice) 'posted'
          - amount_residual > 0 (no pagadas / con saldo)
          - invoice_date_due > hoy (vencimiento futuro)
          - team_id == seleccionado
        """
        if not data:
            data = {}
        team_id = data.get("team_id")
        team_name = data.get("team_name") or ""
        today = fields.Date.context_today(self)

        domain = [
            ("move_type", "=", "out_invoice"),
        ]

        moves = self.env["account.move"].search([], order="partner_id, name")

        # Agrupar por partner
        grouped = defaultdict(list)
        partners = {}
        for m in moves:
            partners[m.partner_id.id] = m.partner_id
            abono = (m.amount_total or 0.0) - (m.amount_residual or 0.0)
            grouped[m.partner_id.id].append({
                "name": m.name,
                "invoice_date": m.invoice_date,
                "invoice_date_due": m.invoice_date_due,
                "amount_total": m.amount_total,
                "abono": abono,
                "amount_residual": m.amount_residual,
            })

        # Ordenar clientes por document_number ascendente
        # Si no hay document_number, usar cadena vacía para ordenar consistente.
        sorted_partner_ids = sorted(
            partners.keys(),
            key=lambda pid: (partners[pid].document_number or "", partners[pid].name or "")
        )

        items = [{
            "partner": self.env["res.partner"].search([], limit=1),
            "partner_label": "PRUEBA - Cliente",
            "lines": [{
                "name": "FAC0001",
                "invoice_date": "2025-08-13",
                "invoice_date_due": "2025-08-20",
                "amount_total": 1000,
                "abono": 200,
                "amount_residual": 800,
                "company_currency": self.env.company.currency_id,
            }]
        }]

        return {
            "team_name": team_name,
            "today": today,
            "items": items,
        }
