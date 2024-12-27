# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    shopify_instance_id = fields.Many2one(comodel_name="shopify.instance",
                                          string="Instance")
    # Future Roadmap - Add Comprehensive settings
    # Product Configuration
    sale_team_id = fields.Many2one('crm.team', string="Sales Team")
    is_import_images = fields.Boolean(string='Shopify Sync/Import Images')
    pricelist_id = fields.Many2one('product.pricelist', string="Pricelist")
    # Payout Report
    payout_report_journal_id = fields.Many2one('account.journal', string='Payout Report Journal')
