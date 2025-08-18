from odoo import api, fields, models
from datetime import date, timedelta

class InformeClientesWizard(models.TransientModel):
    _name = "informe.clientes.wizard"
    _description = "Wizard Informe de Clientes"

    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        required=True,
        domain=[("customer_rank", ">", 0)],
    )

    invoice_scope = fields.Selection(
        [
            ("pending", "Facturas pendientes"),
            ("all", "Todas las facturas"),
        ],
        string="Ámbito de facturas",
        required=True,
        default="pending",
    )

    date_scope = fields.Selection(
        [
            ("current_year", "Año en curso"),
            ("last_12", "Últimos 12 meses"),
            ("range", "Rango de fechas"),
        ],
        string="Rango",
        required=True,
        default="current_year",
    )

    date_from = fields.Date(string="Desde")
    date_to = fields.Date(string="Hasta")

    @api.onchange("date_scope")
    def _onchange_date_scope(self):
        today = fields.Date.context_today(self)
        if self.date_scope == "current_year":
            self.date_from = date(today.year, 1, 1)
            self.date_to = today
        elif self.date_scope == "last_12":
            # 12 meses hacia atrás desde hoy (incluye hoy)
            self.date_to = today
            # restar 365 días para cubrir 12 meses aprox, evitando monthdelta (sin dateutil)
            self.date_from = today - timedelta(days=365)
        elif self.date_scope == "range":
            # no autocompletar; queda a elección del usuario
            self.date_from = self.date_from
            self.date_to = self.date_to

    def _compute_domain(self):
        self.ensure_one()
        domain = [
            ("move_type", "in", ["out_invoice", "out_refund"]),
            # ("state", "=", "posted"),
            ("partner_id", "=", self.partner_id.id),
        ]

        # Pendientes vs todas
         #if self.invoice_scope == "pending":
          #   domain += [("amount_residual", ">", 0)]

        # Fechas
         #if self.date_scope in ("current_year", "last_12"):
            # date_from / date_to ya seteados en onchange
           #  if self.date_from:
            #     domain += [("invoice_date", ">=", self.date_from)]
             #if self.date_to:
              #   domain += [("invoice_date", "<=", self.date_to)]
         #elif self.date_scope == "range":
          #   if self.date_from:
            #     domain += [("invoice_date", ">=", self.date_from)]
            # if self.date_to:
              #   domain += [("invoice_date", "<=", self.date_to)]

        return domain

    def action_print_report(self):
        self.ensure_one()
        domain = self._compute_domain()
        moves = self.env["account.move"].search(domain, order="invoice_date asc")

        data = {
            "partner_id": self.partner_id.id,
            "partner_display": f"{self.partner_id.document_number or ''} - {self.partner_id.name or ''}",
            "invoice_scope": self.invoice_scope,
            "date_scope": self.date_scope,
            "date_from": str(self.date_from) if self.date_from else False,
            "date_to": str(self.date_to) if self.date_to else False,
            "move_ids": moves.ids,
        }
        return self.env.ref("Insumar_Estadopagos.action_report_clientes").report_action(None, data=data)

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}
