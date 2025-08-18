# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{ 'name': 'Insumar_EstadoPagos',
'summary': "Reporte de estado de pagos",
'author': "Mauricio Gah",
'license': "AGPL-3",
'application': "True",
'version': "2.0",
'data': ['security/groups.xml',
         'security/ir.model.access.csv',
         'wizard/estado_wizard.xml',
        'wizard/deudores.xml',
        'report/report_deudores.xml',
        'report/report_payment.xml'

],
'depends': ['base' , 'contacts' , 'account', 'parches_insumar']
}
