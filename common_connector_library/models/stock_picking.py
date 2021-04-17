# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _action_done(self):
        """
        Added comment by Udit
        create and paid invoice on the basis of auto invoice work flow
        when invoicing policy is 'delivery'.
        """
        result = super(StockPicking, self)._action_done()
        for picking in self:
            if picking.sale_id.invoice_status == 'invoiced':
                continue

            order = picking.sale_id
            work_flow_process_record = order and order.auto_workflow_process_id
            delivery_lines = picking.move_line_ids.filtered(lambda l: l.product_id.invoice_policy == 'delivery')

            if work_flow_process_record and delivery_lines and work_flow_process_record.create_invoice and \
                    picking.picking_type_id.code == 'outgoing':
                order.validate_and_paid_invoices_ept(work_flow_process_record)
        return result

    def send_to_shipper(self):
        """
        usage: If auto_processed_orders_ept = True passed in Context then we can not call send shipment from carrier
        This change is used in case of Import Shipped Orders for all connectors.
        @author: Keyur Kanani
        """
        context = dict(self._context)
        if context.get('auto_processed_orders_ept', False):
            return True
        return super(StockPicking, self).send_to_shipper()
