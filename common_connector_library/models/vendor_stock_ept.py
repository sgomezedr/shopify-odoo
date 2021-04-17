# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import fields, models

class VendorStockEpt(models.Model):
    _name = 'vendor.stock.ept'
    _description = "Vendor Stock"

    vendor_product_id = fields.Many2one('product.product', string="Vendor List")
    vendor_id = fields.Many2one('res.partner', string="Vendor")
    vendor_stock = fields.Float()
