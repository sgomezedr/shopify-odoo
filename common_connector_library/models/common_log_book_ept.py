# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api

class CommonLogBookEpt(models.Model):
    _name = "common.log.book.ept"
    _inherit = ["mail.thread"]
    _order = 'id desc'
    _description = "Common log book for all connector"

    name = fields.Char(readonly=True)
    type = fields.Selection([('import', 'Import'), ('export', 'Export')], string="Operation")
    module = fields.Selection([('amazon_ept', 'Amazon Connector'),
                               ('woocommerce_ept', 'Woocommerce Connector'),
                               ('shopify_ept', 'Shopify Connector'),
                               ('magento_ept', 'Magento Connector'),
                               ('bol_ept', 'Bol Connector'),
                               ('ebay_ept', 'Ebay Connector'),
                               ('amz_vendor_central', 'Amazon Vendor Central')])
    active = fields.Boolean(default=True)
    log_lines = fields.One2many('common.log.lines.ept', 'log_book_id')
    message = fields.Text()
    model_id = fields.Many2one("ir.model", help="Model Id", string="Model")
    res_id = fields.Integer(string="Record ID", help="Process record id")
    attachment_id = fields.Many2one('ir.attachment', string="Attachment")

    @api.model
    def create(self, vals):
        """
        This method is create for sequence wise name.
        :param vals: values
        :return:super
        """
        seq = self.env['ir.sequence'].next_by_code('common.log.book.ept') or '/'
        vals['name'] = seq
        return super(CommonLogBookEpt, self).create(vals)
