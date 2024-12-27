# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, Command, _
from odoo.exceptions import ValidationError
from ..tools.shopify_api import ShopifyApi
from ..tools.shopify_api_v2 import ShopifyApi as ShopifyApiv2

_logger = logging.getLogger(__name__)


class ShopifyQueue(models.Model):
    _name = 'shopify.queue'
    _description = 'Shopify Queue'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    """
        All imported operations should be
        stage on this queue so that it can handle multiple
        record with only single process. This can track all
        the imported records coming from shopify.

        Initially, all imported records are directly created
        to their respective model.
    """
    name = fields.Char(readonly=True, required=True, default=lambda self: _('New'))
    status = fields.Selection(
        [("draft", "Draft"), ("complete", "Completed"), ("fail", "Failed")],
        string="Status", default="draft")

    instance_id = fields.Many2one('shopify.instance', string="Shopify Instance", required=True)
    do_not_update_existing = fields.Boolean(string='Do Not Update Existing Product')

    no_of_record = fields.Integer(compute='_compute_record_count', string='No. of Record')
    no_of_draft = fields.Integer(compute='_compute_record_count', string='No. of Draft')
    no_of_failed = fields.Integer(compute='_compute_record_count', string='No. of Failed')
    no_of_cancelled = fields.Integer(compute='_compute_record_count', string='No. of Cancelled')
    no_of_done = fields.Integer(compute='_compute_record_count', string='No. of Done')

    queue_line = fields.One2many('shopify.queue.line', 'line_id', string='Product Lines', copy=True)

    queue_type = fields.Char()
    mismatch_log_ids = fields.One2many('shopify.queue.mismatch.log', 'queue_id', string='Mismatch Logs')

    @api.model
    def create(self, vals):
        res = super().create(vals)
        operation_name = self.env.context.get('operation_name', _('New'))
        _logger.info('Shopify Operation Name: %s', operation_name)
        if operation_name == 'import_product':
            res['name'] = self.env['ir.sequence'].next_by_code(
                'shopify.import.product.queue'
            ) or _('New')
        elif operation_name == 'import_customer':
            res['name'] = self.env['ir.sequence'].next_by_code(
                'shopify.import.customer.queue'
            ) or _('New')
        elif operation_name == 'import_order':
            res['name'] = self.env['ir.sequence'].next_by_code(
                'shopify.import.order.queue'
                ) or _('New')
        elif operation_name == 'import_location':
            res['name'] = self.env['ir.sequence'].next_by_code(
                'shopify.import.location.queue'
                ) or _('New')
        elif operation_name == 'import_stock':
            res['name'] = self.env['ir.sequence'].next_by_code(
                'shopify.import.stock.queue'
                ) or _('New')
        return res

    # Will migrate this to another model to avoid redundancy
    def _get_default_instance_id(self):
        setting = self.env['ir.config_parameter'].sudo().get_param('sk_shopify_connector_for_odoo.shopify_instance_id') or False
        if setting:
            return self.env['shopify.instance'].browse(int(setting))
        return setting

    @api.model
    def _create_queue_records_from_cron(self, operation_name):

        def get_customer_name(customer):
            return f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()

        def get_latest_shopify_id(model, field):
            record = self.env[model].search_read(
                [(field, '!=', False)], [field],
                limit=1, order=f"{field} DESC"
            )
            return record[0][field] if record else None

        def update_since_id(config, model, field):
            latest_id = get_latest_shopify_id(model, field)
            if latest_id:
                config['params'].update({'since_id': int(latest_id)})

        # Default instance ID
        instance_id = self._get_default_instance_id()

        # Base parameters and mappings for each operation
        operation_config = {
            'import_product': {
                'queue_type': 'product',
                'api_method': '_import_products',
                'params': {'status': 'active', 'limit': 250},
                'key_field': 'id',
                'data_key': 'products',
                'model': 'product.template',
                'field': 'shopify_product_id'
            },
            'import_customer': {
                'queue_type': 'customer',
                'api_method': '_import_customers',
                'params': {},
                'key_field': 'id',
                'data_key': 'customers',
                'model': 'res.partner',
                'field': 'shopify_user_id'
            },
            'import_order': {
                'queue_type': 'order',
                'api_method': '_import_orders',
                'params': {},
                'key_field': None,
                'data_key': 'orders',
                'model': 'sale.order',
                'field': 'shopify_id'
            },
            'import_location': {
                'queue_type': 'location',
                'api_method': '_import_locations',
                'params': {'active': True},
                'key_field': 'id',
                'data_key': 'locations'
            },
            'import_stock': {
                'queue_type': 'stock',
                'api_method': '_import_stocks',
                'params': {
                    'ids': self.env['product.product'].search(
                        [('shopify_inventory_id', '!=', False)], limit=50
                    ).mapped('shopify_inventory_id'),
                },
                'key_field': 'inventory_item_id',
                'data_key': 'inventory_levels'
            }
        }

        config = operation_config.get(operation_name)
        if not config:
            raise ValidationError(_('Invalid operation name'))

        # Update params based on operation
        if operation_name in ['import_product', 'import_order', 'import_customer']:
            update_since_id(config, config['model'], config['field'])

        elif operation_name == 'import_stock':
            inventory_item_list = self.env['product.product'].search(
                [('shopify_inventory_id', '!=', False)]
            )
            if inventory_item_list:
                list_of_ids = inventory_item_list.mapped('shopify_inventory_id')
                if list_of_ids:
                    config['params']['inventoryitemids'] = ','.join(map(str, list_of_ids))
                if self.location_id:
                    config['params']['location_ids'] = int(self.location_id.shopify_location_id)

        api_method = getattr(ShopifyApi(instance_id), config['api_method'])
        api_data = api_method(params=config.get('params', {}))

        if api_data:
            queue_lines = [
                {
                    'shopify_id': data.get(config['key_field']),
                    'name': data.get('name') or get_customer_name(data),
                    'json_data': data,
                }
                for data in api_data[config['data_key']]
            ]

            data_queue = {
                'instance_id': instance_id,
                'queue_type': config['queue_type'],
                'queue_line': [Command.create(queue) for queue in queue_lines]
            }

            self.with_context(operation_name=operation_name).create(data_queue)

    @api.model
    def _process_queue_from_cron(self, queue_type):
        queues = self.search([('status', '=', 'draft'), ('queue_type', '=', queue_type)])

        for queue in queues:
            queue.process_queue()

    def process_queue(self):
        operation_map = {
            'product': '_create_product_from_queue',
            'customer': '_create_customer_from_queue',
            'order': '_create_order_from_queue',
            'location': '_create_location_from_queue',
            'stock': '_create_stock_from_queue',
        }

        operation_name = operation_map.get(self.queue_type)
        if not operation_name:
            return False

        for line in self.queue_line:
            if hasattr(line, operation_name):
                getattr(line, operation_name)()
            else:
                _logger.warning(f"Queue line {line.id} does not support operation '{operation_name}'")

        user = self.env.user.name
        note = f'{user} set the process queue manually.'
        self.create_activity(note=note)

        if self.queue_line:
            self.write({'status': 'complete'})
        return True

    def set_to_complete(self):
        self.write({'status': 'complete'})
        lines = self.queue_line
        message = 'User manually set all the data to complete.'
        for line in lines:
            self.log_mismatch('sync_error', message, line.shopify_id)
            line.write({'status': 'complete'})

        user = self.env.user.name
        note = f'{user} set the queue to completed.'
        self.create_activity(note=note)
        return True

    @api.depends('queue_line', 'queue_line.status')
    def _compute_record_count(self):
        for line in self:
            queue_lines = line.queue_line
            total_count = len(queue_lines)
            draft_count = failed_count = cancelled_count = done_count = 0

            for q_line in queue_lines:
                if q_line.status == 'draft':
                    draft_count += 1
                elif q_line.status == 'fail':
                    failed_count += 1
                elif q_line.status == 'cancel':
                    cancelled_count += 1
                elif q_line.status == 'done':
                    done_count += 1

            line.no_of_record = total_count
            line.no_of_draft = draft_count
            line.no_of_failed = failed_count
            line.no_of_cancelled = cancelled_count
            line.no_of_done = done_count

    def log_mismatch(self, error_type, message, data=None):
        self.env['shopify.queue.mismatch.log'].create({
            'queue_id': self.id,
            'error_type': error_type,
            'message': message,
            'data': data,
        })

    def create_activity(self, note):
        users = self.env.ref('sk_shopify_connector_for_odoo.group_shopify_admin').users
        for user in users:
            self.activity_schedule('sk_shopify_connector_for_odoo.mail_act_queue_operation',
                                   user_id=user.id, note=note)

    @api.model
    def retrieve_dashboard(self):
        """ This function returns the values to populate the custom dashboard in
            the shopify queue views.
        """

        result = {
            'all_draft': self.search_count([('status', '=', 'draft')]),
            'all_complete': self.search_count([('status', '=', 'complete')]),
            'all_fail': self.search_count([('status', '=', 'fail')]),
        }

        return result


