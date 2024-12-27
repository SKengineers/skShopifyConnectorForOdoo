# -*- coding: utf-8 -*-

import logging
import json
from odoo import models, fields
_logger = logging.getLogger(__name__)


class ShopifyOrderStatus(models.Model):
    _name = 'shopify.order.status'
    _description = 'Shopify Order Status'

    name = fields.Char()
    status = fields.Char()
