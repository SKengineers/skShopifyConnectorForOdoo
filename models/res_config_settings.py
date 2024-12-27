# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, _

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    shopify_instance_id = fields.Many2one(comodel_name="shopify.instance",
                                          config_parameter="sk_shopify_connector_for_odoo.shopify_instance_id",
                                          string="Instance")

    payout_report_journal_id = fields.Many2one(related='company_id.payout_report_journal_id',
                                               string='Payout Report Journal',
                                               readonly=False)

    shopify_instance = fields.Many2one(related='company_id.shopify_instance_id',
                                       string='Instance',
                                       readonly=False)

    # Future Roadmap - Add Comprehensive settings
    # Order Configuration
    sale_team_id = fields.Many2one(related='company_id.sale_team_id',
                                   string='Sales Team',
                                   readonly=False)
    # Product Configuration
    is_import_images = fields.Boolean(related='company_id.is_import_images',
                                      string='Shopify Sync/Import Images',
                                      readonly=False)
    pricelist_id = fields.Many2one(related='company_id.pricelist_id',
                                   string="Pricelist",
                                   readonly=False)

    def button_create_instances(self):
        return {
            'name': _('Create Instance'),
            'type': 'ir.actions.act_window',
            'res_model': 'shopify.instance',
            'view_mode': 'form',
            'view_id': self.env.ref('sk_shopify_connector_for_odoo.shopify_instance_form_view').id,
            'target': 'new',
        }
