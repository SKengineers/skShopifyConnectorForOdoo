# -*- coding: utf-8 -*-
from odoo import _


class ShopifyError(Exception):
    def __init__(self, message='', error_code=False, failure_type=False):
        """Handle errors for Shopify API, storing error codes.

        :param str message: An error message
        :param int error_code: Shopify error code
        :param str failure_type: Failure Type Message
        """

        self.failure_type = failure_type
        self.error_code = error_code
        self.error_message = message

        formated_message = ''
        if error_code:
            formated_message = f'{error_code}: {message}'
        elif failure_type == 'api_account':
            formated_message = _("Shopify connection is misconfigured.")
        elif failure_type == 'network':
            formated_message = _("Shopify could not be reached or the query was malformed.")
        elif failure_type == 'http_error':
            formated_message = _("Shopify HTTP Client Error. Check your http request if invalid.")
        elif failure_type == 'rate_limit':
            formated_message = _("Shopify rate limit has been reached. Please try again in a minute.")
        else:
            formated_message = _("Unknown error when processing shopify api request.")

        # Shopify Error code
        if error_code == 400:
            formated_message = _("Required parameter missing or invalid.")
        elif error_code == 402:
            formated_message = _("This shop's plan does not have access to this feature")
        elif error_code == 403:
            formated_message = _("User does not have access")
        elif error_code == 404:
            formated_message = _("Not Found")
        elif error_code == 405:
            formated_message = _("This shop is unavailable")
        elif error_code == 500:
            formated_message = _("An unexpected error occurred")
        super().__init__(formated_message)
