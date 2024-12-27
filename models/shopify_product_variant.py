# -*- coding: utf-8 -*-

import logging
import base64

from odoo import models, fields, api
from ..tools.shopify_api_v2 import ShopifyApi

_logger = logging.getLogger(__name__)


class ShopifyProductVariant(models.Model):
    _name = 'shopify.product.variant'
    _description = 'Shopify Product Variant'

    name = fields.Char(string='Title')
    active = fields.Boolean(string='Active')
    default_code = fields.Char(string='Default Code')
    display_name = fields.Char(string='Display Name')
    exported_in_shopify = fields.Char(string='Exported in Shopify')
    inventory_item_id = fields.Char('Shopify Inventory ID', required=True)
    inventory_graphql_id = fields.Char('GraphQL Inventory ID', required=True)
    shopify_product_id = fields.Many2one('shopify.product', string="Shopify Product")
    shopify_instance_id = fields.Many2one('shopify.instance', string='Shopify Instance', required=True)
    product_id = fields.Many2one('product.product', string='Product')
    sequence = fields.Integer(string='Position')
    variant_id = fields.Char('Shopify Product Variant ID')
    variant_graphql_id = fields.Char('Shopify Product Variant GraphQL ID')
