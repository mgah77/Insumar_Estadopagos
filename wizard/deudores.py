# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import date

class InsumarDeudoresWizard(models.TransientModel):
    _name = "insumar.deudores.wizard"
    _description = "Wizard de Deudores por Sucursal"

    team_selection = fields.Selection(
        selection=[
            ("5", "Ñuble"),
            ("1", "Par Vial"),
        ],
        string="Sucursal",
        required=True,
        default="5",
        help="Seleccione la sucursal para filtrar por team_id.",
    )

    def action_print_report(self):
        self.ensure_one()
        team_id = int(self.team_selection)
        team_name = "Ñuble" if team_id == 5 else "Par Vial"
        data = {"team_id": team_id, "team_name": team_name}
        # Importante: pasar self (docids) en lugar de None
        return self.env.ref("Insumar_Estadopagos.report_deudores").report_action(self, data=data)

