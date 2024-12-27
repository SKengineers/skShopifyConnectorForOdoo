# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, Command

_logger = logging.getLogger(__name__)


class SaleAutoWorkflow(models.Model):
    _name = 'sale.auto.workflow'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Sale Auto Workflow'

    name = fields.Char(string='Workflow Name')

    # Workflow Options
    confirm_quotation = fields.Boolean(tracking=True)
    create_validate_invoice = fields.Boolean(tracking=True)
    register_payment = fields.Boolean(tracking=True)
    force_accounting_date = fields.Boolean(tracking=True)

    # Order Configuration
    shipping_policy = fields.Selection([
            ("each_product", "Deliver each product when available"),
            ("all_product", "Deliver all products at one"),
            ],
            string="Shipping Policy", required=True)

    journal_id = fields.Many2one(comodel_name="account.journal",
                                 string="Sales Journal", required=True)
