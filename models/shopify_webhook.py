# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from ..tools.shopify_api_v2 import ShopifyApi

_logger = logging.getLogger(__name__)


class ShopifyWebhook(models.Model):
    _name = 'shopify.webhook'
    _description = 'Shopify Webhook'

    instance_id = fields.Many2one(comodel_name='shopify.instance')
    state = fields.Selection([('active', 'Active'),
                              ('inactive', 'Inactive')],
                             default='inactive',
                             string='State')
    webhook_action = fields.Selection([('PRODUCTS_CREATE', 'When Product is Created.'),
                                       ('PRODUCTS_UPDATE', 'When Product is Updated'),
                                       ('PRODUCTS_DELETE', 'When Product is Delete'),
                                       ('ORDERS_UPDATED', 'When Order is Updated'),
                                       ('CUSTOMERS_CREATE', 'When Customer is Created'),
                                       ('CUSTOMERS_UPDATE', 'When Customer is Updated')])
    webhook_id = fields.Char(string='Webhook ID in Shopify')
    webhook_name = fields.Char(string='Name', required=True)
    delivery_url = fields.Text(string='Delivery URL', required=True)

    @api.model
    def create(self, vals):
        webhook_action = vals.get('webhook_action')
        delivery_url = vals.get('delivery_url')
        instance_id = vals.get('instance_id')

        if webhook_action and delivery_url:
            payload = {
                "topic": webhook_action,
                "webhookSubscription": {
                    "callbackUrl": delivery_url,
                    "format": "JSON"
                }
            }
            instance = self.env['shopify.instance'].browse(instance_id)
            webhook_resp = ShopifyApi(instance).import_raw_data(
                query_name='webhookSubscriptionCreate',
                variables=payload
            )
            _logger.info('Webhook Response Test %s', webhook_resp)
            webhook_data = webhook_resp.get('data', {}).get('webhookSubscriptionCreate', {}).get('webhookSubscription', {})
            webhook_id = webhook_data.get('id')

            if webhook_id:
                vals.update({
                    'webhook_id': webhook_id,
                    'state': 'active'
                })
                _logger.info('Webhook ID created: %s', webhook_id)
            else:
                _logger.warning('Failed to create webhook: %s', webhook_resp)
        _logger.info('Webhook creation payload: %s', vals)
        return super().create(vals)

    def write(self, vals):
        _logger.info('Updating Webhook: Values to update: %s, Current Record: %s', vals, self)
        if any(field in vals for field in ('instance_id', 'webhook_action')):
            raise ValidationError(_('You cannot modify "Instance" or "Webhook Action" once the webhook has been created. Only the "Delivery URL" can be updated.'))

        if 'delivery_url' in vals and self.webhook_id:
            payload = {
                "id": self.webhook_id,
                "webhookSubscription": {
                    "callbackUrl": vals['delivery_url']
                }
            }

            webhook_resp = ShopifyApi(self.instance_id).import_raw_data(
                query_name='WebhookSubscriptionUpdate',
                variables=payload
            )
            _logger.info('Webhook update response: %s', webhook_resp)

        return super().write(vals)

    def unlink(self):
        for record in self:
            _logger.info('Deleting Webhook: %s', record)

            if record.webhook_id:
                payload = {"id": record.webhook_id}

                response = ShopifyApi(record.instance_id).import_raw_data(
                    query_name='webhookSubscriptionDelete',
                    variables=payload
                )

                _logger.info('Response from Webhook Deletion: %s', response)
        return super().unlink()

    @api.constrains('delivery_url')
    def _check_delivery_url(self):
        """Ensure the delivery URL is a valid URL format."""
        for record in self:
            if record.delivery_url and not record.delivery_url.startswith(('https://')):
                raise ValidationError(_("The delivery URL must start with 'https://'."))

    @api.constrains('webhook_id')
    def _check_webhook_id(self):
        """Ensure the webhook ID is unique across active instances."""
        for record in self:
            if record.webhook_id:
                existing_webhook = self.search([
                    ('webhook_id', '=', record.webhook_id),
                    ('id', '!=', record.id),
                    ('state', '=', 'active'),
                ], limit=1)
                if existing_webhook:
                    raise ValidationError(_("The webhook ID must be unique for active webhooks."))
