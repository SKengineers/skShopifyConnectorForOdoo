# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api
from ..tools.shopify_api_v2 import ShopifyApi

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    shopify_product_id = fields.Char(related='product_tmpl_id.shopify_product_id',
                                     string='Shopify Product ID', copy=False)
    product_graphql_id = fields.Char(string='Product GraphQL ID', copy=False)
    product_product_id = fields.Char(string='Shopify ID', copy=False)
    shopify_inventory_id = fields.Char('Shopify Inventory ID')
    inventory_graphql_id = fields.Char('Inventory GraphQL ID')
    shopify_instance_id = fields.Many2one('shopify.instance', string="Shopify Instance")
    compare_at_price = fields.Float('Compare At Price')

    def _export_product_stock_to_shopify(self, instance, location_id):
        self.ensure_one()

        inventory_payload = {
            'input': {
                'name': 'available',
                'ignoreCompareQuantity': True,
                'reason': 'correction', # TODO: Add this as options in wizard
                'quantities': [{
                    'inventoryItemId': self.inventory_graphql_id,
                    'locationId': location_id,
                    'quantity': int(self.qty_available),
                }]
            }
        }
        exported_locations = ShopifyApi(instance).export_data(query_name='inventorySetQuantities',
                                                              payload=inventory_payload,
                                                              key_value='inventoryAdjustmentGroup')
        return exported_locations

    @api.model
    def create_stock_from_shopify(self, stock):

        available_qty = self.get_on_hand_quantity(stock)
        if available_qty > 0:
            # TODO: Added useful configs here.
            warehouse = self.env['stock.warehouse'].search(
                [('company_id', '=', self.env.company.id)], limit=1
            )

            product_id = self.search(
                [('inventory_graphql_id', '=', stock.get('id'))],
                limit=1)

            if product_id and warehouse:
                self.env['stock.quant'].with_context(inventory_mode=True).create({
                    'product_id': product_id.id,
                    'location_id': warehouse.lot_stock_id.id,
                    'inventory_quantity': available_qty,
                })._apply_inventory()
                return True
        else:
            return {'error': 'On hand quantity must be in positive value.'}

        return False

    def get_on_hand_quantity(self, inventory_item):
        """
        Get the 'on_hand' quantity from an inventory item.

        :param inventory_item: A dictionary containing the inventory item data.
        :return: The 'on_hand' quantity, or None if not found.
        """
        inventory_levels = inventory_item.get('inventoryLevels', {}).get('edges', [])

        for level in inventory_levels:
            quantities = level.get('node', {}).get('quantities', [])
            for quantity in quantities:
                if quantity.get('name') == 'on_hand':
                    return quantity.get('quantity')
        return None
