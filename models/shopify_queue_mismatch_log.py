# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class ShopifyQueueMismatchLog(models.Model):
    _name = 'shopify.queue.mismatch.log'
    _description = 'Shopify Queue Mismatch Log'

    queue_id = fields.Many2one('shopify.queue', string='Queue Reference', required=True, ondelete='cascade')
    error_type = fields.Selection(
        [('data_error', 'Data Error'), ('sync_error', 'Sync Error'), ('validation_error', 'Validation Error')],
        string='Error Type', required=True)
    message = fields.Text(string='Message', required=True)
    data = fields.Text(string='Data', help="The raw data that caused the mismatch or error")
    timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now, readonly=True)
