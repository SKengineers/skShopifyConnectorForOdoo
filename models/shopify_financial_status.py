# -*- coding: utf-8 -*-

import logging
import json
from odoo import models, fields
_logger = logging.getLogger(__name__)


class ShopifyFinancialStatus(models.Model):
    _name = 'shopify.financial.status'
    _description = 'Financial Status for Shopify'

    auto_workflow_id = fields.Many2one('sale.auto.workflow', string='Auto Workflow')
    financial_status = fields.Selection([('pending', 'The finances are pending'),
                                         ('authorized', 'The finances have been authorized'),
                                         ('partially_paid', 'The finances have been partially paid'),
                                         ('paid', 'The finances have been paid'),
                                         ('partially_refunded', 'The finances have been partially refunded'),
                                         ('refunded', 'The finances have been refunded'),
                                         ('voided', 'The finances have been voided'),], string='Financial Status')
    payment_gateway_id = fields.Many2one('shopify.payment.gateway', string='Payment Gateway')
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Term')
    shopify_instance_id = fields.Many2one('shopify.instance', string='Shopify Instance')
    shopify_order_payment_status = fields.Many2one('shopify.order.status', string='Shopify Order Status')

    _sql_constraints = [
        (
            'workflow_unique',
            'unique(financial_status, shopify_instance_id, payment_gateway_id, shopify_order_payment_status)',
            'The combination of financial status, Shopify instance, payment gateway, and order payment status must be unique.'
        )
    ]
