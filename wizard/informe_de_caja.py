# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class InformeDeCajaWizard(models.TransientModel):
    _name = 'informe_de_caja_wizard'
    _description = 'Informe de Caja Diario'

    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    user_id = fields.Many2one('res.users', string='Usuario', default=lambda self: self.env.user, readonly=True)
    categoria = fields.Selection([
        ('adm', 'Administración'),
        ('par', 'Par Vial'),
        ('nub', 'Ñuble'),
    ], string='Selección', required=True, default=lambda self: self._default_categoria())
    is_adm = fields.Boolean(string='Es Administrador', compute='_compute_is_adm', store=False)

    @api.model
    def _default_categoria(self):
        user = self.env.user
        # Equipos CRM: par=team_id 1, nub=team_id 5
        par_team = self.env['crm.team'].browse(1)
        nub_team = self.env['crm.team'].browse(5)
        if user and par_team and user in par_team.member_ids:
            return 'par'
        if user and nub_team and user in nub_team.member_ids:
            return 'nub'
        return 'adm'

    @api.depends('categoria')
    def _compute_is_adm(self):
        for rec in self:
            rec.is_adm = (rec.categoria == 'adm')

    # ----------------------------
    # Botón imprimir
    # ----------------------------
    def action_print(self):
        self.ensure_one()
        # Para 'adm' se permite cambiar la selección; si no cambia, no se imprime.
        if self.categoria == 'adm':
            raise UserError(_('Seleccione Par Vial o Ñuble antes de imprimir.'))

        data = self._build_report_data()
        return self.env.ref('Insumar_Estadopagos.report_caja').report_action(self, data=data)

    # ----------------------------
    # Construcción de datos
    # ----------------------------
    def _build_report_data(self):
        self.ensure_one()
        date = self.date
        seleccion = self.categoria

        # Map journals por selección
        journal_map = {
            'par': 12,   # Par Vial
            'nub': 14,   # Ñuble
        }
        journal_id = journal_map.get(seleccion)
        if not journal_id:
            raise UserError(_('No se encontró journal para la selección.'))

        # Payment Method Lines del journal seleccionado
        pml_ids = self.env['account.payment.method.line'].search([('journal_id', '=', journal_id)]).ids

        rows_by_invoice = {}

        # 1) Entradas (pagos) del día por journal (move_type=entry)
        entries = self.env['account.move'].search([
            ('move_type', '=', 'entry'),
            ('date', '=', date),
            ('journal_id', '=', journal_id),
            ('payment_id', '!=', False),
            ('state', '=', 'posted'),
        ])

        for entry in entries:
            payment = entry.payment_id
            if not payment:
                continue
            # Validar método de pago del journal seleccionado
            if not payment.payment_method_line_id or payment.payment_method_line_id.id not in pml_ids:
                continue

            method_name = (payment.payment_method_line_id.name or '').strip()
            # Factura por referencia: ref del asiento = name de la factura (out_invoice)
            invoice = self.env['account.move'].search([
                ('move_type', '=', 'out_invoice'),
                ('name', '=', entry.ref or ''),
            ], limit=1)
            if not invoice:
                # Si no se encontró la factura por ref, se omite.
                continue

            # Monto pagado para esta factura por este pago
            paid_amount = self._compute_paid_amount_for_invoice_with_payment(invoice, payment)
            if paid_amount <= 0.0:
                continue

            inv_row = rows_by_invoice.get(invoice.id)
            if not inv_row:
                inv_row = self._empty_row_from_invoice(invoice)

            # Columna según método
            col_key = self._method_to_column(method_name)
            inv_row[col_key] += paid_amount

            # Crédito = saldo
            inv_row['credito'] = max((invoice.amount_total or 0.0) - self._accum_paid(inv_row), 0.0)
            rows_by_invoice[invoice.id] = inv_row

        # 2) Facturas del día sin pagos asociados (o con parcial)
        unpaid_invoices = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('invoice_date', '=', date),
            ('state', '=', 'posted'),
        ])
        for inv in unpaid_invoices:
            inv_row = rows_by_invoice.get(inv.id)
            residual = max(inv.amount_residual or 0.0, 0.0)
            if inv_row:
                # Asegurar crédito = residual (si ya existía por pago parcial)
                inv_row['credito'] = max(residual, 0.0)
                rows_by_invoice[inv.id] = inv_row
            else:
                # Sin pagos asociados del día → todo a crédito
                inv_row = self._empty_row_from_invoice(inv)
                inv_row['credito'] = residual if residual > 0.0 else (inv.amount_total or 0.0)
                rows_by_invoice[inv.id] = inv_row

        # Ordenar facturas por fecha desc
        rows = list(rows_by_invoice.values())
        rows.sort(key=lambda r: r.get('date_invoice') or fields.Date.from_string('1970-01-01'), reverse=True)

        # 3) Notas de crédito del día al final (out_refund)
        refund_rows = []
        refunds = self.env['account.move'].search([
            ('move_type', '=', 'out_refund'),
            ('invoice_date', '=', date),
            ('state', '=', 'posted'),
        ])
        for rf in refunds:
            rf_row = self._empty_row_from_invoice(rf)
            # Transferencia/Depósito/NC en una sola columna
            rf_row['transferencia_deposito'] += abs(rf.amount_total or 0.0)
            refund_rows.append(rf_row)

        seleccion_name = 'Par Vial' if seleccion == 'par' else 'Ñuble'
        return {
            'date': date,
            'seleccion_name': seleccion_name,
            'rows': rows + refund_rows,
        }

    def _empty_row_from_invoice(self, inv):
        partner = inv.partner_id
        return {
            'sequence_prefix': inv.sequence_prefix or '',
            'sequence_number': inv.sequence_number or 0,
            'date_invoice': inv.invoice_date or inv.date or False,
            'amount_total': inv.amount_total or 0.0,
            'efectivo': 0.0,
            'debito_tarjeta': 0.0,
            'transferencia_deposito': 0.0,  # también agrupa NC (out_refund)
            'cheque': 0.0,
            'credito': 0.0,
            'document_number': getattr(partner, 'document_number', '') or '',
        }

    def _method_to_column(self, method_name):
        m = (method_name or '').strip().lower()
        if m == 'efectivo':
            return 'efectivo'
        if m in ('débito', 'debito', 'tarjeta de crédito', 'tarjeta de credito'):
            return 'debito_tarjeta'
        if m in ('transferencia', 'depósito', 'deposito'):
            return 'transferencia_deposito'
        if m == 'cheque':
            return 'cheque'
        # Por defecto agrupar en transferencia/deposito
        return 'transferencia_deposito'

    def _accum_paid(self, row):
        return (row.get('efectivo', 0.0)
                + row.get('debito_tarjeta', 0.0)
                + row.get('transferencia_deposito', 0.0)
                + row.get('cheque', 0.0))

    def _compute_paid_amount_for_invoice_with_payment(self, invoice, payment):
        """Suma la conciliación parcial entre líneas de la factura y del pago."""
        amount = 0.0
        inv_lines = invoice.line_ids.filtered(lambda l: l.account_id.internal_type in ('receivable', 'payable'))
        pay_lines = payment.move_id.line_ids.filtered(lambda l: l.account_id.internal_type in ('receivable', 'payable'))
        pay_lines_set = set(pay_lines.ids)

        for line in inv_lines:
            # matched_debit_ids y matched_credit_ids apuntan a account.partial.reconcile
            for pr in (line.matched_debit_ids | line.matched_credit_ids):
                # counterpart line (del pago) según lado
                c_line = pr.debit_move_id if pr.credit_move_id.id == line.id else pr.credit_move_id
                if c_line.id in pay_lines_set:
                    amount += pr.amount
        return amount
