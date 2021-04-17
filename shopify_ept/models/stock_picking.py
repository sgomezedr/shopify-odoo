# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields

class StockPicking(models.Model):
    """Inhetit the model to add the fields in this model related to connector"""
    _inherit = "stock.picking"

    updated_in_shopify = fields.Boolean(default=False)
    is_shopify_delivery_order = fields.Boolean("Shopify Delivery Order", default=False)
    shopify_instance_id = fields.Many2one("shopify.instance.ept", "Instance")
    is_cancelled_in_shopify = fields.Boolean("Is Cancelled In Shopify ?", default=False, copy=False,
                                             help="Use this field to identify shipped in Odoo but cancelled in Shopify")
    is_manually_action_shopify_fulfillment = fields.Boolean("Is Manually Action Required ?", default=False, copy=False,
                                                            help="Those orders which we may fail update fulfillment status, we force set True and use will manually take necessary actions")
    shopify_fulfillment_id = fields.Char(string='Shopify Fulfillment Id')