class ShopifyQueueLine(models.Model):
    _name = 'shopify.queue.line'
    _description = 'Shopify Queue Lines'

    shopify_id = fields.Char(string='Shopify ID')
    name = fields.Char()
    image_import_state = fields.Selection(
            [("no_import", "Don't Import"),
             ("pending", "Pending"),
             ("complete", "Completed")],
            string="Image Import State", default="pending")
    status = fields.Selection(
            [("draft", "Draft"),
             ("complete", "Completed"),
             ("fail", "Failed"),
             ("cancel", "Canceled"),
             ("done", "Done")],
            string="Status", default="draft")
    json_data = fields.Json(string='Shopify Response')

    line_id = fields.Many2one('shopify.queue', string='Order Reference',
                              index=True, required=True, ondelete='cascade')

    instance_id = fields.Many2one('shopify.instance', related="line_id.instance_id", string="Shopify Instance", copy=False)

    def __create_record_from_queue(self, model, search_field, create_method, data_key='legacyResourceId', skip_check_records=False, **kwargs):

        self.ensure_one()
        record_data = self.json_data
        model_obj = self.env[model]
        record_id = record_data.get(data_key)

        existing_records = model_obj.search([(search_field, '=', record_id)]) if record_id and not skip_check_records else False

        if existing_records:
            self.line_id.log_mismatch('validation_error', 'Found an existing record', self.shopify_id)
            self.write({'status': 'cancel'})
            return

        try:
            created_record = getattr(model_obj, create_method)(record_data, **kwargs)
            status = 'done' if created_record else 'fail'

            # Add mismatch stock logs
            if skip_check_records and model == 'product.product':
                if isinstance(created_record, dict):
                    status = 'fail'
                    self.line_id.log_mismatch('data_error', created_record.get('error'), self.shopify_id)

            if not created_record:
                self.line_id.log_mismatch('data_error', 'There is something wrong in creating data.', self.shopify_id)

        except Exception as err:
            _logger.info('Create Record Failed %s', err)
            self.line_id.log_mismatch('data_error', 'There is something wrong in creating data.', self.shopify_id)
            status = 'fail'

        # Update the queue line status
        self.write({'status': status})

    def _create_product_from_queue(self):
        self.__create_record_from_queue(
            model='product.template',
            search_field='shopify_product_id',
            create_method='create_product_from_shopify',
            instance_id=self.instance_id.id
        )

    def _create_customer_from_queue(self):
        self.__create_record_from_queue(
            model='res.partner',
            search_field='shopify_user_id',
            create_method='create_customer_from_shopify',
            instance_id=self.instance_id.id
        )

    def _create_order_from_queue(self):
        self.__create_record_from_queue(
            model='sale.order',
            search_field='shopify_id',
            create_method='create_order_from_shopify',
            instance_id=self.instance_id.id
        )

    def _create_location_from_queue(self):
        self.__create_record_from_queue(
            model='shopify.location',
            search_field='shopify_location_id',
            create_method='create_location_from_shopify',
            instance_id=self.instance_id.id
        )

    def _create_stock_from_queue(self):
        self.__create_record_from_queue(
            model='product.product',
            search_field='inventory_graphql_id',
            create_method='create_stock_from_shopify',
            skip_check_records=True,
        )

    @api.model
    def auto_process_queue_cron(self):
        """ Process Queue using Import Scheduler"""

        # Only Process Queue that are set in draft
        domain = [('status', '=', 'draft')]
        draft_queues = self.env['shopify.queue'].search(domain)

        for queue in draft_queues:
            _logger.info('Processing this Queue: %s', queue.name)
            queue.process_queue()
            _logger.info('Queue Status: %s', queue.status)
