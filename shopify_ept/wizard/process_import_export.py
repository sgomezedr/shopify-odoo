# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import base64
import csv
import logging
import time

from datetime import datetime, timedelta
from io import StringIO, BytesIO

from odoo.exceptions import UserError
from odoo.tools.misc import split_every

from odoo import models, fields, api, _
from .. import shopify
from ..shopify.pyactiveresource.connection import ClientError

_logger = logging.getLogger("Shopify Operations")


class ShopifyProcessImportExport(models.TransientModel):
    _name = 'shopify.process.import.export'
    _description = 'Shopify Process Import Export'

    shopify_instance_id = fields.Many2one("shopify.instance.ept", string="Instance")
    shopify_operation = fields.Selection(
        [("sync_product", "Import Products"),
         ("sync_product_by_remote_ids", "Import Products - By Remote Ids"),
         ("import_customers", "Import Customers"),
         ("import_unshipped_orders", "Import Unshipped Orders"),
         ("import_shipped_orders", "Import Shipped Orders"),
         ("import_orders_by_remote_ids", "Import Orders - By Remote Ids"),
         ("update_order_status", "Update Order Shipping Status"),
         ("export_stock", "Export Stock"),
         ("import_stock", "Import Stock"),
         ("import_products_from_csv", "Import Products From CSV"),
         ("import_location", "Import Location"),
         ("import_payout_report", "Import Payout Report")], default="sync_product", string="Operation")
    orders_from_date = fields.Datetime(string="From Date")
    orders_to_date = fields.Datetime(string="To Date")
    shopify_instance_ids = fields.Many2many("shopify.instance.ept", "shopify_instance_import_export_rel",
                                            "process_id", "shopify_instance_id", "Instances")
    shopify_is_set_price = fields.Boolean(string="Set Price ?",
                                          help="If is a mark, it set the price with product in the Shopify store.",
                                          default=False)
    shopify_is_set_stock = fields.Boolean(string="Set Stock ?",
                                          help="If is a mark, it set the stock with product in the Shopify store.",
                                          default=False)
    shopify_is_publish = fields.Selection(
        [('publish_product_web', 'Publish Web Only'), ('publish_product_global', 'Publish Web and POS'),
         ('unpublish_product', 'Unpublish')],
        string="Publish In Website ?",
        help="If is a mark, it publish the product in website.",
        default='publish_product_web')
    shopify_is_set_image = fields.Boolean(string="Set Image ?",
                                          help="If is a mark, it set the image with product in the Shopify store.",
                                          default=False)
    shopify_is_set_basic_detail = fields.Boolean(string="Set Basic Detail ?",
                                                 help="If is a mark, it set the product basic detail in shopify store",
                                                 default=True)
    shopify_is_update_basic_detail = fields.Boolean(string="Update Basic Detail ?", default=False,
                                                    help="If is a mark, it update the product basic detail in "
                                                         "shopify store")
    shopify_is_update_price = fields.Boolean(string="set Price ?")
    shopify_template_ids = fields.Text(string="Template Ids",
                                       help="Based on template ids get product from shopify and import in odoo")
    shopify_order_ids = fields.Text(string="Order Ids",
                                    help="Based on template ids get product from shopify and import products in odoo")
    export_stock_from = fields.Datetime(help="It is used for exporting stock from Odoo to Shopify.")
    payout_start_date = fields.Date(string="Start Date")
    payout_end_date = fields.Date(string="End Date")
    skip_existing_product = fields.Boolean(string="Do Not Update Existing Products",
                                           help="Check if you want to skip existing products.")
    csv_file = fields.Binary(help="Select CSV file to upload.")
    file_name = fields.Char(help="Name of CSV file.")
    cron_process_notification = fields.Text(string="Shopify Note: ", store=False,
                                            help="Used to display that cron will be run after some time")
    is_hide_operation_execute_button = fields.Boolean(default=False, store=False,
                                                      help="Used to hide the execute button from operation wizard "
                                                           "while selected operation cron is running in backend")

    def shopify_execute(self):
        """This method used to execute the operation as per given in wizard.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 25/10/2019.
        """
        product_data_queue_obj = self.env["shopify.product.data.queue.ept"]
        order_date_queue_obj = self.env["shopify.order.data.queue.ept"]
        queue_ids = False

        instance = self.shopify_instance_id
        if self.shopify_operation == "sync_product":
            product_queue_ids = product_data_queue_obj.shopify_create_product_data_queue(instance,
                                                                                         self.skip_existing_product)
            if product_queue_ids:
                queue_ids = product_queue_ids
                action_name = "shopify_ept.action_shopify_product_data_queue"
                form_view_name = "shopify_ept.product_synced_data_form_view_ept"

        elif self.shopify_operation == "sync_product_by_remote_ids":
            product_queue_ids = product_data_queue_obj.shopify_create_product_data_queue(instance,
                                                                                         self.skip_existing_product,
                                                                                         self.shopify_template_ids)
            if product_queue_ids:
                queue_ids = product_queue_ids
                product_data_queue = product_data_queue_obj.browse(queue_ids)
                product_data_queue.product_data_queue_lines.process_product_queue_line_data()
                _logger.info("Processed product queue : %s of Instance : %s Via Product Template ids Successfully .",
                             product_data_queue.name, instance.name)
                if not product_data_queue.product_data_queue_lines:
                    product_data_queue.unlink()
                action_name = "shopify_ept.action_shopify_product_data_queue"
                form_view_name = "shopify_ept.product_synced_data_form_view_ept"

        elif self.shopify_operation == "import_customers":
            customer_queues = self.sync_shopify_customers()
            if customer_queues:
                queue_ids = customer_queues
                action_name = "shopify_ept.action_shopify_synced_customer_data"
                form_view_name = "shopify_ept.shopify_synced_customer_data_form_view_ept"

        elif self.shopify_operation == "import_unshipped_orders":
            order_date_queue_obj.shopify_create_order_data_queues(instance, self.orders_from_date,
                                                                  self.orders_to_date,
                                                                  order_type="unshipped")

        elif self.shopify_operation == "import_shipped_orders":
            order_queues = order_date_queue_obj.shopify_create_order_data_queues(instance,
                                                                                 self.orders_from_date,
                                                                                 self.orders_to_date,
                                                                                 order_type="shipped")
            if order_queues:
                queue_ids = order_queues
                action_name = "shopify_ept.action_shopify_order_data_queue_ept"
                form_view_name = "shopify_ept.view_shopify_order_data_queue_ept_form"

        elif self.shopify_operation == "import_orders_by_remote_ids":
            order_date_queue_obj.import_order_process_by_remote_ids(instance, self.shopify_order_ids)

        elif self.shopify_operation == "export_stock":
            self.update_stock_in_shopify()

        elif self.shopify_operation == "import_stock":
            inventory_records = self.import_stock_in_odoo()
            if inventory_records:
                queue_ids = inventory_records
                action_name = "stock.action_inventory_form"
                form_view_name = "stock.view_inventory_form"

        elif self.shopify_operation == "update_order_status":
            self.update_order_status()

        elif self.shopify_operation == "import_payout_report":
            if self.payout_end_date and self.payout_start_date:
                if self.payout_end_date < self.payout_start_date:
                    raise UserError("The start date must be precede its end date")
                self.env["shopify.payout.report.ept"].get_payout_report(self.payout_start_date, self.payout_end_date,
                                                                        instance)

        elif self.shopify_operation == "import_products_from_csv":
            self.import_products_from_csv()

        elif self.shopify_operation == "import_location":
            shopify_locations = self.import_shopify_location()
            if shopify_locations:
                queue_ids = shopify_locations
                action_name = "shopify_ept.action_shopify_location_data"
                form_view_name = "shopify_ept.shopify_synced_locations_data_form_view_ept"

        if queue_ids and action_name and form_view_name:
            action = self.env.ref(action_name).sudo().read()[0]
            form_view = self.sudo().env.ref(form_view_name)

            if len(queue_ids) == 1:
                action.update({"view_id": (form_view.id, form_view.name), "res_id": queue_ids[0],
                               "views": [(form_view.id, "form")]})
            else:
                action["domain"] = [("id", "in", queue_ids)]
            return action

        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def manual_export_product_to_shopify(self):
        """ This method is used to call child method for export products from shopify layer products to Shopify store.
            It calls from the Shopify layer product screen.
        """
        start = time.time()
        shopify_product_template_obj = self.env["shopify.product.template.ept"]
        shopify_product_obj = self.env['shopify.product.product.ept']
        instance_obj = self.env['shopify.instance.ept']

        shopify_products = self._context.get('active_ids', [])

        template = shopify_product_template_obj.browse(shopify_products)
        templates = template.filtered(lambda x: not x.exported_in_shopify)
        if templates and len(templates) > 80:
            raise UserError(_("Error:\n- System will not export more then 80 Products at a "
                              "time.\n- Please select only 80 product for export."))
        shopify_instances = instance_obj.search([])
        for instance in shopify_instances:
            shopify_templates = templates.filtered(lambda product: product.shopify_instance_id == instance)
            if shopify_templates:
                shopify_product_obj.shopify_export_products(instance,
                                                            self.shopify_is_set_basic_detail,
                                                            self.shopify_is_set_price,
                                                            self.shopify_is_set_image,
                                                            self.shopify_is_publish,
                                                            shopify_templates)
        end = time.time()
        _logger.info("Export Processed %s Products in %s seconds.", str(len(templates)), str(end - start))
        return True

    def manual_update_product_to_shopify(self):
        """ This method is used to call child method for update products values from shopify layer products to Shopify
            store. It calls from the Shopify layer product screen.
        """
        if not self.shopify_is_update_basic_detail and not self.shopify_is_publish and not self.shopify_is_set_price \
            and not self.shopify_is_set_image:
            raise UserError("Please Select Any Option To Update Product.")

        shopify_product_template_obj = self.env['shopify.product.template.ept']
        shopify_product_obj = self.env['shopify.product.product.ept']
        instance_obj = self.env['shopify.instance.ept']

        start = time.time()
        shopify_products = self._context.get('active_ids', [])

        template = shopify_product_template_obj.browse(shopify_products)
        templates = template.filtered(lambda x: x.exported_in_shopify)
        if templates and len(templates) > 80:
            raise UserError(_("Error:\n- System will not update more then 80 Products at a "
                              "time.\n- Please select only 80 product for export."))
        shopify_instances = instance_obj.search([])
        for instance in shopify_instances:
            shopify_templates = templates.filtered(lambda product: product.shopify_instance_id == instance)
            if shopify_templates:
                shopify_product_obj.update_products_in_shopify(instance, shopify_templates,
                                                               self.shopify_is_set_price,
                                                               self.shopify_is_set_image,
                                                               self.shopify_is_publish,
                                                               self.shopify_is_update_basic_detail)
        end = time.time()
        _logger.info("Update Processed %s Products in %s seconds.", str(len(template)), str(end - start))
        return True

    def shopify_export_variant_vals(self, instance, variant, shopify_template):
        """This method used prepare a shopify template vals for export product process,
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 17/10/2019.
        """
        shopify_variant_vals = {
            'shopify_instance_id': instance.id,
            'product_id': variant.id,
            'shopify_template_id': shopify_template.id,
            'default_code': variant.default_code,
            'name': variant.name,
        }
        return shopify_variant_vals

    def shopify_export_template_vals(self, instance, odoo_template):
        """This method used prepare a shopify template vals for export product process,
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 17/10/2019.
        """
        shopify_template_vals = {
            'shopify_instance_id': instance.id,
            'product_tmpl_id': odoo_template.id,
            'name': odoo_template.name,
            'description': odoo_template.description_sale,
            'shopify_product_category': odoo_template.categ_id.id,
        }
        return shopify_template_vals

    def sync_shopify_customers(self):
        """
        This method used to sync the customers data from Shopify to Odoo.
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 23/10/2019.
        :Task ID: 157065
        @change: Maulik Barad on Date 09-Sep-2020.
        """
        customer_queues_ids = []

        self.shopify_instance_id.connect_in_shopify()
        if not self.shopify_instance_id.shopify_last_date_customer_import:
            customer_ids = shopify.Customer().find(limit=250)
        else:
            customer_ids = shopify.Customer().find(
                updated_at_min=self.shopify_instance_id.shopify_last_date_customer_import, limit=250)
        if customer_ids:
            customer_queues_ids = self.create_customer_data_queues(customer_ids)
            if len(customer_ids) == 250:
                customer_queues_ids += self.shopify_list_all_customer(customer_ids)

            self.shopify_instance_id.shopify_last_date_customer_import = datetime.now()
        if not customer_ids:
            _logger.info("Customers not found while the import customers from Shopify")
        return customer_queues_ids

    def create_customer_data_queues(self, customer_data):
        """
        It creates customer data queue from data of Customer.
        @author: Maulik Barad on Date 09-Sep-2020.
        @param customer_data: Data of Customer.
        """
        customer_queue_list = []
        customer_data_queue_obj = self.env["shopify.customer.data.queue.ept"]
        customer_data_queue_line_obj = self.env["shopify.customer.data.queue.line.ept"]
        bus_bus_obj = self.env["bus.bus"]

        if len(customer_data) > 0:
            for customer_id_chunk in split_every(125, customer_data):
                customer_queue = customer_data_queue_obj.create_customer_queue(self.shopify_instance_id,
                                                                               "import_process")
                customer_data_queue_line_obj.shopify_create_multi_queue(customer_queue, customer_id_chunk)

                message = "Customer Queue created {}".format(customer_queue.name)
                bus_bus_obj.sendone((self._cr.dbname, "res.partner", self.env.user.partner_id.id),
                                    {"type": "simple_notification", "title": "Shopify Notification",
                                     "message": message, "sticky": False, "warning": True})
                _logger.info(message)

                customer_queue_list.append(customer_queue.id)
            self._cr.commit()
        return customer_queue_list

    def webhook_customer_create_process(self, res, instance):
        """
        This method is used for create customer queue and queue line while the customer create form the webhook method.
        :param res: Response of customer which receive from the webhook.
        :param instance: Record of the instance.
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 13/01/2020.
        """
        data_queue_obj = self.env['shopify.customer.data.queue.ept']

        customer_queue_id = data_queue_obj.search([("record_created_from", "=", "webhook"), ("state", "=", "draft"),
                                                   ("shopify_instance_id", "=", instance.id)])
        if customer_queue_id:
            message = "Customer %s added into Queue %s." % (res.get("first_name"), customer_queue_id.name)
        else:
            customer_queue_id = data_queue_obj.create_customer_queue(instance, "webhook")
            message = "Customer Queue %s created." % customer_queue_id.name
        _logger.info(message)

        customer_queue_id.synced_customer_queue_line_ids.shopify_customer_data_queue_line_create(res, customer_queue_id)
        if len(customer_queue_id.synced_customer_queue_line_ids) == 50:
            customer_queue_id.synced_customer_queue_line_ids.sync_shopify_customer_into_odoo()
        return True

    def shopify_list_all_customer(self, result):
        """
        This method used to call the page wise data import for customers from Shopify to Odoo.
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 14/10/2019.
        :Task ID: 157065
        Modify by Haresh Mori on date 26/12/2019, Taken Changes for the pagination and API version.
        """
        catch = ""
        customer_queue_list = []
        while result:
            page_info = ""
            link = shopify.ShopifyResource.connection.response.headers.get('Link')
            if not link or not isinstance(link, str):
                return customer_queue_list
            for page_link in link.split(','):
                if page_link.find('next') > 0:
                    page_info = page_link.split(';')[0].strip('<>').split('page_info=')[1]
                    try:
                        result = shopify.Customer().find(page_info=page_info, limit=250)
                    except ClientError as error:
                        if hasattr(error, "response"):
                            if error.response.code == 429 and error.response.msg == "Too Many Requests":
                                time.sleep(5)
                                result = shopify.Customer().find(page_info=page_info, limit=250)
                    except Exception as error:
                        raise UserError(error)
                    if result:
                        customer_queue_list += self.create_customer_data_queues(result)
            if catch == page_info:
                break
        return customer_queue_list

    @api.model
    def update_stock_in_shopify(self, ctx={}):
        """
        This method used to export stock from odoo to shopify.
        @author: Maulik Barad on Date 15-Sep-2020.
        """
        shopify_instance_obj = self.env['shopify.instance.ept']
        product_obj = self.env['product.product']
        shopify_product_obj = self.env['shopify.product.product.ept']

        if self.shopify_instance_id:
            instance = self.shopify_instance_id
        elif ctx.get('shopify_instance_id'):
            instance_id = ctx.get('shopify_instance_id')
            instance = shopify_instance_obj.browse(instance_id)

        if not instance:
            raise UserError(_("Shopify instance not found.\nPlease select one, if you are processing from Operations"
                              " wizard.\nOtherwise please check the code of cron, if it has been modified."))
        if self.export_stock_from:
            last_update_date = self.export_stock_from
            _logger.info("Exporting Stock from Operations wizard for instance - %s", instance.name)
        else:
            last_update_date = instance.shopify_last_date_update_stock or datetime.now() - timedelta(30)
            _logger.info("Exporting Stock by Cron for instance - %s", instance.name)

        products = product_obj.get_products_based_on_movement_date_ept(last_update_date,
                                                                       instance.shopify_company_id)
        if products:
            shopify_products = shopify_product_obj.export_stock_in_shopify(instance, products)
            if shopify_products:
                instance.write({'shopify_last_date_update_stock': shopify_products[0].last_stock_update_date})
        else:
            instance.shopify_last_date_update_stock = datetime.now()
            _logger.info("No products found to export stock from %s.....", last_update_date)

        return True

    def shopify_selective_product_stock_export(self):
        """
        This method export stock of particular selected products in list view or from form view's action menu.
        @author: Maulik Barad on Date 10-Oct-2020.
        """
        shopify_product_obj = self.env['shopify.product.product.ept']
        shopify_template_ids = self._context.get('active_ids')

        shopify_instances = self.env['shopify.instance.ept'].search([])
        for instance in shopify_instances:
            shopify_products = shopify_product_obj.search([
                ('shopify_instance_id', '=', instance.id),
                ('shopify_template_id', 'in', shopify_template_ids)])
            odoo_product_ids = shopify_products.product_id.ids
            if odoo_product_ids:
                shopify_product_obj.with_context({'is_process_from_selected_product': True}).export_stock_in_shopify(
                    instance, odoo_product_ids)
        return True

    def import_stock_in_odoo(self):
        """
        Import stock from shopify to odoo.
        :Task id: 157905
        """
        instance = self.shopify_instance_id
        shopify_product_obj = self.env['shopify.product.product.ept']
        inventory_records = shopify_product_obj.import_shopify_stock(instance)

        return inventory_records

    def update_order_status(self, instance=False):
        """This method is used to call child method for update order status from Odoo to Shopify.
            @author: Angel Patel @Emipro Technologies Pvt.
            :Task ID: 157905
        """
        sale_order_obj = self.env['sale.order']
        if not instance:
            instance = self.shopify_instance_id
        if instance.active:
            sale_order_obj.update_order_status_in_shopify(instance)
        else:
            _logger.info(_("Your instance '%s' is in active.", instance.name))
        return True

    def update_order_status_cron_action(self, ctx):
        """
        This method is while update order status cron is active.
        @author: Angel Patel @Emipro Technologies Pvt.
        :Task ID: 157716
        """
        instance_id = ctx.get('shopify_instance_id')
        instance = self.env['shopify.instance.ept'].browse(instance_id)
        _logger.info(
            _("Auto cron update order status process start with instance: '%s'"), instance.name)
        self.update_order_status(instance)
        return True

    @api.onchange("shopify_instance_id", "shopify_operation")
    def onchange_shopify_instance_id(self):
        """
        This method sets field values, when the Instance will be changed.
        Author: Bhavesh Jadav 23/12/2019
        """
        instance = self.shopify_instance_id
        self.cron_process_notification = False
        self.is_hide_operation_execute_button = False
        current_time = datetime.now()
        if instance:
            if self.shopify_operation == "import_unshipped_orders":
                self.orders_from_date = instance.last_date_order_import or False
                self.shopify_check_running_schedulers('ir_cron_shopify_auto_import_order_instance_')
            elif self.shopify_operation == "import_shipped_orders":
                self.orders_from_date = instance.last_shipped_order_import_date or False
            elif self.shopify_operation == 'update_order_status':
                self.shopify_check_running_schedulers('ir_cron_shopify_auto_update_order_status_instance_')
            elif self.shopify_operation == 'export_stock':
                self.shopify_check_running_schedulers('ir_cron_shopify_auto_export_inventory_instance_')
            self.orders_to_date = current_time
            self.export_stock_from = instance.shopify_last_date_update_stock or datetime.now() - timedelta(30)
            if instance.payout_last_import_date:
                self.payout_start_date = instance.payout_last_import_date
            self.payout_end_date = current_time

    def import_products_from_csv(self):
        """
        This method used to import product using csv file in shopify third layer.
        @author: Maulik Barad on Date 12-Oct-2020.
        """
        prepare_product_for_export_obj = self.env["shopify.prepare.product.for.export.ept"]
        common_log_obj = self.env["common.log.book.ept"]
        common_log_line_obj = self.env["common.log.lines.ept"]
        model_id = common_log_line_obj.get_model_id("shopify.product.product.ept")

        if not self.csv_file:
            raise UserError(_("File Not Found To Import"))
        if not self.file_name.endswith(".csv"):
            raise UserError(_("Please Provide Only .csv File To Import Product !!!"))
        file_data = self.read_file()
        instance = self.shopify_instance_id
        log_book_id = common_log_obj.shopify_create_common_log_book("import", instance, model_id)
        self.validate_required_csv_header(file_data)
        sequence = 0
        row_no = 1
        shopify_template_id = False
        for record in file_data:
            message = ""
            if not record["PRODUCT_TEMPLATE_ID"] or not record["PRODUCT_ID"] or not record["CATEGORY_ID"]:
                message += "PRODUCT_TEMPLATE_ID Or PRODUCT_ID Or CATEGORY_ID Not As Per Odoo Product %s" % row_no
                vals = {"message": message,
                        "model_id": model_id,
                        "log_book_id": log_book_id.id}
                common_log_line_obj.create(vals)
                continue

            shopify_template, shopify_template_id, sequence = self.create_or_update_shopify_template_from_csv(instance,
                                                                                                              record,
                                                                                                              shopify_template_id,
                                                                                                              sequence)

            shopify_variant = self.create_or_update_shopify_variant_from_csv(instance, record, shopify_template_id,
                                                                             sequence)
            row_no = +1
            prepare_product_for_export_obj.create_shopify_variant_images(shopify_template, shopify_variant)

        if not log_book_id.log_lines:
            log_book_id.unlink()
        return True

    def validate_required_csv_header(self, file_data):
        """ This method is used to validate required csv header while csv file import for products.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 26 October 2020 .
            Task_id: 167537 - Code refactoring
        """
        required_fields = ["template_name", "product_name", "product_default_code",
                           "shopify_product_default_code", "product_description",
                           "PRODUCT_TEMPLATE_ID", "PRODUCT_ID", "CATEGORY_ID"]

        for required_field in required_fields:
            if required_field not in file_data.fieldnames:
                raise UserError(_("Required column is not available in File."))

    def create_or_update_shopify_template_from_csv(self, instance, record, shopify_template_id, sequence):
        """ This method is used to create or update shopify template while process from csv file import.
            :param record: One row data of csv file.
            @return: shopify_template, shopify_template_id, sequence
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 26 October 2020 .
            Task_id: 167537 - Code refactoring
        """
        shopify_product_template = self.env["shopify.product.template.ept"]
        prepare_product_for_export_obj = self.env["shopify.prepare.product.for.export.ept"]
        shopify_template = shopify_product_template.search(
            [("shopify_instance_id", "=", instance.id),
             ("product_tmpl_id", "=", int(record["PRODUCT_TEMPLATE_ID"]))])

        shopify_product_template_vals = {"product_tmpl_id": int(record["PRODUCT_TEMPLATE_ID"]),
                                         "shopify_instance_id": instance.id,
                                         "shopify_product_category": int(record["CATEGORY_ID"]),
                                         "name": record["template_name"]}
        if self.env["ir.config_parameter"].sudo().get_param("shopify_ept.set_sales_description"):
            shopify_product_template_vals.update({"description": record["product_description"]})
        if not shopify_template:
            shopify_template = shopify_product_template.create(shopify_product_template_vals)
            sequence = 1
            shopify_template_id = shopify_template.id
        elif shopify_template_id != shopify_template.id:
            shopify_template.write(shopify_product_template_vals)
            shopify_template_id = shopify_template.id

        prepare_product_for_export_obj.create_shopify_template_images(shopify_template)

        if shopify_template and shopify_template.shopify_product_ids and \
            shopify_template.shopify_product_ids[0].sequence:
            sequence += 1

        return shopify_template, shopify_template_id, sequence

    def create_or_update_shopify_variant_from_csv(self, instance, record, shopify_template_id, sequence):
        """ This method is used to create or update Shopify variants while processing from CSV file import operation.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 26 October 2020 .
            Task_id: 167537 - Code refactoring
        """
        shopify_product_obj = self.env["shopify.product.product.ept"]
        shopify_variant = shopify_product_obj.search(
            [("shopify_instance_id", "=", instance.id),
             ("product_id", "=", int(record["PRODUCT_ID"])),
             ("shopify_template_id", "=", shopify_template_id)])
        shopify_variant_vals = {"shopify_instance_id": instance.id,
                                "product_id": int(record["PRODUCT_ID"]),
                                "shopify_template_id": shopify_template_id,
                                "default_code": record["shopify_product_default_code"],
                                "name": record["product_name"],
                                "sequence": sequence}
        if not shopify_variant:
            shopify_variant = shopify_product_obj.create(shopify_variant_vals)
        else:
            shopify_variant.write(shopify_variant_vals)

        return shopify_variant

    def read_file(self):
        """
        This method reads .csv file
        @author: Nilesh Parmar @Emipro Technologies Pvt. Ltd on date 08/11/2019
        """
        import_file = BytesIO(base64.decodebytes(self.csv_file))
        file_read = StringIO(import_file.read().decode())
        reader = csv.DictReader(file_read, delimiter=",")

        return reader

    def import_shopify_location(self):
        """ This method is used to call the child method to import the Shopify location from Shopify to Odoo.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 10 November 2020 .
            Task_id: 168214 - Import locations process
        """
        shopify_location_obj = self.env["shopify.location.ept"]
        shopify_locations = shopify_location_obj.import_shopify_locations(self.shopify_instance_id)
        return shopify_locations

    def shopify_check_running_schedulers(self, cron_xml_id):
        """ This method is used to check that selected operation cron is running or not.
            :param cron_xml_id: Xml id of the scheduler action.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 12 November 2020 .
            Task_id: 167717 - Manual operation & cron execution conflict
        """
        try:
            cron_id = self.env.ref('shopify_ept.%s%d' % (cron_xml_id, self.shopify_instance_id.id))
        except:
            return
        if cron_id and cron_id.sudo().active:
            res = cron_id.try_cron_lock()
            if res == None:
                res = {}
            if res and res.get('reason') or res.get('result') == 0:
                message = "You are not allowed to run this process.The Scheduler is already started the Process."
                self.cron_process_notification = message
                self.is_hide_operation_execute_button = True
            if res and res.get('result'):
                self.cron_process_notification = "This process is also performed by a scheduler, and the next " \
                                                 "schedule for this process will run in %s minutes." % res.get('result')
            elif res and res.get('reason'):
                self.cron_process_notification = res.get('reason')
