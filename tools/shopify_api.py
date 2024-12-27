# -*- coding: utf-8 -*-

import logging
import requests
import time
from .shopify_exception import ShopifyError

_logger = logging.getLogger(__name__)

CONTENT_TYPE = 'application/json'
DEFAULT_ENDPOINT = 'https://{shop}.myshopify.com/admin/api/{api_version}'
TIMEOUT_SEC = 10
RETRY_AFTER_LIMIT_HIT = 5
MAX_RETRIES = 5


class ShopifyApi:
    def __init__(self, credentials):
        credentials.ensure_one()
        self.shop_name = credentials.shop_name
        self.shop_url = credentials.shop_url
        self.api_version = credentials.api_version
        self.api_key = credentials.api_key
        self.password = credentials.password
        self.secret = None

    def __api_requests(self, request_type, url, params=None, headers=None, result_key=None, **kwargs):
        headers = self._prepare_headers(headers)
        url_call = self._build_url(url)
        all_results = []  # List to store all results across pages

        while True:
            try:
                res = self._make_request(request_type, url_call, params, headers, **kwargs)
                if request_type == 'POST':
                    _logger.info('RESPONSE TEST %s', res.json())
                    return res.json()

                all_results.extend(res.json().get(result_key, [])) if result_key else all_results.extend(res.json())

                next_page_url = self._get_next_page_url(res.headers.get('Link'))
                if not next_page_url:
                    break
                url_call = next_page_url
                params = {}

            except requests.exceptions.RequestException as e:
                _logger.error(f"API request failed: {e}")
                raise ShopifyError(failure_type='network')

        return all_results

    def _prepare_headers(self, headers):
        """Prepare request headers."""
        headers = headers or {}
        if self.api_key:
            headers.update({
                'Content-Type': 'application/json',
                'X-Shopify-Access-Token': self.api_key
            })
        return headers

    def _build_url(self, url):
        """Build request URL."""
        custom_url = (self.shop_url or '') + '/admin/api/' + self.api_version
        return (
            DEFAULT_ENDPOINT.format(shop=self.shop_name, api_version=self.api_version) + url
        )

    def _make_request(self, request_type, url_call, params, headers, **kwargs):
        """Make the API request with retry for rate limit."""
        retry_attempts = 0
        while retry_attempts < MAX_RETRIES:
            try:
                res = requests.request(request_type, url_call, params=params, headers=headers, timeout=TIMEOUT_SEC, **kwargs)
                res.raise_for_status()
                return res

            except requests.exceptions.HTTPError as e:
                if res.status_code == 429:  # Rate limit exceeded
                    retry_after = int(res.headers.get('Retry-After', RETRY_AFTER_LIMIT_HIT))
                    _logger.warning(f"Rate limit exceeded, retrying in {retry_after} seconds...")
                    time.sleep(retry_after)  # Wait before retrying
                    retry_attempts += 1
                else:
                    _logger.error(f"HTTP error: {e}")
                    raise ShopifyError(failure_type='http_error')

    def _get_next_page_url(self, link_header):
        if not link_header:
            return None

        links = link_header.split(',')
        for link in links:
            if 'rel="next"' in link:
                next_url = link[link.find('<') + 1:link.find('>')]
                return next_url
        return None

    def _test_connection(self, url='/shop.json'):
        _logger.info('Test Connection for Shopify API.')
        response = self.__api_requests(request_type='GET', url=url)
        return response.json()

    def _import_products(self, url='/products.json', params=None):
        _logger.info('Import Products from Shopify API.')
        response = self.__api_requests(request_type='GET', url=url, result_key='products', params=params)
        return response

    def _export_products(self, url='/products.json', data={}):
        _logger.info('Export Products to Shopify API.')
        payload = {
            'product': data
        }
        response = self.__api_requests(request_type='POST', url=url, json=payload)
        return response

    def _import_customers(self, url='/customers.json', params=None):
        _logger.info('Import Customers from Shopify API.')
        response = self.__api_requests(request_type='GET', url=url, result_key='customers', params=params)
        return response

    def _import_orders(self, url='/orders.json', params={}):
        _logger.info('Import Orders from Shopify API.')
        params.update({'status': 'open'})
        response = self.__api_requests(request_type='GET', url=url, result_key='orders', params=params)
        return response

    def _import_cancel_orders(self, url='/orders.json', params={}):
        _logger.info('Import Orders from Shopify API.')
        params.update({'status': 'cancelled'})
        response = self.__api_requests(request_type='GET', url=url, result_key='orders', params=params)
        return response

    def _export_order(self, url='/orders.json', data=None):
        _logger.info('Export Orders to Shopify API.')
        payload = {
            'order': data
        }
        return self.__api_requests(request_type='POST', url=url, json=payload)

    def _import_locations(self, url='/locations.json', params={}):
        _logger.info('Import Locations from Shopify API.')
        response = self.__api_requests(request_type='GET', url=url, result_key='locations', params=params)
        return response

    def _import_stocks(self, url='/inventory_levels.json', params={}):
        _logger.info('Import Stocks from Shopify API.')
        response = self.__api_requests(request_type='GET', url=url, result_key='inventory_levels', params=params)
        return response

    def _export_stocks(self, url='/inventory_levels/set.json', data={}):
        _logger.info('Export Stocks to Shopify API. ')
        response = self.__api_requests(request_type='POST', url=url, json=data)
        return response
