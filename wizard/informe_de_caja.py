# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

CAT_SELECTION = [
    ("adm", "Administración"),
    ("par", "Par Vial"),
    ("nub", "Ñuble"),
]

TEAM_PAR_ID = 1
TEAM_NUB_ID = 5

JOURNAL_PAR_ID = 12
JOURNAL_NUB_ID = 14


class InformeDeCajaWizard(models.TransientModel):
    _name = "informe.de.caja.wizard"
    _description = "Wizard Informe de caja diario"

    fecha = fields.Date(
        string="Fecha",
        required=True,
        default=lambda self: fields.Date.context_today(self),
    )
    usuario_id = fields.Many2one(
        "res.users",
        string="Usuario",
        default=lambda self: self.env.user,
        readonly=True,
    )
    categoria = fields.Selection(
        CAT_SELECTION,
        string="Categoría",
        required=True,
        default=lambda self: self._default_categoria(),
    )

    def _default_categoria(self):
        """Determina la categoría por equipo CRM:
           - par si pertenece a team_id=1
           - nub si pertenece a team_id=5
           - adm en cualquier otro caso
        """
        user = self.env.user
        # Intento 1: equipo por relación directa
        team = getattr(user, "sale_team_id", False)
        team_ids = []
        if team:
            team_ids.append(team.id)

        # Intento 2: pertenencia como miembro (si aplica)
        # crm.team tiene member_ids (res.users)
        user_teams = self.env["crm.team"].search([("member_ids", "in", [user.id])])
        team_ids += [t.id for t in user_teams]

        # Evaluación
        if TEAM_PAR_ID in team_ids:
            return "par"
        if TEAM_NUB_ID in team_ids:
            return "nub"
        return "adm"

    def action_print(self):
        self.ensure_one()
        if self.categoria == "adm":
            raise UserError(_("La categoría Administración aún no está implementada."))

        return self.env.ref("Insumar_Estadopagos.report_caja").report_action(self)
