# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
""" Mixin class for deleting unused data queue from database."""
from odoo import models

class DataQueueMixinEpt(models.AbstractModel):
    """ Mixin class for deleting unused data queue from database."""
    _name = 'data.queue.mixin.ept'
    _description = 'Data Queue Mixin'

    def delete_data_queue_ept(self, queue_detail=[], is_delete_queue=False):
        """
        Usage: Method for deleting unused data queues from connectors after 7 days.
        @author: Dipak Gogiya
        :param is_delete_queue: Delete all data form queue table.
        :param queue_detail: ['sample_data_queue_ept1','sample_data_queue_ept2']
        :return: True

        Changes done by twinkalc on 3rd FEB 2021 to delete log book data and process
        the unique list to delete datas from the database.
        """
        if queue_detail:
            try:
                queue_detail += ['common_log_book_ept']
                queue_detail = list(set(queue_detail))
                for tbl_name in queue_detail:
                    if is_delete_queue:
                        self._cr.execute("""delete from %s """ % str(tbl_name))
                        continue
                    self._cr.execute(
                        """delete from %s where cast(create_date as Date) <= current_date - %d""" % (str(tbl_name), 7))
            except Exception as error:
                return error
        return True
