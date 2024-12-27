# -*- coding: utf-8 -*-

import logging
import shopify
import json
import base64

from pathlib import Path
from .shopify_exception import ShopifyError
from odoo.exceptions import ValidationError
from odoo import _

_logger = logging.getLogger(__name__)

RETRY_AFTER_LIMIT_HIT = 5
MAX_RETRIES = 5
QUERY_PATH = './scripts/shopify_query.graphql'
FIRST_DATA = 50  # Number of data on every paginated.


class ShopifyApi:
    def __init__(self, credentials):
        credentials.ensure_one()
        self.shop_url = credentials.shop_url
        self.api_version = credentials.api_version
        self.api_key = credentials.api_key

    def _initialize_shopify_session(self):
        session = shopify.Session(self.shop_url, self.api_version, self.api_key)
        shopify.ShopifyResource.activate_session(session)
        return session

    def _close_session(self):
        _logger.info('Closing the current shopify session.')
        shopify.ShopifyResource.clear_session()

    def __get_query_filepath(self):
        """
        Reads the GraphQL query from the specified file.
        """
        file_path = Path(__file__).parent / 'scripts' / 'shopify_query.graphql'
        return file_path.read_text()

    def _fetch_data(self, query_name, variables):
        """
        Fetch a single page of data from Shopify API.

        :param query_name: GraphQL operation name (e.g., 'GetLocations', 'GetProducts')
        :param variables: Dictionary of variables to be passed into the GraphQL query
        :return: Result of GraphQL query execution
        """
        document = self.__get_query_filepath()

        result = shopify.GraphQL().execute(
            query=document,
            variables=variables,  # Dynamic variables passed here
            operation_name=query_name
        )
        return result

    def _fetch_paginated_data(self, query_name, first=FIRST_DATA, extra_variables=None, key_value=None):
        """
        Fetch the paginated data.

        :param query_name: GraphQL operation name (e.g., 'GetLocations', 'GetProducts')
        :param first: Number of items to fetch per page
        :param extra_variables: Additional dynamic variables to be included in the query
        :param key_value: Key value to get the data in returned dictionary.
        :return: All items from paginated API call
        """
        cursor = None
        all_items = []

        while True:
            variables = {
                "first": first,
                "after": cursor
            }

            if extra_variables:
                variables.update(extra_variables)

            result = self._fetch_data(query_name, variables)
            result = json.loads(result)
            _logger.info('Result Test 1: %s', result)
            items = result.get('data', {}).get(key_value, {}).get('edges', [])
            all_items.extend(items)

            page_info = result.get('data', {}).get(key_value, {}).get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)

            if items:
                cursor = items[-1].get('cursor')

            if not has_next_page:
                break

        return all_items

    def import_data(self, query_name, extra_variables=None, key_value=None):
        """
        Main method to import data using the paginated fetching function.

        :param query_name: GraphQL operation name (e.g., 'GetLocations', 'GetProducts')
        :param extra_variables: Additional dynamic variables for the GraphQL query
        :param key_value: Key value to get the data in returned dictionary.
        :return: All imported data
        """
        self._initialize_shopify_session()
        try:
            data = self._fetch_paginated_data(query_name=query_name, extra_variables=extra_variables, key_value=key_value)
        finally:
            self._close_session()

        return data

    def import_raw_data(self, query_name, variables=None):
        """
        Main method to import raw data using the fetch_data function.

        :param query_name: GraphQL operation name (e.g., 'GetLocations', 'GetProducts')
        :param variables: Additional dynamic variables for the GraphQL query

        :return: Imported raw data
        """

        self._initialize_shopify_session()
        try:
            data = self._fetch_data(query_name=query_name, variables=variables)
            result = json.loads(data)
        finally:
            self._close_session()

        return result

    def export_data(self, query_name, payload=None, key_value=None):
        """
        Main method to export data using the paginated fetching function.

        :param query_name: GraphQL operation name (e.g., 'GetLocations', 'GetProducts')
        :param payload: Additional dynamic variables for the GraphQL query
        :param key_value: Key value to get the data in returned dictionary.
        :return: All exported data
        """
        self._initialize_shopify_session()
        try:
            data = self._fetch_paginated_data(query_name=query_name, extra_variables=payload, key_value=key_value)
        finally:
            self._close_session()

        return data

    def _test_connection(self):
        try:
            self._initialize_shopify_session()

            query = '{ shop { name id } }'
            response = shopify.GraphQL().execute(query)
            if not response:
                return {'error': "No response received from Shopify."}

            result = json.loads(response)
            shop_id = result.get('data', {}).get('shop', {}).get('id')

            if not shop_id:
                return {'error': "Shop ID not found in Shopify response."}
            return shop_id

        except Exception as err:
            _logger.error('Test Connection Failed: %s', err)
            error_message = f"Test Connection Failed: {err}"
            return {'error': error_message}
        finally:
            self._close_session()

    def export_image_data(self, product_id, attachment):
        self._initialize_shopify_session()
        try:
            image_attachment = base64.b64decode(attachment)
            new_image = shopify.Image()
            new_image.product_id = product_id
            new_image.attach_image(image_attachment)
            new_image.save()
        finally:
            self._close_session()
