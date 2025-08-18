from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date

class InformeClientesWizard(models.TransientModel):
    _name = 'insumar.estadopagos.wizard'
    _description = 'Wizard para generar informe de estado de pagos'


    sucursal = fields.Selection([
        ('1', 'Par Vial'),
        ('5', 'Ñuble')
    ], string='Sucursal', required=True)

       
    fecha_corte = fields.Date(
        string='Fecha de Corte para Vencimientos',
        required=True,
        default=fields.Date.context_today
    )


    def generar_reporte(self):
        data = {
            'sucursal': self.sucursal,
            'sucursal_nombre': dict(self._fields['sucursal'].selection).get(self.sucursal),
            'fecha_actual': date.today().strftime('%d/%m/%Y'),
            'fecha_corte': self.fecha_corte.strftime('%d/%m/%Y'), 
        }
        
        facturas = self.env['account.move'].search([
            ('payment_state', 'in', ['not_paid', 'partial']),
            ('team_id', '=', int(self.sucursal)),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date_due', '<=', self.fecha_corte),
        ], order='partner_id')
        
        clientes = {}
        for factura in facturas:
            partner = factura.partner_id
            if partner.id not in clientes:
                clientes[partner.id] = {
                    'document_number': partner.document_number or 'Sin RUT',
                    'name': partner.name,
                    'facturas': []
                }
            
            abono = factura.amount_total - factura.amount_residual
            clientes[partner.id]['facturas'].append({
                'name': factura.sii_document_number,
                'invoice_date': factura.invoice_date.strftime('%d/%m/%Y') if factura.invoice_date else '',
                'invoice_date_due': factura.invoice_date_due.strftime('%d/%m/%Y') if factura.invoice_date_due else '',
                'amount_total': factura.amount_total,
                'abono': abono,
                'amount_residual': factura.amount_residual,
            })
        
        # Ordenar clientes por document_number
        clientes_ordenados = sorted(clientes.values(), key=lambda x: x['document_number'])
        data['clientes'] = clientes_ordenados
        
        return self.env.ref('Insumar_Estadopagos.report_deudores').report_action(self, data=data)


class InformeClientesWizard2(models.TransientModel):
    _name = 'informe.clientes.wizard'
    _description = 'Wizard para generar informe de estado de pagos'
