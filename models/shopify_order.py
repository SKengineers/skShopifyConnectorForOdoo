# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, Command, _
from ..tools.shopify_api_v2 import ShopifyApi

_logger = logging.getLogger(__name__)


class ShopifyProduct(models.Model):
    _inherit = 'sale.order'

    shopify_id = fields.Char('ID')
    shopify_graphql_id = fields.Char('Shopify GraphQL ID')
    shopify_order_no = fields.Char('Order No.')
    shopify_processing_method = fields.Char("Processing Method")
    shopify_status = fields.Char('Order Status')
    shopify_fulfillment_status = fields.Char('Fulfillment Status')
    shopify_fulfillment_location = fields.Char('Fulfillment location')
    shopify_order_url = fields.Char(string="Order URL")
    shopify_order_date = fields.Date(string="Order Date")
    shopify_order_subtotal = fields.Float('Order Subtotal')
    shopify_order_total_tax = fields.Float('Order Total Tax')
    shopify_order_total = fields.Float('Order Total Price')
    shopify_order_note = fields.Char('Order Note from Customer')
    shopify_instance_id = fields.Many2one('shopify.instance', string="Shopify Instance")

    is_exported = fields.Boolean('Synced In Shopify', default=False)
    is_shopify_order = fields.Boolean('Is Shopify Order', default=False)
    is_shopify_draft_order = fields.Boolean('Shopify Draft Order', default=False)

    @api.model
    def create_order_from_shopify(self, order, instance_id):
        customer_id = order.get('customer', {})

        if customer_id:
            customer_id = customer_id.get('legacyResourceId')

        partner_id = self.env['res.partner'].search([(
            'shopify_user_id', '=', customer_id
        )], limit=1)

        if partner_id:
            partner_id = partner_id
        else:
            return False

        fulfillment_status = order.get('displayFulfillmentStatus', 'unshipped').lower()
        gateway_names = order.get('paymentGatewayNames', ['manual'])

        order_data = {
            'shopify_id': order.get('legacyResourceId'),
            'shopify_graphql_id': order.get('id'),
            'shopify_order_no': order.get('name'),
            'shopify_fulfillment_status': fulfillment_status,
            'partner_id': partner_id.id,
            'shopify_instance_id': instance_id,
            'state': 'draft',
        }
        # TODO: For improvements
        order_lines = []
        if order.get('lineItems'):
            for line in order['lineItems']['nodes']:
                variant = line.get('variant', {})

                if variant:
                    variant_id = variant.get('legacyResourceId', False)
                else:
                    _logger.info('No Product ID Found: %s', line)
                    continue
                price = line['discountedUnitPriceAfterAllDiscountsSet'].get('shopMoney', {}).get('amount', 0)

                product_obj = self.env['product.product'].search_read([(
                    'product_product_id', '=', variant_id
                )], ['id'], limit=1)
                if not product_obj:
                    continue

                line_item = {
                    'shopify_graphql_id': line.get('id'),
                    'product_id': product_obj[0]['id'] if product_obj else False,
                    'price_unit': price,
                    'product_uom_qty': line.get('quantity'),
                    'tax_id': False,
                    # 'tax_lines': [
                    #     {
                    #         'price': 13.5,
                    #         'rate': 0.06,
                    #         'title': "State tax"
                    #     }
                    # ]
                }

                order_lines.append(Command.create(line_item))
            order_data['order_line'] = order_lines
        created_order = self.create(order_data)

        # For Cancelled Order.
        if order.get('cancellation') and order.get('cancelledAt'):
            created_order.action_cancel()
            return created_order

        financial_status = self.get_financial_status(instance_id,
                                                    fulfillment_status,
                                                    gateway_names)

        if financial_status:
            self.apply_financial_status_to_order(created_order,
                                                financial_status)

        return created_order

    def export_to_shopify(self, instance_id):
        self.ensure_one()

        line_items = [
            {
                'title': line.product_id.name,
                'originalUnitPrice': line.price_unit,
                'quantity': int(line.product_uom_qty),
            }
            for line in self.order_line
            if line.product_id.product_product_id
        ]

        # TODO: For testing.
        order_payload = {
            'input': {
                'purchasingEntity': {
                    'customerId': self.partner_id.shopify_graphql_id
                },
                'lineItems': line_items,
            }
        }
        response = ShopifyApi(instance_id).import_raw_data(query_name='draftOrderCreate',
                                                           variables=order_payload)
        return response

    def get_financial_status(self, instance_id, fulfillment_status, gateway_names):

        fulfillment_status = self.env['shopify.order.status'].search([('status', '=', fulfillment_status)], limit=1)
        gateway_name = self.env['shopify.payment.gateway'].search([('code', 'in', gateway_names)], limit=1)

        financial_status = self.env['shopify.financial.status'].search([('shopify_instance_id','=', instance_id),
                                                                        ('shopify_order_payment_status', '=', fulfillment_status.id),
                                                                        ('payment_gateway_id', '=', gateway_name.id )], limit=1)

        if not financial_status:
            _logger.info('No Financial Status setup found in this configuration')
            return

        return financial_status

    def apply_financial_status_to_order(self, order, financial_status):
        payment_term = financial_status.payment_term_id
        order_payment_status = financial_status.shopify_order_payment_status.status
        if payment_term:
            order.write({
                'payment_term_id': payment_term.id,
                'shopify_fulfillment_status': order_payment_status,
            })

        auto_workflow = financial_status.auto_workflow_id
        if auto_workflow:
            if auto_workflow.confirm_quotation:
                order.action_confirm()

            if auto_workflow.create_validate_invoice:
                invoice = order._create_invoice()
                invoice.action_post()

            if auto_workflow.register_payment:
                payment = self.env['account.payment'].create({
                    'invoice_ids': [(6, 0, order.invoice_ids.ids)],
                    'amount': order.amount_total,
                    'payment_date': fields.Date.today(),
                    'payment_type': 'inbound',
                    'partner_id': order.partner_id.id,
                    'partner_type': 'customer',
                })
                payment.action_post()

            if auto_workflow.force_accounting_date:
                for invoice in order.invoice_ids:
                    invoice.write({'date': fields.Date.today()})

    def _apply_auto_workflow(self, order, auto_workflow):
        if auto_workflow:
            if auto_workflow.confirm_quotation:
                order.action_confirm()

            if auto_workflow.create_validate_invoice:
                invoice = order._create_invoice()
                invoice.action_post()

            if auto_workflow.register_payment:
                payment = self.env['account.payment'].create({
                    'invoice_ids': [(6, 0, order.invoice_ids.ids)],
                    'amount': order.amount_total,
                    'payment_date': fields.Date.today(),
                    'payment_type': 'inbound',
                    'partner_id': order.partner_id.id,
                    'partner_type': 'customer',
                })
                payment.action_post()

            if auto_workflow.force_accounting_date:
                for invoice in order.invoice_ids:
                    invoice.write({'date': fields.Date.today()})

    def action_goto_shopify_link(self):
        self.ensure_one()
        if self.shopify_id and self.shopify_instance_id:
            shop_url = self.shopify_instance_id.shop_url
            subdomain = shop_url.split("//")[1].split(".")[0]
            url = 'https://admin.shopify.com/store/%s/orders/%s' % (subdomain, self.shopify_id)
            return {
                'type': 'ir.actions.act_url',
                'url': url,
                'target': 'new',
            }

    def action_cancel_shopify(self):
        return {
            'name': _('Cancel Order in Shopify'),
            'res_model': 'cancel.refund.order.shopify.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('sk_shopify_connector_for_odoo.cancel_refund_order_wizard_form_view').id,
            'views': [[False, 'form']],
            'context': {
                'active_model': 'sale.order',
                'active_ids': self.ids,
                'default_transaction_type': 'cancel_order',
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }


class ShopifyProductLine(models.Model):
    _inherit = 'sale.order.line'

    shopify_graphql_id = fields.Char('Shopify GraphQL ID')
    shopify_id = fields.Char('Shopify Line ID', compute='compute_shopify_id')

    @api.depends('shopify_graphql_id')
    def compute_shopify_id(self):
        for line in self:
            line_id = line.shopify_graphql_id
            line.shopify_id = line_id.split("/")[-1]
