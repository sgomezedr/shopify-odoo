# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _

class AccountMove(models.Model):
    """
    Inherite the account move here to return refund action.
    """
    _inherit = "account.move"

    is_refund_in_shopify = fields.Boolean("Refund In Shopify", default=False,
                                          help="True: Refunded credit note amount in shopify store.\n False: "
                                               "Remaining to refund in Shopify Store")
    shopify_instance_id = fields.Many2one("shopify.instance.ept", "Instances")

    def action_open_refund_wizard(self):
        """This method used to open a wizard for Refund order in Shopify.
            @param : self
            @return: action
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 20/11/2019.
            Task Id : 157911
        """
        form_view = self.env.ref('shopify_ept.view_shopify_refund_wizard')
        context = dict(self._context)
        context.update({'active_model':'account.invoice', 'active_id':self.id, 'active_ids':self.ids})

        return {
            'name':_('Refund order In Shopify'),
            'type':'ir.actions.act_window',
            'view_type':'form',
            'view_mode':'form',
            'res_model':'shopify.cancel.refund.order.wizard',
            'views':[(form_view.id, 'form')],
            'view_id':form_view.id,
            'target':'new',
            'context':context
        }
