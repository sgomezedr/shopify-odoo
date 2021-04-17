# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def create_sale_order_line_ept(self, vals):
        """
        Pass dictionary
        vals = {'order_id':order_id, 'product_id':product_id, 'company_id':company_id, 'description':product_name,
        'order_qty':qty, 'price_unit':price, 'discount':discount}
        Required data in dictionary :- order_id, name, product_id.
        Migration done by twinkalc August 2020
        """
        sale_order_line = self.env['sale.order.line']
        order_line = {
            'order_id':vals.get('order_id', False),
            'product_id':vals.get('product_id', False),
            'company_id':vals.get('company_id', False),
            'name':vals.get('description', ''),
            'product_uom':vals.get('product_uom')
        }

        new_order_line = sale_order_line.new(order_line)
        new_order_line.product_id_change()
        order_line = sale_order_line._convert_to_write({name:new_order_line[name] for name in new_order_line._cache})

        order_line.update({
            'order_id':vals.get('order_id', False),
            'product_uom_qty':vals.get('order_qty', 0.0),
            'price_unit':vals.get('price_unit', 0.0),
            'discount':vals.get('discount', 0.0),
            'state':'draft',
        })
        return order_line
