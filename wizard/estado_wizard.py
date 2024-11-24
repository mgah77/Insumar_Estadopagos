from odoo import models, fields, api
from datetime import date

class EstadoWizard(models.TransientModel):
    _name = "wizard.estadopago"
    _description = "Estado de pago de clientes"

    cliente = fields.Many2one('res.partner',string='Cliente',domain="[('type', '!=', 'private'), ('is_company', '=', True), ('type','=','contact'), ('is_customer','=',True)]")
    fac_vencido = fields.Integer(string="FacturasVencidas", compute='_compute_cantidad_vencida')
    vencido = fields.Float(string="Cantidad Vencida", compute='_compute_cantidad_vencida', digits=(16, 0))
    pre_fac_vencido = fields.Integer(string="Facturas por vencer", compute='_compute_cantidad_vencida')
    pre_vencido = fields.Float(string="Cantidad por vencer", compute='_compute_cantidad_vencida', digits=(16, 0))
    totales = fields.Float(string="Total Deuda", compute='_compute_cantidad_vencida', digits=(16, 0))
    facturas_out = fields.One2many('account.move', compute='_compute_cantidad_vencida', string="Facturas")
    facturas_in = fields.One2many('account.move', compute='_compute_cantidad_vencida', string="Facturas")

    
    @api.depends('cliente')
    def _compute_cantidad_vencida(self):
        Invoice = self.env['account.move']
        for record in self:
            if record.cliente:
                fac_vencido = Invoice.search_count([('partner_id', '=', record.cliente.id),('move_type', '=', 'out_invoice'),('payment_state', '=', 'not_paid'),('invoice_date_due', '<', fields.Date.today())])
                record.fac_vencido = fac_vencido
                vencido = Invoice.search([('partner_id', '=', record.cliente.id),('move_type', '=', 'out_invoice'),('payment_state', '=', 'not_paid'),('invoice_date_due', '<', fields.Date.today())])
                total_vencido = sum(factura.amount_residual_signed for factura in vencido)
                record.vencido = total_vencido
                pre_fac_vencido = Invoice.search_count([('partner_id', '=', record.cliente.id),('move_type', '=', 'out_invoice'),('payment_state', '=', 'not_paid'),('invoice_date_due', '>=', fields.Date.today())])
                record.pre_fac_vencido = pre_fac_vencido
                pre_vencido = Invoice.search([('partner_id', '=', record.cliente.id),('move_type', '=', 'out_invoice'),('payment_state', '=', 'not_paid'),('invoice_date_due', '>=', fields.Date.today())])
                total_pre_vencido = sum(factura.amount_residual_signed for factura in pre_vencido)
                record.pre_vencido = total_pre_vencido
                pre_total = Invoice.search([('partner_id', '=', record.cliente.id),('move_type', '=', 'out_invoice'),('payment_state', '=', 'not_paid')])
                totales = sum(factura.amount_residual_signed for factura in pre_total)
                record.totales = totales                
                record.facturas_out = Invoice.search([('partner_id', '=', record.cliente.id), ('move_type', '=', 'out_invoice'), ('payment_state', '=', 'not_paid'),('invoice_date_due', '<', fields.Date.today())])
                record.facturas_in = Invoice.search([('partner_id', '=', record.cliente.id), ('move_type', '=', 'out_invoice'), ('payment_state', '=', 'not_paid'),('invoice_date_due', '>=', fields.Date.today())])
            else:
                record.fac_vencido = 0
                record.vencido = 0
                record.pre_fac_vencido = 0
                record.pre_vencido = 0
                record.totales = 0
                record.facturas_out = [(5, 0, 0)]  # Limpiar las relaciones
                record.facturas_in = [(5, 0, 0)]
        return

    def action_print_report(self):
        report = self.env.ref('Insumar_Estadopagos.action_payment_report')  # Reemplaza con el nombre correcto de tu informe
        return report.with_context(active_ids=self.ids, active_model=self._name).report_action(self)
