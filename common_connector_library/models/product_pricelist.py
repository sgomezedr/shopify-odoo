# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models


class ProductPricelist(models.Model):
    _inherit = "product.pricelist"

    def get_product_price_ept(self, product, partner=False):
        """
        Gives price of a product from pricelist(self).
        :param product: product id
        :param partner: partner id or False
        :return: price
        Migration done by twinkalc August 2020
        """
        price = self.get_product_price(product, 1.0, partner=partner, uom_id=product.uom_id.id)
        return price

    def set_product_price_ept(self, product_id, price, min_qty=1):
        """
        Creates or updates price for product in Pricelist.
        :param product_id: Id of product.
        :param price: Price
        :param min_qty: qty
        :return: product_pricelist_item
        Migration done by twinkalc August 2020
        """
        product_pricelist_item_obj = self.env['product.pricelist.item']
        domain = [('pricelist_id', '=', self.id), ('product_id', '=', product_id), ('min_quantity', '=', min_qty)]

        product_pricelist_item = product_pricelist_item_obj.search(domain)

        if product_pricelist_item:
            product_pricelist_item.write({'fixed_price': price})
        else:
            vals = {
                'pricelist_id': self.id,
                'applied_on': '0_product_variant',
                'product_id': product_id,
                'min_quantity': min_qty,
                'fixed_price': price,
            }
            new_record = product_pricelist_item_obj.new(vals)
            new_record._onchange_product_id()
            new_vals = product_pricelist_item_obj._convert_to_write(
                {name: new_record[name] for name in new_record._cache})
            product_pricelist_item = product_pricelist_item_obj.create(new_vals)
        return product_pricelist_item
