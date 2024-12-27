# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, Command
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ShopifyPaymentGateway(models.Model):
    _name = 'shopify.payment.gateway'

    name = fields.Char(string='Name')
    code = fields.Char(string='Code')
    active = fields.Boolean(string='Active', default=True)
    shopify_instance_id = fields.Many2one(comodel_name='shopify.instance', string='Instance ID')

    @api.constrains('name', 'code', 'shopify_instance_id')
    def _check_unique_name_code_instance(self):
        for record in self:
            duplicate = self.search([
                ('name', '=', record.name),
                ('code', '=', record.code),
                ('shopify_instance_id', '=', record.shopify_instance_id.id),
                ('id', '!=', record.id)
            ])
            if duplicate:
                raise ValidationError("A payment gateway with the same Name, Code, and Shopify Instance already exists.")
