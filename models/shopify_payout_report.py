# -*- coding: utf-8 -*-

import logging
import shopify
from odoo import models, fields, api, Command, _
from ..tools.shopify_api_v2 import ShopifyApi
from datetime import datetime, date
from odoo.addons.web.controllers.utils import clean_action

_logger = logging.getLogger(__name__)

DATE_FORMAT = "%Y-%m-%d"


class ShopifyPayoutReport(models.Model):
    _name = 'shopify.payout.report'
    _description = 'Shopify Payout Report'

    name = fields.Char("Payout Reference ID", required=True, default=lambda self: _('New'))
    shopify_instance_id = fields.Many2one('shopify.instance', string="Shopify Instance", required=True)
    payout_date = fields.Date("Payout Date")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')    
    total_amount = fields.Float("Total Amount", compute='_compute_total_amount')
    payout_status = fields.Selection([
        ('draft', 'Draft'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
    ], string="Payout Status", default='draft')
    transaction_line_ids = fields.One2many(
        'shopify.payout.report.line', 'payout_id', string="Payout Transaction Lines"
    )
    status = fields.Selection([
        ('new', 'New'),
        ('process', 'Processing'),
        ('validate', 'Validate')], string='Status', default='new')

    @api.depends('transaction_line_ids')
    def _compute_total_amount(self):
        for rec in self:
            total_amount = 0
            for line in rec.transaction_line_ids:
                total_amount += line.amount

            rec.total_amount = total_amount

    @api.model
    def create(self, vals):
        res = super().create(vals)
        res['name'] = self.env['ir.sequence'].next_by_code(
            'shopify.payout.report.sequence'
        ) or _('New')
        return res

    @api.model
    def create_payout_report_from_shopify(self, instance_id, records):
        date_payout = self.env.context.get('payout_date')
        payout_data = records['data']['shopifyPaymentsAccount']

        if not payout_data:
            return False

        currency_id = self.env['res.currency'].search([('name', '=', payout_data.get('defaultCurrency'))], limit=1)

        data = {
            'shopify_instance_id': instance_id,
            'payout_date': date_payout,
            'currency_id': currency_id.id
        }

        transaction_list = []
        transactions = payout_data['balanceTransactions']['edges']
        for line in transactions:
            transaction = line.get('node')
            amount = transaction['amount']['amount']
            fee_amount = transaction['fee']['amount']
            net_amount = transaction['net']['amount']

            if transaction['associatedOrder']:
                order_reference = transaction['associatedOrder']['name']
                order_id = transaction['associatedOrder']['id']
            create = Command.create({
                'transaction_type': transaction.get('type'),
                'transaction_id': transaction.get('sourceId'),
                'graphql_id': transaction['id'],
                'order_reference': order_reference,
                'order_id': order_id,
                'net_amount': float(net_amount),
                'fees': float(fee_amount),
                'amount': float(amount),
            })

            transaction_list.append(create)

        if transaction_list:
            data['transaction_line_ids'] = transaction_list
            return self.create(data)

        return False

    @api.model
    def auto_import_payout_report(self):
        # Retrieve instances where import scheduler is enabled
        instances = self.env['shopify.instance'].search([('is_import_scheduler', '=', True)])

        if not instances:
            _logger.info("No instances found with enabled import scheduler.")
            return

        from_date = to_date = fields.Date.today()
        date_query = f"payout_date:>={from_date.strftime(DATE_FORMAT)} AND payout_date:<={to_date.strftime(DATE_FORMAT)}"
        variables = {'first': 50, 'query': date_query}

        for instance in instances:
            _logger.info(f"Starting payout data import for instance {instance.id} on {to_date}.")

            imported_payout_data = ShopifyApi(instance).import_raw_data(query_name='GetPayoutReport',
                                                                        variables=variables)

            created_payout = self.env['shopify.payout.report'] \
                .with_context(payout_date=to_date) \
                .create_payout_report_from_shopify(instance.id,
                                                imported_payout_data)

            if created_payout:
                _logger.info(f"Payout data successfully created for instance {instance.id}.")
            else:
                _logger.warning(f"Failed to create payout data for instance {instance.id}.")

    # For Testing
    def generate_bank_statement(self):
        line_ids = []
        for data in self.transaction_line_ids:
            sale_order = self.env['sale.order'].search([('shopify_graphql_id', '=', data.order_id)])

            # Skip record if order doesn't sync in odoo
            if sale_order:
                continue
            if len(sale_order.invoice_ids) == 1:
                continue

            journal_id = self.company_id.payout_report_journal_id
            line = {
                'move_id': sale_order.invoice_ids.id,
                'amount': data.amount,
                'payment_ref': data.order_reference,
                'date': self.payout_date,
                'partner_id': sale_order.partner_id.id,
                'journal_id': journal_id.id if journal_id else False,
            }
            line_ids.append(line)

        bank_statement = self.env['account.bank.statement'].create(
            {
                'journal_id': journal_id,
                'line_ids': [Command.create(line) for line in line_ids]
            }
        )
        self.write({'status': 'validate'})

        shopify_bank_statement = self.env['shopify.bank.statement'].create({
            'line_ids': Command.link(bank_statement.line_ids.ids)
        })

        view_id = self.env.ref('sk_shopify_connector_for_odoo.shopify_bank_statement_form_view').id
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Bank Statement'),
            'res_model': 'shopify.bank.statement',
            'view_mode': 'form',
            'views': [[view_id, 'form']],
            'res_id': shopify_bank_statement.id,
        }
        return clean_action(action, self.env)


class ShopifyPayoutReportLine(models.Model):
    _name = 'shopify.payout.report.line'
    _description = 'Shopify Payout Report Line'

    payout_id = fields.Many2one('shopify.payout.report',
                                string="Payout Report",
                                index=True,
                                required=True,
                                ondelete="cascade")
    transaction_type = fields.Char("Balance Transaction Type")
    transaction_id = fields.Char("Transaction ID")
    graphql_id = fields.Char('GraphQL ID')
    order_reference = fields.Char("Order Reference")
    order_id = fields.Char('Order ID')
    net_amount = fields.Float("Net Amount")
    fees = fields.Float("Fees")
    amount = fields.Float("Amount")
