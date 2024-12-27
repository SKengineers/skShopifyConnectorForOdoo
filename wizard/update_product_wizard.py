# -*- coding: utf-8 -*-

import logging

from odoo import fields, models, api, Command,  _
from ..tools.shopify_api_v2 import ShopifyApi
from ..tools.product_importer import ProductDataImporter
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UpdateProductWizard(models.TransientModel):
    _name = 'update.product.wizard'
    _description = 'Update Product Wizard'
    _inherit = 'operation.shopify.wizard'

    name = fields.Char()
    operation_type = fields.Selection([
            ("export_product", "Export Product"),
            ("export_order", "Export Order"),
            ("export_stock", "Export Stock"),
        ],
        string="Operations", required=True)

    def proceed_to_update(self):
        return True
