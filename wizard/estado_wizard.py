from odoo import models, fields, api
from datetime import date

class EstadoWizard(models.TransientModel):
    _name = "wizard.estadopago"
    _description = "Estado de pago de clientes"

    cliente = fields.Many2one('res.partner', string='Cliente',domain=[('is_company','=',True)])
    fac_vencida = fields.Integer(string = 'Facturas Vencidas')