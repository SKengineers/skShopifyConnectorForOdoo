# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, Command

_logger = logging.getLogger(__name__)


class ProductCategory(models.Model):
    _inherit = 'product.category'

    is_shopify = fields.Boolean(string='Is Shopify?')
    shopify_instance_id = fields.Many2one('shopify.instance', ondelete='cascade')
