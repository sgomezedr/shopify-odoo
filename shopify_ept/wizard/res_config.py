# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .. import shopify


class ShopifyInstanceConfig(models.TransientModel):
    _name = "res.config.shopify.instance"
    _description = "Shopify Instance Configuration"

    name = fields.Char(help="Any User friendly name to identify the Shopify store")
    shopify_api_key = fields.Char("API Key", required=True, help="Shopify API Key. You can find "
                                                                 "it under Shopify store control "
                                                                 "panel.")
    shopify_password = fields.Char("Password", required=True, help="Shopify API Password. You can "
                                                                   "find it under Shopify store control panel")
    shopify_shared_secret = fields.Char("Secret Key", required=True, help="Shopify API Shared Secret. You can find it "
                                                                          "under Shopify store control panel")
    shopify_host = fields.Char("Host", required=True,
                               help="Add your shopify store URL, for example, https://my-shopify-store.myshopify.com")
    shopify_company_id = fields.Many2one("res.company", string="Instance Company",
                                         help="Orders and Invoices will be generated of this company.")

    def create_pricelist(self, shop_currency):
        """
        This method creates pricelist from currency of the Shopify store.
        @author: Maulik Barad on Date 25-Sep-2020.
        @param shop_currency: Currency got from shopify store.
        """
        currency_obj = self.env["res.currency"]
        pricelist_obj = self.env["product.pricelist"]

        currency_id = currency_obj.search([("name", "=", shop_currency)], limit=1)

        if not currency_id:
            currency_id = currency_obj.search([("name", "=", shop_currency), ("active", "=", False)], limit=1)
            currency_id.write({"active": True})
        if not currency_id:
            currency_id = self.env.user.currency_id

        price_list_name = self.name + " " + "PriceList"
        pricelist = pricelist_obj.search([("name", "=", price_list_name),
                                          ("currency_id", "=", currency_id.id),
                                          ("company_id", "=", self.shopify_company_id.id)],
                                         limit=1)
        if not pricelist:
            pricelist = pricelist_obj.create({"name": price_list_name,
                                              "currency_id": currency_id.id,
                                              "company_id": self.shopify_company_id.id})

        return pricelist.id

    def shopify_test_connection(self):
        """This method used to verify whether Odoo is capable of connecting with Shopify store or not.
            @return : Action of type reload.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 04/10/2019.
        """
        instance_obj = self.env["shopify.instance.ept"]
        shopify_location_obj = self.env["shopify.location.ept"]
        payment_gateway_obj = self.env["shopify.payment.gateway.ept"]
        financial_status_obj = self.env["sale.auto.workflow.configuration.ept"]

        instance_id = instance_obj.with_context(active_test=False).search(
            ["|", ("shopify_api_key", "=", self.shopify_api_key),
             ("shopify_host", "=", self.shopify_host)], limit=1)
        if instance_id:
            raise UserError(_(
                "An instance already exists for the given details \nShopify API key : '%s' \nShopify Host : '%s'" % (
                    self.shopify_api_key, self.shopify_host)))

        shop_url = instance_obj.prepare_shopify_shop_url(self.shopify_host, self.shopify_api_key, self.shopify_password)

        shopify.ShopifyResource.set_site(shop_url)

        try:
            shop_id = shopify.Shop.current()
        except Exception as error:
            raise UserError(error)

        shop_detail = shop_id.to_dict()

        vals = self.prepare_val_for_instance_creation(shop_detail)

        shopify_instance = instance_obj.create(vals)
        shopify_location_obj.import_shopify_locations(shopify_instance)

        payment_gateway_obj.import_payment_gateway(shopify_instance)
        financial_status_obj.create_financial_status(shopify_instance, "paid")

        if self._context.get('is_calling_from_onboarding_panel', False):
            company = shopify_instance.shopify_company_id
            shopify_instance.write({'is_instance_create_from_onboarding_panel': True})
            company.set_onboarding_step_done('shopify_instance_onboarding_state')
            company.write({'is_create_shopify_more_instance': True})

        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def prepare_val_for_instance_creation(self, shop_detail):
        """ This method is used to prepare a vals for instance creation.
            :param shop_detail: Response of shopify.
            @return: vals
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 26 October 2020 .
            Task_id: 167537 - Code refactoring
        """
        warehouse_obj = self.env['stock.warehouse']
        ir_model_obj = self.env["ir.model.fields"]
        shop_currency = shop_detail.get("currency")
        warehouse = warehouse_obj.search([('company_id', '=', self.shopify_company_id.id)], limit=1, order='id')
        pricelist_id = self.create_pricelist(shop_currency)

        stock_field = ir_model_obj.search(
            [("model_id.model", "=", "product.product"), ("name", "=", "free_qty")],
            limit=1)
        vals = {
            "name": self.name,
            "shopify_api_key": self.shopify_api_key,
            "shopify_password": self.shopify_password,
            "shopify_shared_secret": self.shopify_shared_secret,
            "shopify_host": self.shopify_host,
            "shopify_company_id": self.shopify_company_id.id,
            "shopify_warehouse_id": warehouse.id,
            "shopify_store_time_zone": shop_detail.get("iana_timezone"),
            "shopify_pricelist_id": pricelist_id or False,
            "apply_tax_in_order": "create_shopify_tax",
            "shopify_stock_field": stock_field and stock_field.id or False
        }
        return vals

    @api.model
    def action_shopify_open_shopify_instance_wizard(self):
        """ Called by onboarding panel above the Instance."""
        action = self.env["ir.actions.actions"]._for_xml_id(
            "shopify_ept.shopify_on_board_instance_configuration_action")
        action['context'] = {'is_calling_from_onboarding_panel': True}
        instance = self.env['shopify.instance.ept'].search_shopify_instance()
        if instance:
            action.get('context').update({
                'default_name': instance.name,
                'default_shopify_host': instance.shopify_host,
                'default_shopify_api_key': instance.shopify_api_key,
                'default_shopify_password': instance.shopify_password,
                'default_shopify_shared_secret': instance.shopify_shared_secret,
                'default_shopify_company_id': instance.shopify_company_id.id,
                'is_already_instance_created': True,
            })
            company = instance.shopify_company_id
            if company.shopify_instance_onboarding_state != 'done':
                company.set_onboarding_step_done('shopify_instance_onboarding_state')
        return action

    def reset_credentials(self):
        """
        This method set the new credentials and check if connection can be made properly.
        @author: Maulik Barad on Date 01-Oct-2020.
        """
        shopify_instance_obj = self.env["shopify.instance.ept"]
        context = self.env.context
        instance_id = context.get("shopify_instance_id")

        instance = shopify_instance_obj.browse(instance_id)
        if instance.shopify_api_key == self.shopify_api_key or instance.shopify_password == self.shopify_password or \
            instance.shopify_shared_secret == self.shopify_shared_secret:
            raise UserError(_("Entered credentials are same as previous.\nPlease verify the credentials once."))

        vals = {"shopify_api_key": self.shopify_api_key,
                "shopify_password": self.shopify_password,
                "shopify_shared_secret": self.shopify_shared_secret}
        instance.shopify_test_connection(vals)
        if context.get("test_connection"):
            return {"type": "ir.actions.client", "tag": "display_notification",
                    "params": {"title": "Shopify",
                               "message": "New Credentials are working properly!",
                               "sticky": False}}
        instance.write(vals)

        return True


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    def _get_shopify_default_financial_statuses(self):
        if self._context.get('default_shopify_instance_id', False):
            financial_status_ids = self.env['sale.auto.workflow.configuration.ept'].search(
                [('shopify_instance_id', '=', self._context.get('default_shopify_instance_id', False))]).ids
            return [(6, 0, financial_status_ids)]

    shopify_instance_id = fields.Many2one("shopify.instance.ept", "Instance")
    shopify_company_id = fields.Many2one("res.company", string="Shopify Instance Company",
                                         help="Orders and Invoices will be generated of this company.")
    shopify_warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse",
                                           domain="[('company_id', '=',shopify_company_id)]")
    auto_import_product = fields.Boolean(string="Auto Create Product if not found?")
    shopify_sync_product_with = fields.Selection([("sku", "Internal Reference(SKU)"), ("barcode", "Barcode"),
                                                  ("sku_or_barcode", "Internal Reference(SKU) and Barcode")],
                                                 string="Sync Product With", default="sku")
    shopify_pricelist_id = fields.Many2one("product.pricelist", string="Pricelist")
    shopify_stock_field = fields.Many2one("ir.model.fields", string="Stock Field")
    shopify_section_id = fields.Many2one("crm.team", "Sales Team")
    shopify_is_use_default_sequence = fields.Boolean("Use Odoo Default Sequence in Shopify Orders",
                                                     help="If checked,Then use default sequence of odoo while create "
                                                          "sale order.")
    shopify_order_prefix = fields.Char(size=10, string="Order Prefix", help="Enter your order prefix")
    shopify_apply_tax_in_order = fields.Selection(
        [("odoo_tax", "Odoo Default Tax Behaviour"), ("create_shopify_tax", "Create New Tax If Not Found")],
        copy=False, default="create_shopify_tax", help=""" For Shopify Orders :- \n
                    1) Odoo Default Tax Behaviour - The Taxes will be set based on Odoo's default functional 
                    behaviour i.e. based on Odoo's Tax and Fiscal Position configurations. \n
                    2) Create New Tax If Not Found - System will search the tax data received 
                    from Shopify in Odoo, will create a new one if it fails in finding it.""")
    shopify_invoice_tax_account_id = fields.Many2one("account.account", string="Invoice Tax Account For Shopify Tax")
    shopify_credit_tax_account_id = fields.Many2one("account.account", string="Credit Note Tax Account For Shopify Tax")
    shopify_notify_customer = fields.Boolean("Notify Customer about Update Order Status?",
                                             help="If checked,Notify the customer via email about Update Order Status")
    shopify_user_ids = fields.Many2many("res.users", "shopify_res_config_settings_res_users_rel",
                                        "res_config_settings_id", "res_users_id", string="Responsible User")
    shopify_activity_type_id = fields.Many2one("mail.activity.type", string="Shopify Activity Type")
    shopify_date_deadline = fields.Integer("Deadline Lead Days for Shopify", default=1,
                                           help="its add number of  days in schedule activity deadline date ")
    is_shopify_create_schedule = fields.Boolean("Create Schedule activity ? ", default=False,
                                                help="If checked, Then Schedule Activity create on order dara queues"
                                                     " will any queue line failed.")
    shopify_sync_product_with_images = fields.Boolean("Shopify Sync/Import Images?", default=False,
                                                      help="Check if you want to import images along with products")
    create_shopify_products_webhook = fields.Boolean("Manage Shopify Products via Webhooks",
                                                     help="True : It will create all product related webhooks.\n"
                                                          "False : All product related webhooks will be deactivated.")
    create_shopify_customers_webhook = fields.Boolean("Manage Shopify Customers via Webhooks",
                                                      help="True : It will create all customer related webhooks.\n"
                                                           "False : All customer related webhooks will be deactivated.")
    create_shopify_orders_webhook = fields.Boolean("Manage Shopify Orders via Webhooks",
                                                   help="True : It will create all order related webhooks.\n"
                                                        "False : All order related webhooks will be deactivated.")
    shopify_default_pos_customer_id = fields.Many2one("res.partner", "Default POS customer",
                                                      help="This customer will be set in POS order, when"
                                                           "customer is not found.",
                                                      domain="[('customer_rank','>', 0)]")
    last_date_order_import = fields.Datetime(string="Last Date Of Unshipped Order Import",
                                             help="Last date of sync orders from Shopify to Odoo")
    shopify_last_date_customer_import = fields.Datetime(string="Last Date Of Customer Import",
                                                        help="it is used to store last import customer date")
    shopify_last_date_update_stock = fields.Datetime(string="Last Date of Stock Update",
                                                     help="it is used to store last update inventory stock date")
    shopify_last_date_product_import = fields.Datetime(string="Last Date Of Product Import",
                                                       help="it is used to store last import product date")
    shopify_settlement_report_journal_id = fields.Many2one("account.journal", string="Payout Report Journal")
    shopify_payout_last_date_import = fields.Date(string="Last Date of Payout Import",
                                                  help="It is used to store last update shopify payout report")
    shopify_financial_status_ids = fields.Many2many('sale.auto.workflow.configuration.ept',
                                                    'shopify_sale_auto_workflow_conf_rel',
                                                    'financial_onboarding_status_id', 'workflow_id',
                                                    string='Shopify Financial Status',
                                                    default=_get_shopify_default_financial_statuses)
    shopify_set_sales_description_in_product = fields.Boolean("Use Sales Description of Odoo Product for shopify",
                                                              config_parameter="shopify_ept.set_sales_description",
                                                              help="In both odoo products and Woocommerce layer products, "
                                                                   "it is used to set the description. For more details, "
                                                                   "please read the following summary.")
    shopify_order_status_ids = fields.Many2many('import.shopify.order.status',
                                                'shopify_config_settings_order_status_rel',
                                                'shopify_config_id', 'status_id',
                                                "Import Order Status",
                                                help="Select order status in which you want to import the orders from Shopify to Odoo.")
    auto_fulfill_gift_card_order = fields.Boolean(
        "Automatically fulfill only the gift cards of the order", default=True,
        help="If unchecked, It will fulfill qty from Odoo to shopify in update order status process")

    shopify_import_order_after_date = fields.Datetime(
        help="Connector only imports those orders which have created after a given date.")

    shopify_custom_service_product_id = fields.Many2one("product.product", "Custom Service Product",
                                                        domain=[('type', '=', 'service')],
                                                        help="This is used for set custom service products in sale order "
                                                             "lines while receiving the custom item in order response.")
    shopify_custom_storable_product_id = fields.Many2one("product.product", "Custom Storable Product",
                                                         domain=[('type', '=', 'product')],
                                                         help="This is used for set custom storable products in sale order "
                                                              "lines while receiving the custom item as required shipping in "
                                                              "order response.")

    @api.onchange("shopify_instance_id")
    def onchange_shopify_instance_id(self):
        instance = self.shopify_instance_id or False
        if instance:
            self.shopify_company_id = instance.shopify_company_id and instance.shopify_company_id.id or False
            self.shopify_warehouse_id = instance.shopify_warehouse_id and instance.shopify_warehouse_id or False
            self.auto_import_product = instance.auto_import_product or False
            self.shopify_sync_product_with = instance.shopify_sync_product_with
            self.shopify_pricelist_id = instance.shopify_pricelist_id and instance.shopify_pricelist_id.id or False
            self.shopify_stock_field = instance.shopify_stock_field and instance.shopify_stock_field.id or False
            self.shopify_section_id = instance.shopify_section_id.id or False
            self.shopify_order_prefix = instance.shopify_order_prefix
            self.shopify_is_use_default_sequence = instance.is_use_default_sequence
            self.shopify_apply_tax_in_order = instance.apply_tax_in_order
            self.shopify_invoice_tax_account_id = instance.invoice_tax_account_id and \
                                                  instance.invoice_tax_account_id.id or False
            self.shopify_credit_tax_account_id = instance.credit_tax_account_id and \
                                                 instance.credit_tax_account_id.id or False
            self.shopify_notify_customer = instance.notify_customer
            self.shopify_user_ids = instance.shopify_user_ids or False
            self.shopify_activity_type_id = instance.shopify_activity_type_id or False
            self.shopify_date_deadline = instance.shopify_date_deadline or False
            self.is_shopify_create_schedule = instance.is_shopify_create_schedule or False
            self.shopify_sync_product_with_images = instance.sync_product_with_images or False
            self.create_shopify_products_webhook = instance.create_shopify_products_webhook
            self.create_shopify_customers_webhook = instance.create_shopify_customers_webhook
            self.create_shopify_orders_webhook = instance.create_shopify_orders_webhook

            self.shopify_default_pos_customer_id = instance.shopify_default_pos_customer_id
            self.last_date_order_import = instance.last_date_order_import or False
            self.shopify_last_date_customer_import = instance.shopify_last_date_customer_import or False
            self.shopify_last_date_update_stock = instance.shopify_last_date_update_stock or False
            self.shopify_last_date_product_import = instance.shopify_last_date_product_import or False
            self.shopify_payout_last_date_import = instance.payout_last_import_date or False
            self.shopify_settlement_report_journal_id = instance.shopify_settlement_report_journal_id or False
            self.shopify_order_status_ids = instance.shopify_order_status_ids.ids
            self.auto_fulfill_gift_card_order = instance.auto_fulfill_gift_card_order
            self.shopify_import_order_after_date = instance.import_order_after_date or False
            self.shopify_custom_service_product_id = instance.custom_service_product_id
            self.shopify_custom_storable_product_id = instance.custom_storable_product_id

    def execute(self):
        """This method used to set value in an instance of configuration.
            @param : self
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 04/10/2019.
        """
        instance = self.shopify_instance_id
        values = {}
        res = super(ResConfigSettings, self).execute()
        if instance:
            # values["shopify_company_id"] = self.shopify_company_id and self.shopify_company_id.id or False
            values["shopify_warehouse_id"] = self.shopify_warehouse_id and self.shopify_warehouse_id.id or False
            values["auto_import_product"] = self.auto_import_product or False
            values["shopify_sync_product_with"] = self.shopify_sync_product_with
            values["shopify_pricelist_id"] = self.shopify_pricelist_id and self.shopify_pricelist_id.id or False
            values["shopify_stock_field"] = self.shopify_stock_field and self.shopify_stock_field.id or False
            values["shopify_section_id"] = self.shopify_section_id and self.shopify_section_id.id or False
            values["shopify_order_prefix"] = self.shopify_order_prefix
            values["is_use_default_sequence"] = self.shopify_is_use_default_sequence
            values["apply_tax_in_order"] = self.shopify_apply_tax_in_order
            values["invoice_tax_account_id"] = self.shopify_invoice_tax_account_id and \
                                               self.shopify_invoice_tax_account_id.id or False
            values["credit_tax_account_id"] = self.shopify_credit_tax_account_id and \
                                              self.shopify_credit_tax_account_id.id or False
            values["notify_customer"] = self.shopify_notify_customer
            values["shopify_activity_type_id"] = self.shopify_activity_type_id and self.shopify_activity_type_id.id \
                                                 or False
            values["shopify_date_deadline"] = self.shopify_date_deadline or False
            values.update({"shopify_user_ids": [(6, 0, self.shopify_user_ids.ids)]})
            values["is_shopify_create_schedule"] = self.is_shopify_create_schedule
            values["sync_product_with_images"] = self.shopify_sync_product_with_images or False
            values["create_shopify_products_webhook"] = self.create_shopify_products_webhook
            values["create_shopify_customers_webhook"] = self.create_shopify_customers_webhook
            values["create_shopify_orders_webhook"] = self.create_shopify_orders_webhook
            values["shopify_default_pos_customer_id"] = self.shopify_default_pos_customer_id.id
            values["last_date_order_import"] = self.last_date_order_import
            values["shopify_last_date_customer_import"] = self.shopify_last_date_customer_import
            values["shopify_last_date_update_stock"] = self.shopify_last_date_update_stock
            values["shopify_last_date_product_import"] = self.shopify_last_date_product_import
            values["payout_last_import_date"] = self.shopify_payout_last_date_import or False
            values["shopify_settlement_report_journal_id"] = self.shopify_settlement_report_journal_id or False
            values['shopify_order_status_ids'] = [(6, 0, self.shopify_order_status_ids.ids)]
            values["auto_fulfill_gift_card_order"] = self.auto_fulfill_gift_card_order
            values["import_order_after_date"] = self.shopify_import_order_after_date
            values["custom_service_product_id"] = self.shopify_custom_service_product_id.id
            values["custom_storable_product_id"] = self.shopify_custom_storable_product_id.id

            product_webhook_changed = customer_webhook_changed = order_webhook_changed = False
            if instance.create_shopify_products_webhook != self.create_shopify_products_webhook:
                product_webhook_changed = True
            if instance.create_shopify_customers_webhook != self.create_shopify_customers_webhook:
                customer_webhook_changed = True
            if instance.create_shopify_orders_webhook != self.create_shopify_orders_webhook:
                order_webhook_changed = True
            instance.write(values)

            if product_webhook_changed:
                instance.configure_shopify_product_webhook()
            if customer_webhook_changed:
                instance.configure_shopify_customer_webhook()
            if order_webhook_changed:
                instance.configure_shopify_order_webhook()

        return res

    @api.model
    def action_shopify_open_basic_configuration_wizard(self):
        """
           Usage: return the action for open the basic configurations wizard
           @Task:   166992 - Shopify Onboarding panel
           @author: Dipak Gogiya
           :return: True
        """
        try:
            view_id = self.env.ref('shopify_ept.shopify_basic_configurations_onboarding_wizard_view')
        except:
            return True
        return self.shopify_res_config_view_action(view_id)

    @api.model
    def action_shopify_open_financial_status_configuration_wizard(self):
        """
           Usage: return the action for open the basic configurations wizard
           @Task:   166992 - Shopify Onboarding panel
           @author: Dipak Gogiya
           :return: True
        """
        try:
            view_id = self.env.ref('shopify_ept.shopify_financial_status_onboarding_wizard_view')
        except:
            return True
        return self.shopify_res_config_view_action(view_id)

    def shopify_res_config_view_action(self, view_id):
        """
           Usage: return the action for open the configurations wizard
           @Task:   166992 - Shopify Onboarding panel
           @author: Dipak Gogiya
           :return: True
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            "shopify_ept.action_shopify_instance_config")
        action_data = {'view_id': view_id.id, 'views': [(view_id.id, 'form')], 'target': 'new',
                       'name': 'Configurations'}
        instance = self.env['shopify.instance.ept'].search_shopify_instance()
        if instance:
            action['context'] = {'default_shopify_instance_id': instance.id}
        else:
            action['context'] = {}
        action.update(action_data)
        return action

    def shopify_save_basic_configurations(self):
        """
           Usage: Save the basic configuration changes in the instance
           @Task:   166992 - Shopify Onboarding panel
           @author: Dipak Gogiya
           :return: True
        """
        instance = self.shopify_instance_id
        if instance:
            basic_configuration_dict = {
                'shopify_company_id': self.shopify_company_id and self.shopify_company_id.id or False,
                'shopify_warehouse_id': self.shopify_warehouse_id and self.shopify_warehouse_id.id or False,
                'auto_import_product': self.auto_import_product or False,
                'sync_product_with_images': self.shopify_sync_product_with_images or False,
                'shopify_sync_product_with': self.shopify_sync_product_with or False,
                'shopify_pricelist_id': self.shopify_pricelist_id and self.shopify_pricelist_id.id or False,
                'shopify_section_id': self.shopify_section_id and self.shopify_section_id.id or False,
                'is_use_default_sequence': self.shopify_is_use_default_sequence,
                'shopify_order_prefix': self.shopify_order_prefix or False,
                'shopify_default_pos_customer_id': self.shopify_default_pos_customer_id.id,
                'apply_tax_in_order': self.shopify_apply_tax_in_order,
                'invoice_tax_account_id': self.shopify_invoice_tax_account_id and
                                          self.shopify_invoice_tax_account_id.id or False,
                'credit_tax_account_id': self.shopify_credit_tax_account_id and
                                         self.shopify_credit_tax_account_id.id or False,
                'import_order_after_date': self.shopify_import_order_after_date,
            }

            instance.write(basic_configuration_dict)
            company = instance.shopify_company_id
            company.set_onboarding_step_done('shopify_basic_configuration_onboarding_state')
        return True

    def shopify_save_financial_status_configurations(self):
        """
            Usage: Save the changes in the Instance.
            @Task:   166992 - Shopify Onboarding panel
            @author: Dipak Gogiya, 22/09/2020
            :return: True
        """
        instance = self.shopify_instance_id
        if instance:
            product_webhook_changed = customer_webhook_changed = order_webhook_changed = False
            if instance.create_shopify_products_webhook != self.create_shopify_products_webhook:
                product_webhook_changed = True
            if instance.create_shopify_customers_webhook != self.create_shopify_customers_webhook:
                customer_webhook_changed = True
            if instance.create_shopify_orders_webhook != self.create_shopify_orders_webhook:
                order_webhook_changed = True

            instance.write({
                'shopify_stock_field': self.shopify_stock_field,
                'last_date_order_import': self.last_date_order_import,
                'notify_customer': self.shopify_notify_customer,
                'shopify_settlement_report_journal_id': self.shopify_settlement_report_journal_id or False,
                'create_shopify_products_webhook': self.create_shopify_products_webhook,
                'create_shopify_customers_webhook': self.create_shopify_customers_webhook,
                'create_shopify_orders_webhook': self.create_shopify_orders_webhook,
            })

            if product_webhook_changed:
                instance.configure_shopify_product_webhook()
            if customer_webhook_changed:
                instance.configure_shopify_customer_webhook()
            if order_webhook_changed:
                instance.configure_shopify_order_webhook()

            company = instance.shopify_company_id
            company.set_onboarding_step_done('shopify_financial_status_onboarding_state')
            financials_status = self.env['sale.auto.workflow.configuration.ept'].search(
                [('shopify_instance_id', '=', instance.id)])
            unlink_for_financials_status = financials_status - self.shopify_financial_status_ids
            unlink_for_financials_status.unlink()
        return True
