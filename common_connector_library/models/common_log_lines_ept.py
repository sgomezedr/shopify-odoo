# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api

class CommonLogLineEpt(models.Model):
    _name = "common.log.lines.ept"
    _description = "Common log line for all connector"

    product_id = fields.Many2one('product.product', 'Product')
    order_ref = fields.Char('Order Reference')
    default_code = fields.Char('SKU')
    log_book_id = fields.Many2one('common.log.book.ept', ondelete="cascade")
    message = fields.Text()
    model_id = fields.Many2one("ir.model", string="Model")
    res_id = fields.Integer("Record ID")

    @api.model
    def get_model_id(self, model_name):
        """
        This method is used to get model id
        :param model_name: model_name
        :return: model_id
        """
        model = self.env['ir.model'].search([('model', '=', model_name)])
        if model:
            return model.id
        return False
