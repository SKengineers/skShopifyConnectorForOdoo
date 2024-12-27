# -*- coding: utf-8 -*-

import logging
import base64
import requests

from odoo import models, fields, api, Command
from ..tools.shopify_api_v2 import ShopifyApi

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    shopify_product_id = fields.Char(string='Shopify Product ID')
    shopify_graphql_id = fields.Char(string='GraphQL ID')
    shopify_instance_id = fields.Many2one('shopify.instance', string="Shopify Instance")

    @api.model
    def create_product_from_shopify(self, product, instance_id):

        data = {
            'shopify_product_id': product.get('legacyResourceId', ''),
            'shopify_graphql_id': product.get('id', ''),
            'shopify_instance_id': instance_id,
            'name': product.get('title', ''),
            'detailed_type': 'product',
            'sale_ok': True,
            'purchase_ok': True,
            'list_price': 0,
        }

        tags = product.get('tags')
        if tags:
            data['product_tag_ids'] = self._prepare_product_tags(tags)

        variant_options = product.get('options', [])
        variant_id = inventory_id = False
        if any("Default Title" in option["values"] for option in variant_options):
            variants = product.get('variants', [{}])
            product_info = variants.get('nodes')[0]
            variant_id = product_info['legacyResourceId']
            variant_graphql_id = product_info['id']
            inventory_id = product_info['inventoryItem']
            
            data.update({
                'default_code': product_info['sku'],
                'barcode': product_info['barcode'],
                'list_price': float(product_info['price']),
            })

        product_variants = self._prepare_product_variants(variant_options)
        if product_variants.get('attribute_line_ids', []):
            data.update(product_variants)

        shopify_product = self.create(data)
        if shopify_product.product_variant_count <= 1:
            if variant_id:
                shopify_product.product_variant_id.write({
                    'product_product_id': variant_id,
                    'product_graphql_id': variant_graphql_id,
                    'shopify_inventory_id': inventory_id['legacyResourceId'],
                    'inventory_graphql_id': inventory_id['id'],
                })
        else:
            # Update product variants information such as shopify id, pricing, etc.
            prod_prod_variants = shopify_product.product_variant_ids
            data_variants = product.get('variants', [])

            self._update_product_variant_info(data_variants, prod_prod_variants)

        # Add an image
        # image_info = product.get('image')
        # if image_info:
        #     image_url = image_info.get('src')
        #     if image_url:
        #         image = self._get_binary_image(image_url)
        #         data['image_1920'] = image


        # Create a Product middle layer
        # This can handle multiple image in shopify.
        description = product.get('descriptionHtml')
        media = product.get('media')
        self._create_shopify_middle_layer(shopify_product=shopify_product,
                                          instance_id=instance_id,
                                          description=description,
                                          media=media)

        return shopify_product

    def _prepare_product_variants(self, options):
        product_attribute = self.env['product.attribute']
        product_attribute_value = self.env['product.attribute.value']

        product_variants = []

        for variant in options:
            variant_value_ids = []
            variant_id = variant.get('id').split('/')[-1]
            if 'Default Title' in variant['values']:
                continue

            # Create or search for the product attribute
            product_attribute_id = product_attribute.search([('name', '=', variant['name']),
                                                             ('shopify_id', '=', variant_id),
                                                             ('create_variant', '=', 'always')], limit=1)

            if not product_attribute_id.shopify_graphql_id:
                product_attribute_id.write({
                    'shopify_graphql_id': variant.get('id'),
                })

            # Auto update Graphql ID
            if not product_attribute_id:
                product_attribute_id = product_attribute.create({'name': variant['name'],
                                                                 'shopify_graphql_id': variant.get('id'),
                                                                 'create_variant': 'always'
                                                                 })

            for index, value in enumerate(variant.get('optionValues', [])):
                graphql_id = value.get('id').split('/')[-1]
                attrib_value_id = product_attribute_value.search([('name', '=', value.get('name')),
                                                                  ('shopify_id', '=', graphql_id),
                                                                  ('attribute_id', '=', product_attribute_id.id)],
                                                                 limit=1)

                # Auto update Graphql ID
                if not attrib_value_id.shopify_graphql_id:
                    product_attribute_id.write({
                        'shopify_graphql_id': value.get('id'),
                    })

                if not attrib_value_id:
                    attrib_value_id = product_attribute_value.create({
                        'name': value.get('name'),
                        'shopify_graphql_id': value.get('id'),
                        'attribute_id': product_attribute_id.id,
                        'sequence': index
                    })

                variant_value_ids.append(attrib_value_id.id)

            product_variants.append(Command.create({
                    'attribute_id': product_attribute_id.id,
                    'value_ids': [Command.set(variant_value_ids)]
                })
            )

        return {'attribute_line_ids': product_variants}

    def _update_product_variant_info(self, variant_data, product_variants):

        for data in variant_data.get('nodes'):
            selected_options = [item["optionValue"]["id"].split('/')[-1] for item in data.get('selectedOptions')]

            match_variant = False
            for product_variant in product_variants:
                variant_values = product_variant.product_template_variant_value_ids.mapped('product_attribute_value_id.shopify_id')
                if sorted(selected_options) == sorted(variant_values):
                    match_variant = product_variant
                    break

            price = data.get('price') or 0.0
            
            inventory_item = data.get('inventoryItem')
            if match_variant:
                match_variant.write({
                    'product_product_id': data.get('legacyResourceId'),
                    'product_graphql_id': data.get('id'),
                    'compare_at_price': float(data.get('compareAtPrice')) if data.get('compareAtPrice') else 0,
                    'shopify_inventory_id': inventory_item['legacyResourceId'],
                    'inventory_graphql_id': inventory_item['id'],
                    'default_code': data.get('sku'),
                    'barcode': data.get('barcode'),
                    'lst_price': float(price),
                    'standard_price': float(inventory_item['unitCost']['amount']) if inventory_item['unitCost']['amount'] else 0,
                })

    def _prepare_product_tags(self, tags):
        # Add a tag
        tag_cmd = []

        for tag in tags:
            check_tag = self.env['product.tag'].search([('name', '=', tag)])
            if check_tag:
                tag_cmd.append(Command.link(check_tag.id))
            else:
                tag_cmd.append(Command.create({'name': tag}))
        return tag_cmd

    # For Testing
    def _create_shopify_middle_layer(self, shopify_product, instance_id, description, media=None):
        # Initialize data dictionary for product creation
        data = {
            'product_tmpl_id': shopify_product.id,
            'shopify_instance_id': instance_id,
            'status': 'publish',
            'name': shopify_product.name,
            'is_export': False,
            'product_body_html': description,
        }

        # Process media if provided
        if media and media.get('nodes'):
            media_nodes = media['nodes']
            shopify_images = []

            instance = self.env['shopify.instance'].browse(instance_id)
            for node in media_nodes:
                try:
                    payload = {
                        'product_tmpl_id': shopify_product.id,
                        'name': shopify_product.name,
                        'media_content_type': node['mediaContentType'],
                        'shopify_graphql_id': node['id'],
                    }

                    variables = {'id': node['id']}
                    media_info = ShopifyApi(instance).import_raw_data(query_name='GetMedia', variables=variables)
                    node_data = media_info.get('data', {}).get('node', {})
                    _logger.info('NODE DATA %s', node_data)
                    if node['mediaContentType'] == 'IMAGE':
                        image_url = node_data.get('image', {}).get('url')
                        payload.update({
                            'url': image_url,
                            'template_image': self._get_binary_image(image_url),
                        })
                    else:
                        payload.update({
                            'url': node_data.get('embedUrl', ''),
                        })

                    # Add processed payload to shopify_images
                    shopify_images.append(Command.create(payload))

                except Exception as e:
                    _logger.error('Error processing media node %s: %s', node, str(e))

            # Update data with processed shopify images
            data['shopify_images'] = shopify_images
            _logger.info('Check data test %s', data)
        # Create Shopify product record
        shopify_product = self.env['shopify.product'].create(data)
        _logger.info('Shopify Product Created: %s', shopify_product.name)

    def _get_binary_image(self, image_url):
        binary_data = None
        try:
            with requests.get(image_url) as response:
                if response.status_code == 200:
                    # Encode the image content to base64
                    binary_data = base64.b64encode(response.content)
        except requests.RequestException as e:
            _logger.info("Request failed: %s", e)
        except Exception as e:
            _logger.error("An unexpected error occurred: %s", e)

        return binary_data
