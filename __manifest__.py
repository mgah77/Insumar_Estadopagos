# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{ 'name': 'Insumar_taller',
'summary': "OT y certificaciones",
'author': "Mauricio Gah",
'license': "AGPL-3",
'application': "True",
'version': "2.0",
'data': ['security/groups.xml',
         'security/ir.model.access.csv',
         'views/menu.xml',
         'views/maestro.xml',
         'views/product_template.xml',
         'views/orden_trabajo.xml',
         'views/planificacion.xml',
         'views/maniobras.xml'
],
'depends': ['base' , 'contacts' , 'stock' , 'product', 'parches_insumar']
}
