from odoo import models, fields, api

class ReportClientes(models.AbstractModel):
    _name = 'report.insumar_estadopagos.report_clientes'
    _description = 'Reporte de Estado de Pagos'

    def _get_report_values(self, docids, data=None):
        partner_id = data.get('partner_id')
        tipo_reporte = data.get('tipo_reporte')
        rango_fechas = data.get('rango_fechas')
        fecha_desde = data.get('fecha_desde')
        fecha_hasta = data.get('fecha_hasta')

        domain = [('partner_id', '=', partner_id), ('move_type', 'in', ['out_invoice', 'out_refund'])]
        
        if tipo_reporte == 'pendientes':
            domain.append(('payment_state', '!=', 'paid'))
        
        if rango_fechas == 'actual':
            domain.append(('invoice_date', '>=', fields.Date.today().replace(month=1, day=1)))
            domain.append(('invoice_date', '<=', fields.Date.today()))
        elif rango_fechas == 'anterior':
            domain.append(('invoice_date', '>=', fields.Date.today() - relativedelta(months=12)))
            domain.append(('invoice_date', '<=', fields.Date.today()))
        elif rango_fechas == 'personalizado' and fecha_desde and fecha_hasta:
            domain.append(('invoice_date', '>=', fecha_desde))
            domain.append(('invoice_date', '<=', fecha_hasta))
        
        invoices = self.env['account.move'].search(domain, order='invoice_date asc')
        
        partner = self.env['res.partner'].browse(partner_id)
        
        return {
            'doc_ids': invoices.ids,
            'doc_model': 'account.move',
            'docs': invoices,
            'partner': partner,
            'tipo_reporte': 'Pendientes' if tipo_reporte == 'pendientes' else 'Todas',
            'rango_fechas': self._get_rango_fechas_text(rango_fechas, fecha_desde, fecha_hasta),
        }
    
    def _get_rango_fechas_text(self, rango_fechas, fecha_desde, fecha_hasta):
        if rango_fechas == 'actual':
            return 'Año en Curso'
        elif rango_fechas == 'anterior':
            return 'Últimos 12 Meses'
        elif rango_fechas == 'personalizado':
            return f"Desde {fecha_desde} hasta {fecha_hasta}"
        return ''