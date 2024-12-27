# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, Command, _

_logger = logging.getLogger(__name__)


class ProductAttribute(models.Model):
    _inherit = 'product.attribute'

    shopify_id = fields.Char('Shopify ID', compute='_compute_shopify_id', store=True)
    shopify_graphql_id = fields.Char('Shopify GraphQL ID')

    @api.depends('shopify_graphql_id')
    def _compute_shopify_id(self):
        for rec in self:
            if rec.shopify_graphql_id:
                try:
                    rec.shopify_id = rec.shopify_graphql_id.rsplit('/', 1)[-1]
                except Exception as e:
                    _logger.error(f"Failed to compute shopify_id for record {rec.id}: {e}")
                    rec.shopify_id = False
            else:
                rec.shopify_id = False
