from odoo import models, fields, api
from datetime import datetime, timedelta
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
    
    tipo_reporte = fields.Selection([
        ('pendientes', 'Facturas Pendientes'),
        ('todas', 'Todas las Facturas')
    ], string='Tipo de Reporte', default='pendientes', required=True)
    
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
    
    def action_print_report(self):
        data = {
            'partner_id': self.partner_id.id,
            'tipo_reporte': self.tipo_reporte,
            'rango_fechas': self.rango_fechas,
            'fecha_desde': self.fecha_desde,
            'fecha_hasta': self.fecha_hasta,
        }
        return self.env.ref('Insumar_Estadopagos.action_report_clientes').report_action(self, data=data)