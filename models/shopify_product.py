# -*- coding: utf-8 -*-

import logging
import base64
import shopify

from odoo import models, fields, api
from ..tools.shopify_api_v2 import ShopifyApi

_logger = logging.getLogger(__name__)


class ShopifyProduct(models.Model):
    _name = 'shopify.product'
    _description = 'Shopify Product'

    name = fields.Char(string='Name')
    shopify_instance_id = fields.Many2one('shopify.instance', string="Shopify Instance", required=True)
    product_tmpl_id = fields.Many2one('product.template', string="Product Template")
    product_category_id = fields.Many2one('product.category', string="Product Category")
    status = fields.Selection(
        [("publish", "Published"), ("unpublish", "Unpublished")],
        string="Status", default="unpublish")
    is_export = fields.Boolean(string='Exported in Shopify', default=False)
    product_body_html = fields.Html()

    shopify_images = fields.Many2many(comodel_name='shopify.image', string="Shopify Image")

    def export_to_shopify(self):
        self.ensure_one()

        product = self.product_tmpl_id
        product_type = self.get_selection_label('product.template',
                                                'detailed_type',
                                                product.detailed_type)

        # Product Options
        options = []
        if product.product_variant_count > 1:
            options = [
                {
                 'name': variant.attribute_id.name,
                 'values': variant.value_ids.mapped('name'),
                }
                for variant in product.attribute_line_ids
            ]

        product_payload = {
            'input': {
                'title': product.name,
                'productOptions': options,
                'productType': product_type,
                'descriptionHtml': self.product_body_html if self.product_body_html else '',
                'status': 'ACTIVE',
            }
        }

        shopify_api = ShopifyApi(self.shopify_instance_id)
        res = shopify_api.import_raw_data(query_name='CreateProductWithOptions',
                                                                   variables=product_payload)

        shopify_product = res.get('data', {}).get('productCreate', {}).get('product', {})
        shopify_product_id = shopify_product.get('legacyResourceId')

        if self.shopify_images:
            for image in self.shopify_images:
                shopify_api.export_image_data(shopify_product_id, image.template_image)

        return res

    def get_selection_label(self, object, field_name, field_value):
        return dict(self.env[object].fields_get(allfields=[field_name])[field_name]['selection'])[field_value]
