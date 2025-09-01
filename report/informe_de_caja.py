# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.tools import html_escape

TEAM_PAR_ID = 1
TEAM_NUB_ID = 5

JOURNAL_PAR_ID = 12
JOURNAL_NUB_ID = 14


class ReportCaja(models.AbstractModel):
    _name = "report.insumar_estadopagos.report_caja"
    _description = "Reporte QWeb - Informe de caja diario"

    def _normalize(self, s):
        return (s or "").strip().lower()

    def _pm_to_bucket(self, pm_name):
        """Mapea el nombre del método de pago a la columna del informe."""
        n = self._normalize(pm_name)
        # Efectivo
        if "efectivo" in n:
            return "efectivo"
        # Débito o Tarjeta de crédito (misma columna)
        if "débito" in n or "debito" in n or "tarjeta de crédito" in n or "tarjeta de credito" in n:
            return "debito_tarjeta"
        # Transferencia o Depósito (misma columna; NC se mostrará al final como línea)
        if "transferencia" in n or "depósito" in n or "deposito" in n:
            return "transf_deposito_nc"
        # Cheque
        if "cheque" in n:
            return "cheque"
        # Desconocido -> no clasifica a ninguna columna específica
        return None

    def _team_and_journal_from_cat(self, cat):
        if cat == "par":
            return TEAM_PAR_ID, JOURNAL_PAR_ID
        if cat == "nub":
            return TEAM_NUB_ID, JOURNAL_NUB_ID
        return None, None

    def _pm_line_ids_for_journal(self, journal_id):
        lines = self.env["account.payment.method.line"].search([("journal_id", "=", journal_id)])
        return set(lines.ids)

    def _collect(self, wizard):
        """Construye las líneas para el QWeb."""
        fecha = wizard.fecha
        cat = wizard.categoria
        team_id, journal_id = self._team_and_journal_from_cat(cat)
        if not team_id or not journal_id:
            return {
                "fecha": fecha,
                "categoria_label": dict(wizard._fields["categoria"].selection).get(cat, cat),
                "fact_lines": [],
                "refund_lines": [],
            }

        pm_line_ids = self._pm_line_ids_for_journal(journal_id)

        # 1) Pagos del día (asientos entry) -> vincular a facturas por ref == name
        entries = self.env["account.move"].search([
            ("move_type", "=", "entry"),
            ("state", "=", "posted"),
            ("date", "=", fecha),
            ("payment_id", "!=", False),
            ("ref", "!=", False),
        ])

        # Agregador por factura
        agg = {}  # invoice_id -> dict(cols)
        invoice_by_name = {}

        for entry in entries:
            payment = entry.payment_id
            if not payment or not payment.payment_method_line_id:
                continue
            if payment.payment_method_line_id.id not in pm_line_ids:
                continue

            # localizar factura por ref == name
            inv = self.env["account.move"].search([
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("name", "=", entry.ref),
            ], limit=1)
            if not inv:
                continue
            if getattr(inv, "team_id", False) and inv.team_id.id != team_id:
                # filtrar por equipo
                continue

            invoice_by_name[inv.name] = inv
            bucket = self._pm_to_bucket(payment.payment_method_line_id.name)
            if not bucket:
                continue

            # Inicializar estructura
            if inv.id not in agg:
                agg[inv.id] = {
                    "invoice": inv,
                    "efectivo": 0.0,
                    "debito_tarjeta": 0.0,
                    "transf_deposito_nc": 0.0,
                    "cheque": 0.0,
                }

            amount = abs(payment.amount or 0.0)
            if bucket in agg[inv.id]:
                agg[inv.id][bucket] += amount

        # 2) Todas las facturas del día (por equipo), aunque no tengan pagos del día
        invoices = self.env["account.move"].search([
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("invoice_date", "=", fecha),
            ("team_id", "=", team_id),
        ])

        # Asegurar presencia en agg con 0s
        for inv in invoices:
            if inv.id not in agg:
                agg[inv.id] = {
                    "invoice": inv,
                    "efectivo": 0.0,
                    "debito_tarjeta": 0.0,
                    "transf_deposito_nc": 0.0,
                    "cheque": 0.0,
                }

        # 3) Construir líneas de facturas (orden fecha desc)
        fact_lines = []
        for inv_id, data in agg.items():
            inv = data["invoice"]
            paid_today = (
                data["efectivo"]
                + data["debito_tarjeta"]
                + data["transf_deposito_nc"]
                + data["cheque"]
            )
            credito = inv.amount_total - paid_today
            if credito < 0:
                credito = 0.0

            fact_lines.append({
                "sequence_prefix": inv.sequence_prefix or "",
                "sequence_number": inv.sequence_number or "",
                "date_invoice": inv.invoice_date,
                "amount_total": inv.amount_total,
                "efectivo": data["efectivo"],
                "debito_tarjeta": data["debito_tarjeta"],
                "transf_deposito_nc": data["transf_deposito_nc"],
                "cheque": data["cheque"],
                "credito": credito,
                "partner_document": getattr(inv.partner_id, "document_number", "") or "",
            })

        # Ordenar facturas por fecha desc
        fact_lines.sort(key=lambda l: (l.get("date_invoice") or ""), reverse=True)

        # 4) Notas de crédito (al final)
        refunds = self.env["account.move"].search([
            ("move_type", "=", "out_refund"),
            ("state", "=", "posted"),
            ("invoice_date", "=", fecha),
            ("team_id", "=", team_id),
        ])

        refund_lines = []
        for inv in refunds:
            refund_lines.append({
                "sequence_prefix": inv.sequence_prefix or "",
                "sequence_number": inv.sequence_number or "",
                "date_invoice": inv.invoice_date,
                "amount_total": inv.amount_total,
                "efectivo": 0.0,
                "debito_tarjeta": 0.0,
                "transf_deposito_nc": inv.amount_total,  # NC va en esta columna
                "cheque": 0.0,
                "credito": 0.0,
                "partner_document": getattr(inv.partner_id, "document_number", "") or "",
            })

        categoria_label = dict(wizard._fields["categoria"].selection).get(cat, cat)

        return {
            "fecha": fecha,
            "categoria_label": categoria_label,
            "fact_lines": fact_lines,
            "refund_lines": refund_lines,
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env["informe.de.caja.wizard"].browse(docids[:1])
        vals = self._collect(wizard)
        return {
            "doc_ids": docids,
            "doc_model": "informe.de.caja.wizard",
            "docs": wizard,
            "fecha": vals["fecha"],
            "categoria_label": vals["categoria_label"],
            "fact_lines": vals["fact_lines"],
            "refund_lines": vals["refund_lines"],
        }
