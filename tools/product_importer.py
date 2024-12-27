import base64
import csv
import logging
from io import StringIO
from odoo import Command, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ProductDataImporter:
    def __init__(self, env):
        self.env = env

    def import_data(self, file_data, filename):
        """
        Import product data from a file.

        :param file_data: The base64-encoded file data.
        :param filename: The name of the file (used to determine file type).
        :return: A list of imported product records.
        """

        if not filename.lower().endswith('.csv'):
            raise ValidationError(_('Only CSV files are supported.'))

        try:
            decoded_file = base64.b64decode(file_data)
        except (base64.binascii.Error, ValidationError) as e:
            _logger.error('Failed to decode file: %s', e)
            raise ValidationError(_('Invalid file data. Please provide a valid base64-encoded CSV file.'))

        try:
            data = self._read_csv(decoded_file)
            imported_records = self._process_product_data(data)
            _logger.info('Successfully imported %d records.', len(imported_records))
        except Exception as e:
            _logger.error('Error processing product data: %s', e)
            raise ValidationError(_(f'Error processing data: {str(e)}'))

        return imported_records

    def _read_csv(self, file_data):
        """
        Read the CSV file data.

        :param file_data: The decoded CSV file content.
        :return: A list of dictionaries containing the CSV data.
        """
        file_content = file_data.decode('utf-8')
        csv_reader = csv.DictReader(StringIO(file_content))
        return list(csv_reader)

    def _process_product_data(self, data):
        """
        Process the data and create or update products.

        :param data: List of dictionaries containing the product data.
        :return: A list of created or updated product record IDs.
        """
        imported_records = []
        product_model = self.env['product.template']

        product_names = [row.get('Title') for row in data if row.get('Title')]
        existing_products = product_model.search([('name', 'in', product_names)])
        existing_product_map = {prod.name: prod for prod in existing_products}

        for row in data:
            title = row.get('Title')
            tags = row.get('Tags')
            if not title:
                continue

            # Prepare data for product creation or update
            product_category = row.get('Product Category', '').lower()
            product_category = 'product' if product_category == 'storable product' else 'service' if product_category == 'service' else 'product'
            price = float(row.get('Variant Price', 0) or 0)

            product_vals = {
                'name': title,
                'detailed_type': product_category,
                'sale_ok': True,
                'purchase_ok': True,
                'list_price': price,
            }

            if tags:
                product_vals['product_tag_ids'] = self._prepare_product_tags(tags)

            product_template = existing_product_map.get(title)

            if product_template:
                product_template.write(product_vals)
            else:
                product_template = product_model.create(product_vals)

            imported_records.append(product_template.id)

        return imported_records

    def _prepare_product_tags(self, tags):
        # Add a tag
        tag_cmd = []

        for tag in tags.split(','):
            name_tag = tag.strip()
            check_tag = self.env['product.tag'].search([('name', '=', name_tag)])
            if check_tag:
                tag_cmd.append(Command.link(check_tag.id))
            else:
                tag_cmd.append(Command.create({'name': name_tag}))
        return tag_cmd
