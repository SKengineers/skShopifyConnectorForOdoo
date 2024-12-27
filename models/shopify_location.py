# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class ShopifyLocations(models.Model):
    _name = 'shopify.location'
    _description = 'Shopify Locations'

    name = fields.Char('Name', required=True)
    shopify_location_id = fields.Char('Shopify Location ID')
    graphql_id = fields.Char('GraphQL ID')

    is_shopify = fields.Boolean(default=False, string="Is shopify")
    is_active = fields.Boolean(default=True)
    is_legacy = fields.Boolean('Is Legacy Location')

    shopify_instance_id = fields.Many2one('shopify.instance', string="Shopify Instance")    
    import_stock_to_warehouse = fields.Many2one('stock.warehouse', string='Warehouse to Import Stock')

    @api.model
    def create_location_from_shopify(self, location, instance_id):
        data_location = {
            'name': location.get('name'),
            'shopify_location_id': location.get('legacyResourceId'),
            'graphql_id': location.get('id'),
            'is_shopify': True,
            'is_active': location.get('isActive'),
            'is_legacy': location.get('legacy'),
            'shopify_instance_id': instance_id,
        }
        return self.create(data_location)
