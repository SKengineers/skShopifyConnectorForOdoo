# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, Command, _

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    shopify_id = fields.Char('Shopify ID')
    shopify_refund_id = fields.Char('Shopify Refund ID')

    shopify_instance_id = fields.Many2one('shopify.instance', ondelete='cascade')
    is_exported = fields.Boolean('Synced In Shopify', default=False)
    is_refund = fields.Boolean('Is refunded', default=False)

    def action_refund_shopify(self):
        return {
            'name': _('Refund in Shopify'),
            'res_model': 'cancel.refund.order.shopify.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('sk_shopify_connector_for_odoo.cancel_refund_order_wizard_form_view').id,
            'views': [[False, 'form']],
            'context': {
                'active_model': 'account.move',
                'active_ids': self.ids,
                'default_transaction_type': 'refund_order',
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }
