# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models

class AccountMove(models.Model):
    _inherit = 'account.move'

    def prepare_payment_dict(self, work_flow_process_record):
        """
        Added By Twinkalc 29 july 2020
        This method will prepare payment dictionary.
        :param work_flow_process_record: Sale Workflow object.
        Migration done by twinkalc August 2020
        """
        return {
            'journal_id': work_flow_process_record.journal_id.id,
            'ref': self.payment_reference,
            'currency_id': self.currency_id.id,
            'payment_type': 'inbound',
            'date': self.date,
            'partner_id': self.commercial_partner_id.id,
            'amount': self.amount_residual,
            'payment_method_id': work_flow_process_record.inbound_payment_method_id.id,
            'partner_type': 'customer'
        }
