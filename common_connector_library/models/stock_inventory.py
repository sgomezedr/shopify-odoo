# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
import time
from odoo import models, api


class StockInventory(models.Model):
    _inherit = "stock.inventory"

    @api.model
    def create_stock_inventory_ept(self, products, location_id, auto_validate=False):
        """
        @author: Udit
        This method will create inventory based on products and location passed to this method.
        :param products: List of dictionary as [{'product_id':product_obj,'product_qty':qty,'location_id':location_id}]
        :param location_id: Location for which need an inventory adjustment.
        :param auto_validate: If also need to validate inventory then pass "True" otherwise "False".
        Migration done by twinkalc August 2020
        """
        if products:
            inventories = self
            while products:
                inventory_lines = products[:100]
                inventory_products = [line['product_id'].id for line in inventory_lines]

                inventory_vals = self.prepare_inventory_vals_ept(location_id, inventory_products)
                inventory = self.create(inventory_vals)
                inventory.create_inventory_lines_ept(inventory_lines, location_id)

                inventory.action_start()
                if auto_validate:
                    inventory.action_validate()
                inventories += inventory
                del products[:100]

            return inventories
        return False

    @api.model
    def create_inventory_lines_ept(self, products, location_id):
        """
        Added by Udit
        This method will create inventory as per the data passed to the method.
        :param products: List of dictionary for which requested to make inventory adjustment.
        :param location_id: Location for which need an inventory adjustment.
        Migration done by twinkalc August 2020
        """
        inventory_line_obj = self.env['stock.inventory.line']
        vals_list = []
        for product_data in products:
            if product_data.get('product_id') and product_data.get('product_qty'):
                val = self.prepare_inventory_line_vals_ept(product_data.get('product_id'),
                                                           product_data.get('product_qty'),
                                                           location_id)
                vals_list.append(val)
        inventory_line_obj.create(vals_list)
        return True

    def prepare_inventory_line_vals_ept(self, product, qty, location):
        """
        Added by Udit
        This method will create inventory line vals.
        :param product: Product object for which we need to create inventory adjustment.
        :param qty: Actual quantity.
        :param location: Location for which need an inventory adjustment.
        :return: This method will return inventory line vals.
        Migration done by twinkalc August 2020
        """
        vals = {
            'company_id': self.company_id.id,
            'product_id': product.id,
            'inventory_id': self.id,
            'location_id': location.id,
            'product_qty': 0 if qty <= 0 else qty,
            'product_uom_id': product.uom_id.id if product.uom_id else False,
        }
        return vals

    def prepare_inventory_vals_ept(self, location_id, inventory_products):
        """
        Prepares dictionary for creating inventory.
        @author: Maulik Barad on Date 20-Oct-2020.

        """
        inventory_name = 'product_inventory_%s' % (time.strftime("%Y-%m-%d %H:%M:%S"))
        return {
            'name': inventory_name,
            'location_ids': [(6, 0, [location_id.id])] if location_id else False,
            'date': time.strftime("%Y-%m-%d %H:%M:%S"),
            'product_ids': [(6, 0, inventory_products)],
            'prefill_counted_quantity': 'zero',
            "company_id": location_id.company_id.id if location_id else self.env.company.id
        }
