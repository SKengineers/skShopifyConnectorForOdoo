# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, Command, _
from odoo.exceptions import ValidationError
from ..tools.shopify_api import ShopifyApi
from ..tools.shopify_api_v2 import ShopifyApi as ShopifyApiv2

_logger = logging.getLogger(__name__)


class ShopifyScheduleAction(models.Model):
    _name = 'shopify.schedule.action'
    _description = 'Detailed Configuration for Scheduled Actions'

    import_order = fields.Boolean(string='Import Order')
    import_shipped_order = fields.Boolean(string='Import Shipped Order')
    import_cancel_order = fields.Boolean(string='Import Cancel Order')
    # Add update shipping status
    export_stock = fields.Boolean(string='Export Stock')
    import_payout_report = fields.Boolean(string='Auto Import Payout Report')
