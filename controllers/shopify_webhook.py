# -*- coding: utf-8 -*-

import logging
import requests
import base64

from odoo import http, Command
from odoo.http import request
from ..tools.shopify_api_v2 import ShopifyApi

_logger = logging.getLogger(__name__)


def str_to_bool(value: str) -> bool:
    return {"true": True, "false": False}.get(value.strip().lower(), False)


class WebhookController(http.Controller):

    # Utility methods
    def _create_shopify_middle_layer(self, shopify_product, instance_id, description, media=None):
        # Initialize data dictionary for product creation

        # Do not create if product template exist on this model
        product_exists = http.request.env['shopify.product'].sudo().search([('product_tmpl_id', '=', shopify_product.id)])
        _logger.info('Product Exists %s', product_exists)

        data = {
            'product_tmpl_id': shopify_product.id,
            'shopify_instance_id': instance_id,
            'status': 'publish',
            'name': shopify_product.name,
            'is_export': False,
            'product_body_html': description,
        }

        if media:
            shopify_images = []
            instance = http.request.env['shopify.instance'].sudo().browse(instance_id)
            for node in media:
                try:
                    payload = {
                        'product_tmpl_id': shopify_product.id,
                        'name': shopify_product.name,
                        'media_content_type': node['media_content_type'],
                        'shopify_graphql_id': node['admin_graphql_api_id'],
                    }

                    variables = {'id': node['admin_graphql_api_id']}
                    media_info = ShopifyApi(instance).import_raw_data(query_name='GetMedia', variables=variables)
                    node_data = media_info.get('data', {}).get('node', {})

                    if node['media_content_type'] == 'IMAGE':
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
        # Create Shopify product record
        if product_exists:
            product_exists.write(data)
            shopify_product = product_exists
        else: 
            shopify_product = http.request.env['shopify.product'].sudo().create(data)
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

    # Routes

    @http.route('/shopify_api/products/create', type='json', auth='public', methods=['POST'], csrf=False)
    def get_shopify_products_created(self):
        http_request = http.request.httprequest
        event_topic = http_request.headers.get('X-Shopify-Topic')
        product_data = http_request.get_json()

        shop_domain = http_request.headers.get('X-Shopify-Shop-Domain')
        instance_obj = http.request.env['shopify.instance'].sudo()
        instance_id = instance_obj.search([('shop_url', 'ilike', shop_domain)], limit=1)

        test_transaction = http_request.headers.get('X-Shopify-Test', False)
        if test_transaction:
            _logger.warning('SHOPIFY: This is only a test transaction.')
            return

        if not event_topic == 'products/create':
            _logger.warning('SHOPIFY: Event topic does not match.')
            return

        product_template = http.request.env['product.template'].sudo()

        title = product_data.get('title')
        description = product_data.get('body_html')
        tags = product_data.get('tags')
        shopify_product_id = product_data.get('id')
        graphql_id = product_data.get('admin_graphql_api_id')
        media = product_data.get('media')

        # Prepare Tags
        tag_cmd = []
        if tags:
            tags = tags.split(', ')
            existing_tags = http.request.env['product.tag'].search([('name', 'in', tags)])
            existing_tag_map = {tag.name: tag.id for tag in existing_tags}

            tag_cmd = [
                Command.link(existing_tag_map[tag]) if tag in existing_tag_map else Command.create({'name': tag})
                for tag in tags
            ]

        new_product = product_template.create({
            'name': title,
            'description': description,
            'type': 'product',            
            'shopify_product_id': shopify_product_id,
            'shopify_graphql_id': graphql_id,
            'shopify_instance_id': instance_id.id if instance_id else False,
            'product_tag_ids': tag_cmd if tag_cmd else False,
        })

        variant_options = product_data.get('options', [])
        if any("Default Title" in option["values"] for option in variant_options):
            variant = product_data.get('variants', [{}])[0]
            variant_id = variant.get('id')
            variant_graphql_id = variant.get('admin_graphql_api_id')
            inventory_id = variant.get('inventory_item_id')
            sku = variant.get('sku')
            price = variant.get('price') or 0.0
            compare_at_price = variant.get('compare_at_price') or 0.0

            new_product.product_variant_id.write({
                'product_product_id': variant_id,
                'product_graphql_id': variant_graphql_id,
                'shopify_inventory_id': inventory_id,
                'default_code': sku,
                'list_price': float(price),
                'compare_at_price': float(compare_at_price),
            })

        self._create_shopify_middle_layer(shopify_product=new_product,
                                          instance_id=instance_id.id,
                                          description=description,
                                          media=media)

        if new_product:
            _logger.info('SHOPIFY: Product Created %s', new_product.name)
        else:
            _logger.warning('SHOPIFY: Product did not create.')

    @http.route('/shopify_api/products/updated', type='json', auth='public', methods=['POST'], csrf=False)
    def get_shopify_products_updated(self):
        http_request = http.request.httprequest
        event_topic = http_request.headers.get('X-Shopify-Topic')
        product_data = http_request.get_json()

        shop_domain = http_request.headers.get('X-Shopify-Shop-Domain')
        instance_obj = http.request.env['shopify.instance'].sudo()
        instance_id = instance_obj.search([('shop_url', 'ilike', shop_domain)], limit=1)

        test_transaction = http_request.headers.get('X-Shopify-Test', False)
        if test_transaction:
            _logger.warning('SHOPIFY: This is only a test transaction.')
            return

        if not event_topic == 'products/update':
            _logger.warning('SHOPIFY: Event topic does not match.')
            return

        shopify_product_id = product_data.get('id')
        title = product_data.get('title')
        description = product_data.get('body_html')
        tags = product_data.get('tags')
        media = product_data.get('media')

        product_template = http.request.env['product.template'].sudo()
        existing_product = product_template.search([('shopify_product_id', '=', shopify_product_id)], limit=1)
        if not existing_product:
            _logger.warning('SHOPIFY: Product does not exist.')
            return

        # Prepare Tags
        tag_cmd = []
        if tags:
            tags = tags.split(', ')
            existing_tags = http.request.env['product.tag'].search([('name', 'in', tags)])
            existing_tag_map = {tag.name: tag.id for tag in existing_tags}

            tag_cmd = [
                Command.link(existing_tag_map[tag]) if tag in existing_tag_map else Command.create({'name': tag})
                for tag in tags
            ]

        existing_product.write({
            'name': title,
            'description': description,
            'type': 'product',
            'shopify_instance_id': instance_id.id if instance_id else False,
            'shopify_product_id': shopify_product_id,
            'product_tag_ids': tag_cmd if tag_cmd else False,
        })

        variant_options = product_data.get('options', [])
        if any("Default Title" in option["values"] for option in variant_options):
            variant = product_data.get('variants', [{}])[0]
            variant_id = variant.get('id')
            variant_graphql_id =  variant.get('admin_graphql_api_id')
            inventory_id = variant.get('inventory_item_id')
            sku = variant.get('sku')
            price = variant.get('price') or 0.0
            compare_at_price = variant.get('compare_at_price') or 0.0

            existing_product.product_variant_id.write({
                'product_product_id': variant_id,
                'product_graphql_id': variant_graphql_id,
                'shopify_inventory_id': inventory_id,
                'default_code': sku,
                'list_price': float(price),
                'compare_at_price': float(compare_at_price),
            })

        self._create_shopify_middle_layer(shopify_product=existing_product,
                                          instance_id=instance_id.id,
                                          description=description,
                                          media=media)

        if existing_product:
            _logger.info('SHOPIFY: Product Updated %s', existing_product.name)
        else:
            _logger.warning('SHOPIFY: Product did not updated.')

    @http.route('/shopify_api/products/delete', type='json', auth='public', methods=['POST'], csrf=False)
    def get_shopify_products_delete(self):

        http_request = http.request.httprequest
        event_topic = http_request.headers.get('X-Shopify-Topic')
        product_data = http_request.get_json()

        test_transaction = http_request.headers.get('X-Shopify-Test', False)
        if test_transaction:
            _logger.warning('SHOPIFY: This is only a test transaction.')
            return

        if event_topic == 'products/delete':
            product_template = http.request.env['product.template'].sudo()

            shopify_product_id = product_data.get('id')
            existing_product = product_template.search([('shopify_product_id', '=', shopify_product_id)], limit=1)
            if existing_product:
                product_name = existing_product.name
                existing_product.unlink()
                _logger.info('SHOPIFY: Product Deleted %s', product_name)
            else:
                _logger.warning('SHOPIFY: Customer did not create.')

    @http.route('/shopify_api/orders/updated', type='json', auth='public', methods=['POST'], csrf=False)
    def get_shopify_orders_updated(self):
        http_request = http.request.httprequest
        event_topic = http_request.headers.get('X-Shopify-Topic')
        order_data = http_request.get_json()

        test_transaction = http_request.headers.get('X-Shopify-Test', False)

        if str_to_bool(test_transaction):
            _logger.warning('SHOPIFY: This is only a test transaction.')
            return

        if not event_topic == 'orders/updated':
            _logger.warning('SHOPIFY: Event topic does not match.')
            return

        order_id = order_data.get('id')
        line_items = order_data.get('line_items')
        order_obj = http.request.env['sale.order'].sudo()
        existing_order = order_obj.search([('shopify_id', '=', order_id)], limit=1)
        if not existing_order:
            _logger.warning('SHOPIFY: Order does not exist.')
            return

        if existing_order.state != 'draft':
            _logger.warning('SHOPIFY: Sale Order must be on the draft state.')
            return

        # Process line items
        for item in line_items:
            product_id = item.get('id')  # Assuming you have a way to get product_id
            quantity = item.get('quantity', 1)
            price = item.get('price')
            # Check if the product exists in Odoo
            product = request.env['product.product'].sudo().search([
                ('shopify_product_id', '=', product_id)
            ], limit=1)
            if product:
                # Create or update sale order lines
                existing_line = http.request.env['sale.order.line'].sudo().search([
                    ('order_id', '=', existing_order),
                    ('id', '=', product_id)
                ], limit=1)
                if existing_line:
                    # Update existing line item
                    existing_line.sudo().write({
                        'product_uom_qty': quantity,
                        'price_unit': price,
                    })
                else:
                    # Create a new line item
                    http.request.env['sale.order.line'].sudo().create({
                        'order_id': order_id,
                        'product_id': product.id,
                        'product_uom_qty': quantity,
                        'price_unit': price,
                    })

        _logger.info('SHOPIFY: Order Updated %s', existing_order.name)

    # TODO: For testing
    @http.route('/shopify_api/customers/create', type='json', auth='public', methods=['POST'], csrf=False)
    def get_shopify_customers_create(self):
        _logger.info('SHOPIFY WEBHOOK: Customer created....')

        http_request = http.request.httprequest
        event_topic = http_request.headers.get('X-Shopify-Topic')
        customer_data = http_request.get_json()

        shop_domain = http_request.headers.get('X-Shopify-Shop-Domain')
        instance_obj = http.request.env['shopify.instance'].sudo()
        instance_id = instance_obj.search([('shop_url', 'ilike', shop_domain)], limit=1)

        test_transaction = http_request.headers.get('X-Shopify-Test', False)
        if test_transaction:
            _logger.warning('SHOPIFY: This is only a test transaction.')
            return

        if not event_topic == 'customers/create':
            _logger.warning('SHOPIFY: Event topic does not match.')
            return

        shopify_id = str(customer_data.get('id'))
        email = customer_data.get('email')
        first_name = customer_data.get('first_name')
        last_name = customer_data.get('last_name')
        note = customer_data.get('note')
        graphql_id = customer_data.get('admin_graphql_api_id')
        order_count = customer_data.get('orders_count')
        address = customer_data.get('default_address', {}).get('id', False)
        phone = customer_data.get('phone')

        customer = http.request.env['res.partner'].sudo().create({
            'shopify_user_id': shopify_id, 
            'shopify_instance_id': instance_id.id if instance_id else False,
            'email': email,
            'name': f"{first_name} {last_name}",
            'phone': phone,
            'shopify_customer_note': note,
            'shopify_graphql_id': graphql_id,
            'shopify_order_count': order_count,
            'is_shopify_customer': True,
            'shopify_address_id': address,
        })

        if customer:
            _logger.info('SHOPIFY: Customer created %s', customer.name)
        else:
            _logger.warning('SHOPIFY: Customer did not create.')

    # TODO: For testing
    @http.route('/shopify_api/customers/update', type='json', auth='public', methods=['POST'], csrf=False)
    def get_shopify_customers_update(self):
        _logger.info('SHOPIFY WEBHOOK: Customer created....')

        http_request = http.request.httprequest
        event_topic = http_request.headers.get('X-Shopify-Topic')
        customer_data = http_request.get_json()

        shop_domain = http_request.headers.get('X-Shopify-Shop-Domain')
        instance_obj = http.request.env['shopify.instance'].sudo()
        instance_id = instance_obj.search([('shop_url', 'ilike', shop_domain)], limit=1)

        test_transaction = http_request.headers.get('X-Shopify-Test', False)
        if test_transaction:
            _logger.warning('SHOPIFY: This is only a test transaction.')

        if event_topic == 'customers/update':
            shopify_id = str(customer_data.get('id'))
            email = customer_data.get('email')
            first_name = customer_data.get('first_name')
            last_name = customer_data.get('last_name')
            note = customer_data.get('note')
            graphql_id = customer_data.get('admin_graphql_api_id')
            order_count = customer_data.get('orders_count')
            address = customer_data.get('default_address', {}).get('id', False)
            phone = customer_data.get('phone')

            existing_customer = http.request.env['res.partner'].sudo().search([('shopify_user_id', '=', shopify_id)], limit=1)
            if existing_customer:
                # Update the existing customer with the new data from Shopify
                existing_customer.sudo().write({
                    'shopify_instance_id': instance_id.id if instance_id else False,
                    'email': email,
                    'name': f"{first_name} {last_name}",
                    'shopify_customer_note': note,
                    'phone': phone,
                    'shopify_graphql_id': graphql_id,
                    'shopify_order_count': order_count,
                    'is_shopify_customer': True,
                    'shopify_address_id': address,
                })
                _logger.info('SHOPIFY: Customer updated %s', existing_customer.name)            
            else:
                _logger.warning('SHOPIFY: Customer did not update.')
