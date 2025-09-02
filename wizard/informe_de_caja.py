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
        # Ahora 'adm' sí imprime (con su propia lógica)
        data = self._build_report_data()
        return self.env.ref('Insumar_Estadopagos.report_caja').report_action(self, data=data)

    def _build_report_data(self):
        self.ensure_one()
        date_val = self.date
        seleccion = self.categoria

        # Diarios por selección
        if seleccion == 'par':
            journal_ids = [12]
        elif seleccion == 'nub':
            journal_ids = [14]
        else:  # adm: ambos diarios
            journal_ids = [12, 14]

        # Teams de sucursales (para validar vendedor)
        team_par = self.env['crm.team'].browse(1)
        team_nub = self.env['crm.team'].browse(5)

        # Función: ¿el vendedor (invoice_user_id) calza con la selección?
        def seller_matches_selection(inv):
            if 'invoice_user_id' not in inv._fields:
                return False
            seller = inv.invoice_user_id
            in_par = bool(team_par) and seller and (seller in team_par.member_ids)
            in_nub = bool(team_nub) and seller and (seller in team_nub.member_ids)
            if seleccion == 'par':
                return in_par
            if seleccion == 'nub':
                return in_nub
            # adm: no debe pertenecer a ninguno de los 2 teams; si no hay seller, lo consideramos "adm"
            return not in_par and not in_nub

        # Payment Method Lines de los diarios seleccionados
        pml_ids = self.env['account.payment.method.line'].search([('journal_id', 'in', journal_ids)]).ids

        rows_by_invoice = {}

        # 1) Asientos de pago (entry) del día para los diarios seleccionados
        entries = self.env['account.move'].search([
            ('move_type', '=', 'entry'),
            ('date', '=', date_val),
            ('journal_id', 'in', journal_ids),
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

            # Vincular factura: name == ref del asiento
            invoice = self.env['account.move'].search([
                ('move_type', '=', 'out_invoice'),
                ('name', '=', entry.ref or ''),
            ], limit=1)
            if not invoice:
                continue

            # Nuevo criterio: vendedor debe calzar con la selección
            if not seller_matches_selection(invoice):
                continue

            # Monto del pago (directo desde account.payment)
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

        # 2) Facturas del día sin pago / parcial
        unpaid_invoices = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('invoice_date', '=', date_val),
            ('state', '=', 'posted'),
        ])
        for inv in unpaid_invoices:
            if not seller_matches_selection(inv):
                continue
            inv_row = rows_by_invoice.get(inv.id)
            residual = max(inv.amount_residual or 0.0, 0.0)
            if inv_row:
                inv_row['credito'] = max(residual, 0.0)
            else:
                inv_row = self._empty_row_from_invoice(inv)
                inv_row['credito'] = residual if residual > 0.0 else (inv.amount_total or 0.0)
            rows_by_invoice[inv.id] = inv_row

        # Ordenar facturas por fecha desc
        invoice_rows = list(rows_by_invoice.values())
        invoice_rows.sort(key=lambda r: r.get('date_invoice') or pydate(1970, 1, 1), reverse=True)

        # 3) Notas de crédito del día (negativas)
        refunds = self.env['account.move'].search([
            ('move_type', '=', 'out_refund'),
            ('invoice_date', '=', date_val),
            ('state', '=', 'posted'),
        ])
        refund_rows = []
        for rf in refunds:
            if not seller_matches_selection(rf):
                continue
            rf_row = self._empty_row_from_invoice(rf)
            rf_row['amount_total'] = -abs(rf.amount_total or 0.0)
            rf_row['transferencia_deposito'] += -abs(rf.amount_total or 0.0)
            refund_rows.append(rf_row)

        # Subtotales / Totales
        inv_sub = self._compute_sums(invoice_rows)
        ref_sub = self._compute_sums(refund_rows)
        keys = ['amount_total', 'efectivo', 'debito_tarjeta', 'transferencia_deposito', 'cheque', 'credito']
        grand = {k: (inv_sub.get(k, 0.0) + ref_sub.get(k, 0.0)) for k in keys}

        # Título de selección
        if seleccion == 'par':
            sel_name = 'Par Vial'
        elif seleccion == 'nub':
            sel_name = 'Ñuble'
        else:
            sel_name = 'Administración'

        return {
            'date': date_val,
            'seleccion_name': sel_name,
            'invoice_rows': invoice_rows,
            'refund_rows': refund_rows,
            'inv_subtotals': inv_sub,
            'ref_subtotals': ref_sub,
            'grand_totals': grand,
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

    def _compute_sums(self, rows):
        keys = ['amount_total', 'efectivo', 'debito_tarjeta', 'transferencia_deposito', 'cheque', 'credito']
        totals = {k: 0.0 for k in keys}
        for r in rows:
            for k in keys:
                totals[k] += float(r.get(k) or 0.0)
        return totals
