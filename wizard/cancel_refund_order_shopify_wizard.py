# -*- coding: utf-8 -*-

import logging

from odoo import fields, models, api, Command,  _
from ..tools.shopify_api_v2 import ShopifyApi

_logger = logging.getLogger(__name__)


class CancelRefundOrderShopifyWizard(models.TransientModel):
    _name = 'cancel.refund.order.shopify.wizard'

    transaction_type = fields.Selection([('refund_order', 'REFUND'),
                                         ('cancel_order', 'CANCEL')], string='Transaction Type')
    note = fields.Char(string='Note')
    journal_id = fields.Many2one(comodel_name="account.journal",
                                 string="Journal")
    notify_email = fields.Boolean(string="Notify By Email")
    message = fields.Selection([("CUSTOMER", "The customer wanted to cancel the order."),
                                ("INVENTORY", "There was sufficient inventory"),
                                ("FRAUD", "The order was fraudulent"),
                                ("INVENTORY", "There was insufficient inventory"),
                                ("DECLINED", "Payment was declined."),
                                ("STAFF", "Staff made an error.")], string="Message")
    refund_date = fields.Date(string="Refund Date")
    restock_type = fields.Selection([("no_restock", "No Return"),
                                     ("cancel", "Cancel"),
                                     ("return", "Return")], string="Restock Type")
    reason = fields.Char(string='Reason')

    transaction_line_id = fields.Many2many('cancel.refund.transaction.wizard',
                                           'transaction_wizard_rel',
                                           string='Transaction Lines',
                                           copy=False)

    def execute_refund_operation(self):
        model = self.env.context.get('active_model')
        model_ids = self.env.context.get('active_ids')
        move_ids = self.env[model].browse(model_ids)
        order_obj = self.env['sale.order']

        for move in move_ids:
            order = order_obj.search([('name', '=', move.invoice_origin)], limit=1)
            variables = {
                "input": {
                    "orderId": order.shopify_graphql_id,
                    "note": self.note or 'Refund from Odoo',
                    "refundLineItems": [
                        {
                            "lineItemId": line.shopify_graphql_id,
                            "quantity": int(line.product_uom_qty),
                        } for line in order.order_line
                    ],
                    "transactions": [
                        {
                            "orderId": order.shopify_graphql_id,
                            "gateway": transaction.payment_gateway_id.code,
                            "kind": "REFUND",
                            "amount": str(transaction.refund_amount),
                        } for transaction in self.transaction_line_id
                    ]
                }
            }

            response = ShopifyApi(order.shopify_instance_id).export_data(query_name='M',
                                                                         payload=variables,
                                                                         key_value='job')
            _logger.info('Shopify Refund Response: %s', response)

        return True

    def execute_cancel_operation(self):
        model = self.env.context.get('active_model')
        model_ids = self.env.context.get('active_ids')

        orders = self.env[model].browse(model_ids)

        for order in orders:
            variables = {
                'notifyCustomer': self.notify_email,
                'orderId': order.shopify_graphql_id,
                'reason': self.message,
                'refund': True,
                'restock': True,
                'staffNote': self.reason,
            }

            response = ShopifyApi(order.shopify_instance_id).export_data(query_name='orderCancel',
                                                                         payload=variables,
                                                                         key_value='job')
            _logger.info('Shopify Refund Response: %s', response)

        return True


class CancelRefundTransactionWizard(models.Model):
    _name = 'cancel.refund.transaction.wizard'
    _description = 'Cancel Refund Order Transaction Line Wizard'

    payment_gateway_id = fields.Many2one(comodel_name='shopify.payment.gateway', string='Payment Gateway')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    amount = fields.Monetary(string='Amount',
                             currency_field='currency_id')
    remaining_refund_amount = fields.Monetary(string='Remaining Refund Amount',
                                              currency_field='currency_id')
    refund_amount = fields.Monetary(string='Refund Amount',
                                    currency_field='currency_id')
    is_want_to_refund = fields.Boolean(string='Is Want to Refund',
                                       default=True)

    # TODO: Add some logic when it comes to refunding the amount.
