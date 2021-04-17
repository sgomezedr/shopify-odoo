# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields

class StockInventory(models.Model):
    _inherit = "stock.inventory"

    is_shopify_product_adjustment = fields.Boolean("Shopify Product Adjustment?", default=False)
