# wizards/reporte_estado_pago.py
from odoo import models, fields
from datetime import date

class WizardEstadoPagoSucursal(models.TransientModel):
    _name = 'estado.pago.sucursal.wizard'
    _description = 'Wizard Estado Pago por Sucursal'

    sucursal = fields.Selection([
        ('1', 'Par Vial'),
        ('5', 'Ñuble'),
    ], string='Sucursal', required=True)

    def imprimir_reporte(self):
        team_id = int(self.sucursal)
        today = date.today()
        facturas = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', '!=', 'paid'),
            ('invoice_date_due', '>', today),
            ('team_id', '=', team_id),
        ])
        grouped = {}
        for factura in facturas:
            partner = factura.partner_id
            key = (partner.document_number or '', partner.name or '')
            grouped.setdefault(key, []).append(factura)

        data = {
            'sucursal': dict(self._fields['sucursal'].selection).get(self.sucursal),
            'grouped': sorted(grouped.items(), key=lambda x: x[0][0]),  # por document_number asc
        }
        return self.env.ref('Insumar_Estadopagos.report_estado_pago_pdf').report_action(self, data=data)

