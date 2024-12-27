# -*- coding: utf-8 -*-

import logging
import shopify
from odoo import models, fields, api, Command, _
from ..tools.shopify_api_v2 import ShopifyApi
from datetime import datetime, date

_logger = logging.getLogger(__name__)

DATE_FORMAT = "%Y-%m-%d"


class ShopifyBankStatement(models.Model):
    _name = 'shopify.bank.statement'
    _description = 'Shopify Bank Statement'

    name = fields.Char('Name')
    line_ids = fields.Many2many(comodel_name='account.bank.statement.line')
