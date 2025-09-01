# -*- coding: utf-8 -*-
from datetime import date as pydate
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
        par_team = self.env['crm.team'].browse(1)  # Par Vial
        nub_team = self.env['crm.team'].browse(5)  # Ñuble
        if user and par_team and user in par_team.member_ids:
            return 'par'
        if user and nub_team and user in nub_team.member_ids:
            return 'nub'
        return 'adm'

    @api.depends('user_id')
    def _compute_is_adm(self):
        par_team = self.env['crm.team'].browse(1)
        nub_team = self.env['crm.team'].browse(5)
        for rec in self:
            user = rec.user_id or self.env.user
            is_par = bool(par_team) and (user in par_team.member_ids)
            is_nub = bool(nub_team) and (user in nub_team.member_ids)
            rec.is_adm = not (is_par or is_nub)

    def action_print(self):
        self.ensure_one()
        if self.categoria == 'adm':
            raise UserError(_('Seleccione Par Vial o Ñuble antes de imprimir.'))
        data = self._build_report_data()
        return self.env.ref('Insumar_Estadopagos.report_caja').report_action(self, data=data)

    def _build_report_data(self):
        self.ensure_one()
        date_val = self.date
        seleccion = self.categoria

        # Journals por selección (cajas/bancos por sucursal)
        journal_map = {'par': 12, 'nub': 14}
        journal_id = journal_map.get(seleccion)
        if not journal_id:
            raise UserError(_('No se encontró journal para la selección.'))

        # Teams por selección (ventas por sucursal)
        team_map = {'par': 1, 'nub': 5}
        selected_team_id = team_map.get(seleccion)

        # Payment Method Lines del journal
        pml_ids = self.env['account.payment.method.line'].search([('journal_id', '=', journal_id)]).ids

        rows_by_invoice = {}

        # 1) Asientos de pago del día (entry) del journal seleccionado
        entries = self.env['account.move'].search([
            ('move_type', '=', 'entry'),
            ('date', '=', date_val),
            ('journal_id', '=', journal_id),
            ('payment_id', '!=', False),
            ('state', '=', 'posted'),
        ])

        for entry in entries:
            payment = entry.payment_id
            if not payment:
                continue
            if not payment.payment_method_line_id or payment.payment_method_line_id.id not in pml_ids:
                continue

            method_name = (payment.payment_method_line_id.name or '').strip()

            # Factura cuyo name coincide con ref del asiento de pago
            invoice = self.env['account.move'].search([
                ('move_type', '=', 'out_invoice'),
                ('name', '=', entry.ref or ''),
            ], limit=1)
            if not invoice:
                continue

            # FILTRO por team (sucursal) en la factura
            if 'team_id' in invoice._fields and selected_team_id and (invoice.team_id.id != selected_team_id):
                continue

            # Monto tomado directamente de account.payment (sin decimales en PDF)
            paid_amount = abs(payment.amount or 0.0)
            if paid_amount <= 0.0:
                continue

            inv_row = rows_by_invoice.get(invoice.id) or self._empty_row_from_invoice(invoice)

            # Sumar en columna por método
            col_key = self._method_to_column(method_name)
            inv_row[col_key] += paid_amount

            # Crédito = saldo
            inv_row['credito'] = max((invoice.amount_total or 0.0) - self._accum_paid(inv_row), 0.0)
            rows_by_invoice[invoice.id] = inv_row

        # 2) Facturas del día SIN pagos del día (o con parcial) → crédito/residual
        unpaid_domain = [
            ('move_type', '=', 'out_invoice'),
            ('invoice_date', '=', date_val),
            ('state', '=', 'posted'),
        ]
        if selected_team_id and 'team_id' in self.env['account.move']._fields:
            unpaid_domain.append(('team_id', '=', selected_team_id))

        unpaid_invoices = self.env['account.move'].search(unpaid_domain)
        for inv in unpaid_invoices:
            inv_row = rows_by_invoice.get(inv.id)
            residual = max(inv.amount_residual or 0.0, 0.0)
            if inv_row:
                inv_row['credito'] = max(residual, 0.0)
            else:
                inv_row = self._empty_row_from_invoice(inv)
                inv_row['credito'] = residual if residual > 0.0 else (inv.amount_total or 0.0)
            rows_by_invoice[inv.id] = inv_row

        # Orden: fecha desc
        rows = list(rows_by_invoice.values())
        rows.sort(key=lambda r: r.get('date_invoice') or pydate(1970, 1, 1), reverse=True)

        # 3) Notas de crédito del día (al final), filtradas por team también
        refund_domain = [
            ('move_type', '=', 'out_refund'),
            ('invoice_date', '=', date_val),
            ('state', '=', 'posted'),
        ]
        if selected_team_id and 'team_id' in self.env['account.move']._fields:
            refund_domain.append(('team_id', '=', selected_team_id))

        refund_rows = []
        refunds = self.env['account.move'].search(refund_domain)
        for rf in refunds:
            rf_row = self._empty_row_from_invoice(rf)
            # NC deben ir NEGATIVAS en la columna agrupada
            rf_row['transferencia_deposito'] += -abs(rf.amount_total or 0.0)
            refund_rows.append(rf_row)

        # Pasamos también la clave técnica de selección para el template (Ñ)
        return {
            'date': date_val,
            'seleccion': seleccion,  # 'par' o 'nub'
            'seleccion_name': 'Par Vial' if seleccion == 'par' else 'Ñuble',
            'rows': rows + refund_rows,
        }

    # Helpers
    def _empty_row_from_invoice(self, inv):
        partner = inv.partner_id
        return {
            'sequence_prefix': getattr(inv, 'sequence_prefix', '') or '',
            'sequence_number': getattr(inv, 'sequence_number', 0) or 0,
            'date_invoice': inv.invoice_date or inv.date or False,
            'amount_total': inv.amount_total or 0.0,
            'efectivo': 0.0,
            'debito_tarjeta': 0.0,
            'transferencia_deposito': 0.0,
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
        return 'transferencia_deposito'

    def _accum_paid(self, row):
        return (
            row.get('efectivo', 0.0)
            + row.get('debito_tarjeta', 0.0)
            + row.get('transferencia_deposito', 0.0)
            + row.get('cheque', 0.0)
        )
