# -*- coding: utf-8 -*-

import logging
import json
from odoo import models, fields, _
from ..tools.shopify_api_v2 import ShopifyApi
from odoo.exceptions import ValidationError
_logger = logging.getLogger(__name__)


class ShopifyInstance(models.Model):
    _name = 'shopify.instance'
    _description = 'Shopify Instances'

    name = fields.Char(string="Instance Name", required=True)
    api_key = fields.Char(string="API Key", required=True)
    password = fields.Char(string="Password")
    api_version = fields.Char(string="API Version", required=True)
    shop_url = fields.Char(string="Shop URL")
    is_active = fields.Boolean(string="Active")
    is_authenticate = fields.Boolean(string="Authenticated", default=False)
    webhook_ids = fields.One2many('shopify.webhook', 'instance_id', string='Webhook', copy=False)
    dashboard_graph_data = fields.Text(compute='_kanban_dashboard_graph')
    active = fields.Boolean(string='Active', default=True)
    is_import_scheduler = fields.Boolean(string='Import Scheduler', default=False)
    _sql_constraints = [
        ('unique_api_key_name', 'unique(api_key, name)', 'The combination of API Key and Instance Name must be unique.')
    ]

    def button_test_connection(self):
        response = ShopifyApi(self)._test_connection()

        if isinstance(response, dict):
            if response.get('error'):
                self.is_authenticate = False
            # error_message = response.get('error')
            # raise ValidationError(_(error_message))
        else:
            self.is_authenticate = True

    def action_perform_operation(self):
        return True

    def _kanban_dashboard_graph(self):
        if not self._context.get('sort'):
            context = dict(self.env.context)
            context.update({'sort': 'month'}) #default chart view for order data
            self.env.context = context

        for rec in self:
            values = rec.get_dashboard_data_shopify(rec)
            sales_total = round(sum([key['y'] for key in values]), 2)
            shopify_orders_data = rec.get_total_orders()
            shopify_products_data = rec.get_products()
            shopify_customers_data = rec.get_customers()
            rec.dashboard_graph_data = json.dumps({
                "title": "",
                "key": "Untaxed Amount",
                "values": values,
                "sort_on": self._context.get('sort'),
                "sales_total": sales_total,
                "shop_orders": shopify_orders_data,
                "shop_products": shopify_products_data,
                "shop_customers": shopify_customers_data,
                "shop_currency_symbol": '',
            })

    def get_dashboard_data_shopify(self, record):

        def graph_data_year(record):
            self._cr.execute("""select TRIM(TO_CHAR(DATE_TRUNC('month',month),'MONTH')),sum(amount_untaxed) from
                                    (
                                    SELECT
                                      DATE_TRUNC('month',date(day)) as month,
                                      0 as amount_untaxed
                                    FROM generate_series(date(date_trunc('year', (current_date)))
                                        , date(date_trunc('year', (current_date)) + interval '1 YEAR - 1 day')
                                        , interval  '1 MONTH') day
                                    union all
                                    SELECT DATE_TRUNC('month',date(date_order)) as month,
                                    sum(amount_untaxed) as amount_untaxed
                                      FROM   sale_order
                                    WHERE  date(date_order) >= (select date_trunc('year', date(current_date))) AND date(date_order)::date <= (select date_trunc('year', date(current_date)) + '1 YEAR - 1 day')
                                    and shopify_instance_id = %s and state in ('sale','done')
                                    group by DATE_TRUNC('month',date(date_order))
                                    order by month
                                    )foo 
                                    GROUP  BY foo.month
                                    order by foo.month""" % record.id)
            return self._cr.dictfetchall()

        def graph_data_month(record):
            self._cr.execute("""select EXTRACT(DAY from date(date_day)) :: integer,sum(amount_untaxed) from (
                        SELECT 
                          day::date as date_day,
                          0 as amount_untaxed
                        FROM generate_series(date(date_trunc('month', (current_date)))
                            , date(date_trunc('month', (current_date)) + interval '1 MONTH - 1 day')
                            , interval  '1 day') day
                        union all
                        SELECT date(date_order)::date AS date_day,
                        sum(amount_untaxed) as amount_untaxed
                          FROM   sale_order
                        WHERE  date(date_order) >= (select date_trunc('month', date(current_date)))
                        AND date(date_order)::date <= (select date_trunc('month', date(current_date)) + '1 MONTH - 1 day')
                        and shopify_instance_id = %s and state in ('sale','done')
                        group by 1
                        )foo 
                        GROUP  BY 1
                        ORDER  BY 1""" % record.id)
            return self._cr.dictfetchall()

        def graph_data_week(record):
            self._cr.execute("""SELECT to_char(date(d.day),'DAY'), t.amount_untaxed as sum
                                FROM  (
                                   SELECT day
                                   FROM generate_series(date(date_trunc('week', (current_date)))
                                    , date(date_trunc('week', (current_date)) + interval '6 days')
                                    , interval  '1 day') day
                                   ) d
                                LEFT   JOIN 
                                (SELECT date(date_order)::date AS day, sum(amount_untaxed) as amount_untaxed
                                   FROM   sale_order
                                   WHERE  date(date_order) >= (select date_trunc('week', date(current_date)))
                                   AND    date(date_order) <= (select date_trunc('week', date(current_date)) + interval '6 days')
                                   AND shopify_instance_id=%s and state in ('sale','done')
                                   GROUP  BY 1
                                   ) t USING (day)
                                ORDER  BY day;""" % record.id)
            return self._cr.dictfetchall()

        def graph_data_all(record):
            self._cr.execute("""select TRIM(TO_CHAR(DATE_TRUNC('month',date_order),'YYYY-MM')),sum(amount_untaxed)
                                from sale_order where shopify_instance_id = %s and state in ('sale','done')
                                group by DATE_TRUNC('month',date_order) order by DATE_TRUNC('month',date_order)""" %
                             record.id)
            return self._cr.dictfetchall()

        if self._context.get('sort') == 'week':
            result = graph_data_week(record)
        elif self._context.get('sort') == "month":
            result = graph_data_month(record)
        elif self._context.get('sort') == "year":
            result = graph_data_year(record)
        else:
            result = graph_data_all(record)

        values = [{"x": ("{}".format(data.get(list(data.keys())[0]))), "y": data.get('sum') or 0.0} for data in result]

        return values

    def get_total_orders(self):

        query = """select id from sale_order where shopify_instance_id= %s and state in ('sale','done')""" % self.id

        def week_orders(query):
            w_query = query + " and date(date_order) >= (select date_trunc('week', date(current_date))) order by date(date_order)"
            self._cr.execute(w_query)

            return self._cr.dictfetchall()

        def month_orders(query):
            m_query = query + " and date(date_order) >= (select date_trunc('month', date(current_date))) order by date(date_order)"
            self._cr.execute(m_query)

            return self._cr.dictfetchall()

        def year_orders(query):
            y_query = query + " and date(date_order) >= (select date_trunc('year', date(current_date))) order by date(date_order)"
            self._cr.execute(y_query)
            return self._cr.dictfetchall()

        def all_orders(record):
            self._cr.execute(
                """select id from sale_order where shopify_instance_id = %s and state in ('sale','done')""" % record.id)

            return self._cr.dictfetchall()

        shop_orders = {}
        if self._context.get('sort') == "week":
            result = week_orders(query)
        elif self._context.get('sort') == "month":
            result = month_orders(query)
        elif self._context.get('sort') == "year":
            result = year_orders(query)
        else:
            result = all_orders(self)

        order_ids = [data.get('id') for data in result]
        view = self.env.ref('sk_shopify_connector_for_odoo.action_shopify_order').read()[0]
        action = self.create_action(view, [('id', 'in', order_ids)])
        shop_orders.update({
            'order_count': len(order_ids),
            'order_action': action})
        return shop_orders

    def get_products(self):
        shop_products = {}
        total_count = 0

        self._cr.execute(
            """select count(id) as total_count from product_template where shopify_instance_id = %s""" % self.id)
        result = self._cr.dictfetchall()

        if result:
            total_count = result[0].get('total_count')

        view = self.env.ref('sk_shopify_connector_for_odoo.action_shopify_product_template').read()[0]
        action = self.create_action(view, [('shopify_instance_id', '=', self.id)])
        shop_products.update({
            'product_count': total_count,
            'product_action': action
        })

        return shop_products

    def get_customers(self):
        shop_customers = {}
        self._cr.execute("""select id from res_partner where shopify_instance_id = %s""" % self.id)
        result = self._cr.dictfetchall()
        customer_ids = [data.get('partner_id') for data in result]
        view = self.env.ref('sk_shopify_connector_for_odoo.action_shopify_res_partner').read()[0]
        action = self.create_action(view, [('shopify_instance_id', '=', self.id)])

        shop_customers.update({
            'customer_count': len(customer_ids),
            'customer_action': action
        })

        return shop_customers

    def create_action(self, view, domain):
        action = {
            'name': view.get('name'),
            'type': view.get('type'),
            'domain': domain,
            'view_mode': view.get('view_mode'),
            'view_id': view.get('view_id')[0] if view.get('view_id') else False,
            'views': view.get('views'),
            'res_model': view.get('res_model'),
            'target': view.get('target'),
        }

        if 'tree' in action['views'][0]:
            action['views'][0] = (action['view_id'], 'list')

        return action
