from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

class InformeClientesWizard(models.TransientModel):
    _name = 'insumar.estadopagos.wizard'
    _description = 'Wizard para generar informe de estado de pagos'

    partner_id = fields.Many2one(
        'res.partner', 
        string='Cliente',
        domain=[('customer_rank', '>', 0)],
        required=True
    )

    sucursal = fields.Selection([
        ('1', 'Par Vial'),
        ('5', 'Ñuble')
    ], string='Sucursal', required=True)

       
    fecha_corte = fields.Date(
        string='Fecha de Corte para Vencimientos',
        required=True,
        default=fields.Date.context_today
    )

        
    rango_fechas = fields.Selection([
        ('actual', 'Año en Curso'),
        ('anterior', 'Últimos 12 Meses'),
        ('personalizado', 'Rango Personalizado')
    ], string='Rango de Fechas', default='actual', required=True)
    
    fecha_desde = fields.Date(string='Desde')

    fecha_hasta = fields.Date(string='Hasta')

    @api.onchange('rango_fechas')
    def _onchange_rango_fechas(self):
        today = fields.Date.context_today(self)
        if self.rango_fechas == 'actual':
            self.fecha_desde = datetime(today.year, 1, 1).date()
            self.fecha_hasta = today
        elif self.rango_fechas == 'anterior':
            self.fecha_desde = today - relativedelta(months=12)
            self.fecha_hasta = today
        else:
            self.fecha_desde = False
            self.fecha_hasta = False

    def generar_reporte_cliente(self):
        data = {          
            'partner_name': self.partner_id.name,
            'sucursal': self.sucursal,
            'sucursal_nombre': dict(self._fields['sucursal'].selection).get(self.sucursal),
            'fecha_desde': self.fecha_desde.strftime('%d/%m/%Y'), 
            'fecha_hasta': self.fecha_hasta.strftime('%d/%m/%Y'), 
        }
        
        facturas_bruto = self.env['account.move'].search([
            ('payment_state', 'in', ['not_paid', 'partial']),
            ('move_type', 'in', ['out_invoice','out_refund']),
            ('state', '=', 'posted'),
            ('partner_id', '=', self.partner_id.id)
        ])

        # Crear lista de IDs filtrados
        ids_filtrados = []
        for factura in facturas_bruto:
            if (factura.invoice_date and 
                self.fecha_desde <= factura.invoice_date <= self.fecha_hasta):
                ids_filtrados.append(factura.id)

        facturas = self.env['account.move'].browse(ids_filtrados)
        
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
        
        return self.env.ref('Insumar_Estadopagos.action_report_clientes').report_action(self, data=data)


class InformeClientesWizard2(models.TransientModel):
    _name = 'informe.clientes.wizard'
    _description = 'Wizard para generar informe de estado de pagos'
