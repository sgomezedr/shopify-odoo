# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields

class CommonProductBrandEpt(models.Model):
    _name = 'common.product.brand.ept'
    _description = 'Common Product Brand'

    name = fields.Char('Brand Name', required="True")
    description = fields.Text(translate=True)
    partner_id = fields.Many2one('res.partner', string='Partner', help='Select a partner for this brand if it exists.',
                                 ondelete='restrict')
    logo = fields.Binary('Logo File')
