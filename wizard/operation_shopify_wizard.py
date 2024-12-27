# -*- coding: utf-8 -*-

import logging

from odoo import fields, models, api, Command,  _
from ..tools.shopify_api_v2 import ShopifyApi
from ..tools.product_importer import ProductDataImporter
from odoo.exceptions import ValidationError
from odoo.addons.web.controllers.utils import clean_action

_logger = logging.getLogger(__name__)

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DATE_FORMAT = "%Y-%m-%d"


class OperationShopifyWizard(models.TransientModel):
    _name = 'operation.shopify.wizard'

    company_id = fields.Many2one(comodel_name='res.company',
                                 default=lambda self: self.env.company)
    shopify_image = fields.Boolean(string="Image")
    instance_id = fields.Many2one(comodel_name="shopify.instance",
                                  string="Instance", required=True)
    detail = fields.Boolean(string="Details", default=False)
    operation_type = fields.Selection(
        [("import_product", "Import Product"),
         ("export_product", "Export Product"),
         ("export_product_layer", "Export Product to Middle Layer"),
         ('map_product', "Map Products"),
         ("import_customer", "Import Customer"),
         ("import_ship_order", "Import Shipped Order"),
         ("import_unship_order", "Import Unshipped Order"),
         ("import_specific_order", "Import Specific Order"),
         ("import_cancel_order", "Import Cancel Order"),
         ("export_order", "Export Order"),
         ("import_location", "Import Location"),
         ("import_stock", "Import Stock"),
         ("export_stock", "Export Stock"),
         ("import_payout_report", "Import Payout Report")
         ],
        string="Operations", required=True)

    customer_line_ids = fields.Many2many(comodel_name="res.partner", string="Customers")
    product_tmpl_line_ids = fields.Many2many(comodel_name="product.template", string="Products")
    product_product_line_ids = fields.Many2many(comodel_name="product.product", string="Product Variants")
    sale_order_line_ids = fields.Many2many(comodel_name="sale.order", string="Orders")
    location_id = fields.Many2one(comodel_name="shopify.location",
                                  string="Shopify Location")

    csv_file = fields.Binary("CSV file")
    csv_filename = fields.Char()

    # Add Filtering
    import_based_on_date = fields.Selection([
            ("create_date", "Create Date"),
            ("update_date", "Update Date"),
        ])
    is_import_draft_product = fields.Boolean(string="Import Draft Products")

    # Datetime Filter
    from_datetime = fields.Datetime()
    to_datetime = fields.Datetime(default=fields.Datetime.now)

    # Date Filter
    from_date = fields.Date()
    to_date = fields.Date(default=fields.Date.today)

    skip_existing_product = fields.Boolean(string="Do Not Update Existing Products")
    order_ids = fields.Char(string='Order IDs')

    # Hide fields
    is_sync_options = fields.Boolean(compute='_compute_display_sync_options')

    @api.depends('operation_type')
    def _compute_display_sync_options(self):
        hidden_operation_type = [
            'export_product_layer',
            'export_product',
            'import_customer',
            'import_location',
            'import_stock',
            'export_stock',
            'export_order',
        ]

        if self.operation_type in hidden_operation_type:
            self.is_sync_options = True
        elif not self.operation_type:
            self.is_sync_options = True
        else:
            self.is_sync_options = False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        company_id = res.get('company_id')
        if company_id:
            company = self.env['res.company'].browse(company_id)
            res['instance_id'] = company.shopify_instance_id.id

        active_ids = self.env.context.get('active_ids')
        operation_type = self.env.context.get('default_operation_type')

        if active_ids and operation_type == 'export_product_layer':
            res['product_tmpl_line_ids'] = [Command.set(active_ids)]
        elif active_ids and operation_type == 'export_stock':
            res['product_product_line_ids'] = [Command.set(active_ids)]
        elif active_ids and operation_type == 'export_order':
            res['sale_order_line_ids'] = [Command.set(active_ids)]
        return res

    def execute_operation(self):
        response = None
        operation_mapping = {
                'import_product': self._import_product_queue,
                'export_product': self._export_product,
                'export_product_layer': self._export_product_to_middle_layer,
                'map_product': self._map_products,
                'import_customer': self._import_customer_queue,
                'import_ship_order': self._import_shipped_orders,
                'import_unship_order': self._import_unshipped_orders,
                'import_cancel_order': self._import_cancel_order_queue,
                'import_specific_order': self._import_specific_orders,
                'export_order': self._export_order,
                'import_location': self._import_location,
                'export_stock': self._export_stock,
                'import_stock': self._import_stock,
                'import_payout_report': self._import_payout_report,
            }

        operation_func = operation_mapping.get(self.operation_type)

        if operation_func:
            response = operation_func()
        else:
            raise ValidationError(_('Invalid operation type'))

        return response

    def _import_product_queue(self):
        date_field = 'created_at' if self.import_based_on_date == 'create_date' else 'updated_at' if self.import_based_on_date == 'update_date' else None

        # Build query based on date range if applicable
        query_list = []
        if date_field:
            if self.from_datetime:
                query_list.append(f"{date_field}:>={self.from_datetime.strftime(DATETIME_FORMAT)}")
            if self.to_datetime:
                query_list.append(f"{date_field}:<={self.to_datetime.strftime(DATETIME_FORMAT)}")

        if self.is_import_draft_product:
            query_list.append('status:ACTIVE,DRAFT')
        query = ' AND '.join(query_list)
        variables = {'query': query} if query else None

        imported_products = ShopifyApi(self.instance_id).import_data(query_name='GetProducts',
                                                                        extra_variables=variables,
                                                                        key_value='products')

        return self._create_queue(
            queue_type='product',
            imported_data=imported_products,
            operation_name='import_product',
            key_field='legacyResourceId',
            name_function=lambda product: product.get('title')
        )

    def _export_product(self):
        message_type = 'danger'
        message = _('No products been exported.')

        domain = [('status', '=', 'unpublish'), ('is_export', '=', False)]
        shopify_products = self.env['shopify.product'].search(domain)

        if not shopify_products:
            return self.get_notification(message_type, message)

        for product in shopify_products:
            response = product.export_to_shopify()
            product.write({'status': 'publish', 'is_export': True})
            _logger.info('Products Exported: %s', response)

            message_type = 'success'
            message = _(
                "Products have been imported.\n"
                "See the imported Shopify products."
            )
        return self.get_notification(message_type, message, reload=True)

    def _export_product_to_middle_layer(self):
        message_type = 'danger'
        message = 'No products been created.'

        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            return self.get_notification(message_type, message)

        products = self.env['product.template'].browse(active_ids)
        shopify_products = self.env['shopify.product'].search([('product_tmpl_id', 'in', products.ids)])

        product_tmpl_ids = shopify_products.mapped('product_tmpl_id').ids
        # Filter all the products Shopify Product Id
        filtered_products = products.filtered(lambda item: not item.shopify_product_id and
                                              item.id not in product_tmpl_ids)

        if not filtered_products:
            return self.get_notification(message_type, message)

        vals_list = []
        for product in filtered_products:
            vals = {
                'name': product.name,
                'shopify_instance_id': self.instance_id.id,
                'product_tmpl_id': product.id,
                'product_category_id': product.categ_id.id,
            }

            if self.shopify_image and product.image_1920:
                vals['shopify_images'] = [Command.create({
                    'name': product.name,
                    'product_tmpl_id': product.id,
                    'template_image': product.image_1920,
                })]
            vals_list.append(vals)

        # Create Shopify products and set the success message
        self.env['shopify.product'].create(vals_list)
        message_type = 'success'
        message = 'Products created successfully.'

        return self.get_notification(message_type, message)

    def _map_products(self):
        importer = ProductDataImporter(self.env)
        data = importer.import_data(self.csv_file, self.csv_filename)

        if data:
            message_type = 'success'
            message = 'Products created successfully.'
        else:
            message_type = 'failed'
            message = 'Failed to create a product.'

        return self.get_notification(message_type, message)

    def _import_customer_queue(self):
        variables = {'first': 50}
        imported_customers = ShopifyApi(self.instance_id).import_data(query_name='GetCustomers',
                                                                         extra_variables=variables,
                                                                         key_value='customers')

        def get_customer_name(customer):
            return f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()

        return self._create_queue(
            queue_type='customer',
            imported_data=imported_customers,
            operation_name='import_customer',
            key_field='legacyResourceId',
            name_function=get_customer_name
        )

    def _import_shipped_orders(self):

        query_list = []

        if self.from_datetime:
            query_list.append(f"created_at:>={self.from_datetime.strftime(DATE_FORMAT)}")
        if self.to_datetime:
            query_list.append(f"created_at:<={self.to_datetime.strftime(DATE_FORMAT)}")

        query_list.append('fulfillment_status:fulfilled')
        query = ' AND '.join(query_list)
        variables = {'query': query} if query else None
        imported_orders = ShopifyApi(self.instance_id).import_data(query_name='GetOrders',
                                                                      extra_variables=variables,
                                                                      key_value='orders')

        return self._create_queue(
            queue_type='order',
            imported_data=imported_orders,
            operation_name='import_order',
            key_field='legacyResourceId',
            name_function=lambda order: order.get('name')
        )

    def _import_unshipped_orders(self):

        query_list = []

        if self.from_datetime:
            query_list.append(f"created_at:>={self.from_datetime.strftime(DATE_FORMAT)}")
        if self.to_datetime:
            query_list.append(f"created_at:<={self.to_datetime.strftime(DATE_FORMAT)}")

        query_list.append('fulfillment_status:unfulfilled')
        query = ' AND '.join(query_list)
        variables = {'query': query} if query else None

        imported_orders = ShopifyApi(self.instance_id).import_data(query_name='GetOrders',
                                                                      extra_variables=variables,
                                                                      key_value='orders')

        return self._create_queue(
            queue_type='order',
            imported_data=imported_orders,
            operation_name='import_order',
            key_field='legacyResourceId',
            name_function=lambda order: order.get('name')
        )

    def _import_specific_orders(self):
        order_ids_list = [
            int(order_id) for order_id in self.order_ids.split(',') if order_id.strip().isdigit()
        ]

        if not order_ids_list:
            return False

        query_argument = " OR ".join([f"id:{order_id}" for order_id in order_ids_list])
        variables = {'first': 50, 'query': query_argument}

        imported_orders = ShopifyApi(self.instance_id).import_data(query_name='GetOrders',
                                                                         extra_variables=variables,
                                                                         key_value='orders')

        return self._create_queue(
            queue_type='order',
            imported_data=imported_orders,
            operation_name='import_order',
            key_field='legacyResourceId',
            name_function=lambda order: order.get('name')
        )

    def _import_cancel_order_queue(self):

        query_list = []
        if self.from_datetime:
            query_list.append(f"created_at:>={self.from_datetime.strftime(DATE_FORMAT)}")
        if self.to_datetime:
            query_list.append(f"created_at:<={self.to_datetime.strftime(DATE_FORMAT)}")

        query_list.append('status:cancelled')
        query = ' AND '.join(query_list)
        variables = {'query': query} if query else None
        imported_orders = ShopifyApi(self.instance_id).import_data(query_name='GetOrders',
                                                                      extra_variables=variables,
                                                                      key_value='orders')

        return self._create_queue(
            queue_type='order',
            imported_data=imported_orders,
            operation_name='import_order',
            key_field='legacyResourceId',
            name_function=lambda order: order.get('name')
        )

    def _export_order(self):
        message_type = 'danger'
        message = _('No order been imported.')

        domain = [('shopify_id', '=', False),
                  ('shopify_order_no', '=', False),
                  ('is_shopify_order', '=', False),
                  ('is_exported', '=', False),
                  ('id', 'in', self.sale_order_line_ids.ids)]
        shopify_orders = self.env['sale.order'].search(domain)

        for order in shopify_orders:
            shopify_order = order.export_to_shopify(self.instance_id)
            response = shopify_order.get('data', {}).get('draftOrderCreate', {}).get('draftOrder')
            # Rewrite the existing order here
            if response:
                order.write({
                    'is_shopify_order': True,
                    'shopify_id': response.get('legacyResourceId'),
                    'shopify_graphql_id': response.get('id'),
                    'shopify_order_no': response.get('name')
                })
            message_type = 'success'
            message = _('Order has been imported.')

        return self.get_notification(message_type, message)

    def _import_location(self):
        variables = {'first': 30}
        imported_locations = ShopifyApi(self.instance_id).import_data(query_name='GetLocations',
                                                                         extra_variables=variables,
                                                                         key_value='locations')

        def get_location_name(location):
            return location.get('name')

        return self._create_queue(
            queue_type='location',
            imported_data=imported_locations,
            operation_name='import_location',
            key_field='legacyResourceId',
            name_function=get_location_name
        )

    def _import_stock(self):
        variables = {}
        imported_stocks = ShopifyApi(self.instance_id).import_data(query_name='GetinventoryItems',
                                                                      extra_variables=variables,
                                                                      key_value='inventoryItems')

        def get_inventory_id(stock):
            return stock.get('sku') or stock.get('variant', {}).get('displayName')

        return self._create_queue(
            queue_type='stock',
            imported_data=imported_stocks,
            operation_name='import_stock',
            key_field='legacyResourceId',
            name_function=get_inventory_id
        )

    def _export_stock(self):
        message_type = 'danger'
        message = _('No stocks been imported.')

        if self.product_product_line_ids:
            for product in self.product_product_line_ids:
                product._export_product_stock_to_shopify(self.instance_id, self.location_id.graphql_id)
                message_type = 'success'
                message = _('Stock Level has been exported.')

        return self.get_notification(message_type, message)

    def _import_payout_report(self):
        query_list = []

        if self.from_datetime:
            query_list.append(f"payout_date:>={self.from_date.strftime(DATE_FORMAT)}")
        if self.to_datetime:
            query_list.append(f"payout_date:<={self.to_date.strftime(DATE_FORMAT)}")

        query = ' AND '.join(query_list)
        variables = {'first': 50}

        if query:
            variables.update({'query': query})

        imported_payout_data = ShopifyApi(self.instance_id).import_raw_data(query_name='GetPayoutReport',
                                                                            variables=variables)

        created_payout = self.env['shopify.payout.report'].with_context(payout_date=self.to_datetime.date()).create_payout_report_from_shopify(self.instance_id.id, imported_payout_data)

        if created_payout:
            view_id = self.env.ref('sk_shopify_connector_for_odoo.shopify_payout_report_form_view').id
            return self._get_return_action(res_id=created_payout.id,
                                           view_name='Payout Report',
                                           view_id=view_id,
                                           model_name='shopify.payout.report')

        message_type = 'danger'
        message = _('No {} been imported.'.format('Payout'))
        return self.get_notification(message_type, message)

    def get_notification(self, message_type, message, reload=False):
        if reload:
            next_action = {'type': 'ir.actions.client', 'tag': 'reload'}
        else:
            next_action = {'type': 'ir.actions.act_window_close'}

        return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': message_type,
                    'message': message,
                    'sticky': False,
                    'next': next_action,
                }
            }

    def _get_return_action(self, res_id=False, view_name='Queue', view_id=False, model_name=False):
        if not view_id:
            view_id = self.env.ref('sk_shopify_connector_for_odoo.shopify_queue_form_view').id
        if not model_name:
            model_name = 'shopify.queue'

        action = {
            'type': 'ir.actions.act_window',
            'name': _(view_name),
            'res_model': model_name,
            'view_mode': 'form',
            'views': [[view_id, 'form']],
        }

        if res_id:
            action['res_id'] = res_id

        return clean_action(action, self.env)

    def _create_queue(self, queue_type, imported_data, operation_name, key_field, name_function):
        message_type = 'danger'
        message = _('No {} been imported.'.format(queue_type))

        if not imported_data:
            return self.get_notification(message_type, message)

        queue_lines = []
        for data in imported_data:
            node = data.get('node')
            if node:
                queue_lines.append({
                    'shopify_id': node.get(key_field),
                    'name': name_function(node),
                    'json_data': node,
                })

        data_queue = {
            'instance_id': self.instance_id.id,
            'queue_type': queue_type,
            'queue_line': [Command.create(queue) for queue in queue_lines]
        }

        queue_obj = self.env['shopify.queue'].with_context(operation_name=operation_name)
        created_queue = queue_obj.create(data_queue)

        if created_queue:
            return self._get_return_action(res_id=created_queue.id)

        return self.get_notification(message_type, message)
