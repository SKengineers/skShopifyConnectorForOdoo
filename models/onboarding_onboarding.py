# -*- coding: utf-8 -*-
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

class Onboarding(models.Model):
    _inherit = 'onboarding.onboarding'

    @api.model
    def action_close_panel_shopify_instance_dashboard(self):
        self.action_close_panel('sk_shopify_connector_for_odoo.action_close_panel_shopify_instance_dashboard')

    # TODO: Improvement on this.
    def _prepare_rendering_values(self):
        """ Rendering the values """
        self.ensure_one()
        if self == self.env.ref('sk_shopify_connector_for_odoo.onboarding_onboarding_shopify_instance_dashboard',
                                raise_if_not_found=False):
            # Setup Instance
            step1 = self.env.ref('sk_shopify_connector_for_odoo.onboarding_step_setup_instance', raise_if_not_found=False)
            if step1 and step1.current_step_state == 'not_done':
                if self.env['shopify.instance'].search([], limit=1):
                    step1.action_set_just_done()

            # Manage Configuration
            step2 = self.env.ref('sk_shopify_connector_for_odoo.onboarding_step_manage_configuration', raise_if_not_found=False)
            if step2 and step2.current_step_state == 'not_done':
                setting = self.env['ir.config_parameter'].sudo().get_param('sk_shopify_connector_for_odoo.shopify_instance_id') or False
                # if setting:
                #     step2.action_set_just_done()

            # Configure Financial Status
            step3 = self.env.ref('sk_shopify_connector_for_odoo.onboarding_step_setup_financial_status', raise_if_not_found=False)
            if step3 and step3.current_step_state == 'not_done':
                if self.env['shopify.financial.status'].search([], limit=1):
                    step3.action_set_just_done()

        return super()._prepare_rendering_values()
