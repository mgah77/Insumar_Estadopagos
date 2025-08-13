# -*- coding: utf-8 -*-
from odoo import api, models, fields
from collections import defaultdict

class ReportDeudores(models.AbstractModel):
    _name = "report.insumar_estadopagos.deudores"
    _description = "Reporte Deudores por Sucursal"

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        team_id = data.get("team_id")
        team_name = data.get("team_name", "")
        today = fields.Date.context_today(self)

        # Dominio mínimo (ajusta luego si quieres)
        domain = [("move_type", "=", "out_invoice")]
        if team_id:
            domain.append(("team_id", "=", team_id))

        # sudo() para evitar bloqueos por permisos al leer facturas
        moves = self.env["account.move"].sudo().search(domain, order="partner_id, name")

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
                "company_currency": m.company_currency_id,
            })

        sorted_partner_ids = sorted(
            partners.keys(),
            key=lambda pid: (
                (partners[pid].document_number or "").strip(),
                partners[pid].name or "",
            ),
        )

        groups = []
        for pid in sorted_partner_ids:
            p = partners[pid]
            groups.append({
                "partner": p,
                "partner_label": f"{(p.document_number or '').strip()} - {p.name or ''}",
                "lines": grouped[pid],
            })

        docs = self.env["insumar.deudores.wizard"].browse(docids or [])

        return {
            "doc_ids": docids or [],
            "doc_model": "insumar.deudores.wizard",
            "docs": docs,
            "team_name": team_name,
            "today": today,
            "groups": groups,
        }
