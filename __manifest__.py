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
         'report/report_payment.xml',
         "wizard/deudores_views.xml",
         "data/report_action.xml",
         "report/deudores_templates.xml"
],
'depends': ['base' , 'contacts' , 'account', 'parches_insumar']
}
