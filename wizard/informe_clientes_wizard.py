from odoo import models, fields, api

class InformeClientesWizard(models.TransientModel):
    _name = 'insumar.estadopagos.wizard'
    _description = 'Wizard para generar informe de estado de pagos'
