# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class ShopifyImage(models.Model):
    _name = "shopify.image"
    _description = "Shopify Image"

    product_tmpl_id = fields.Many2one(comodel_name="product.template", string="Product Template")
    template_image = fields.Binary(string="Image")
    template_filename = fields.Char()
    name = fields.Char(string="Name")
    media_content_type = fields.Char('Content Type')
    shopify_graphql_id = fields.Char()
    url = fields.Char(string='Shopify Media URL')
