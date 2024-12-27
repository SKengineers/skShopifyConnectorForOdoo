# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, Command
from ..tools.shopify_api import ShopifyApi

_logger = logging.getLogger(__name__)

CUSTOMER_DEFAULT_PASSWORD = 'defaultpass'


def extract_names(full_name):
    # Split the name into words
    name_parts = full_name.split()

    first_name = ""
    middle_initial = ""
    last_name = ""

    if len(name_parts) == 2:
        first_name = name_parts[0]
        last_name = name_parts[1]
        middle_initial = ""

    elif len(name_parts) == 3:
        first_name = name_parts[0]
        middle_initial = name_parts[1]
        last_name = name_parts[2]

    elif len(name_parts) > 3:
        first_name = " ".join(name_parts[:-2])
        middle_initial = name_parts[-2]
        last_name = name_parts[-1]
    return first_name, middle_initial, last_name


class ResPartner(models.Model):
    _inherit = 'res.partner'

    shopify_user_id = fields.Char('User ID')
    shopify_address_id = fields.Char('Address ID')
    shopify_order_count = fields.Integer('Order Count From Shopify')
    shopify_customer_note = fields.Text('User Note')

    shopify_graphql_id = fields.Char('GraphQL ID')
    is_exported = fields.Boolean('Synced In shopify', default=False)
    is_shopify_customer = fields.Boolean('Is Shopify Customer', default=False)

    shopify_instance_id = fields.Many2one('shopify.instance', string="Shopify Instance")

    @api.model
    def create_customer_from_shopify(self, partner, instance_id):
        partner_data = {
            'name': partner.get('displayName', ''),
            'email': partner.get('email', ''),
            'phone': partner.get('phone', ''),
            'shopify_user_id': partner.get('legacyResourceId', ''),
            'shopify_graphql_id': partner.get('id', ''),
            'shopify_instance_id': instance_id,
            'is_exported': False,
            'is_shopify_customer': True,
            'customer_rank': 1,
        }

        if partner.get('addresses', []):
            partner_data['child_ids'] = [
                Command.create({
                    'shopify_graphql_id': address.get('id'),
                    'name': f"{address.get('firstName', '')} {address.get('lastName', '')}".strip(),
                    'street': address.get('address1', ''),
                    'street2': address.get('address2', ''),
                    'city': address.get('city', ''),
                    'zip': address.get('zip', ''),
                    'country_id': self.env['res.country'].search(
                        [('code', '=', address.get('countryCodeV2'))],
                        limit=1).id,
                    'is_exported': False,
                    'is_shopify_customer': True,
                })
                for address in partner['addresses']
            ]

        data = self.create(partner_data)
        return data

    @api.model
    def _import_customer_cron(self):
        imported_customers = ShopifyApi(self.instance_id)._import_customers()
        customer_list = []

        customer_ids = [customer['id']
                        for customer in imported_customers.get('customers', [])
                        if 'id' in customer]
        existing_partner = self.env['res.partner'].search(['shopify_user_id', 'in', customer_ids]).ids
        for customer in imported_customers.get('customers', []):
            if customer['id'] not in existing_partner:
                customer_data = {
                    'name': f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
                    'email': customer.get('email', ''),
                    'phone': customer.get('phone', ''),
                    'shopify_user_id': customer.get('id', ''),
                    'shopify_instance_id': self.instance_id.id,
                    'is_exported': False,
                    'is_shopify_customer': True,
                }

                if hasattr(customer, 'addresses'):
                    customer_data['child_ids'] = [
                        Command.create({
                          'shopify_user_id': address.get('id'),
                          'name': f"{address.get('first_name', '')} {address.get('last_name', '')}".strip(),
                          'street': address.get('address1', ''),
                          'street2': address.get('address2', ''),
                          'city': address.get('city', ''),
                          'zip': address.get('zip', ''),
                          'country_id': self.env['res.country'].search([('country_code', '=', address.get('country_code'))], limit=1).id
                        })
                        for address in customer['addresses']
                    ]
                customer_list.append(customer_data)

        if customer_list:
            self.env['res.partner'].create(customer_list)
