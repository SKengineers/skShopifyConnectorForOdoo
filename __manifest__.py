# -*- coding: utf-8 -*-
{
    'name': "SK Shopify Connector for Odoo",

    'summary': """
      This connector streamlines operations by automating data transfer
      and synchronization, reducing manual entry and ensuring consistency
      across platforms.
    """,

    'description': """
      The SK Shopify Connector for Odoo integrates Shopify e-commerce platform
      with Odoo ERP system, enabling seamless synchronization of products,
      orders, and customer data between the two systems.
    """,

    'author': "Sritharan K",
    'company': "SK Engineer",
    'maintainer': "SK Engineer",
    'website': "https://www.skengineer.be",
    'category': "Sales",
    'version': "17.0.0.0",

    'depends': ['base', 'mail', 'account', 'stock', 'sale_management', 'account_accountant'], # type: ignore

    # always loaded
    'data': [
        'data/ir_module_category_data.xml',
        'data/ir_cron.xml',
        'data/res_groups.xml',
        'data/ir_sequence.xml',
        'data/shopify_payment_gateway.xml',
        'data/mail_activity_type_data.xml',
        'data/onboarding_data.xml',
        'data/shopify_order_status_data.xml',
        'security/ir.model.access.csv',
        'wizard/operation_shopify_wizard.xml',
        'wizard/cancel_refund_order_shopify_wizard.xml',
        'wizard/update_product_wizard.xml',
        'views/shopify_instance_views.xml',
        'views/shopify_product_views.xml',
        'views/shopify_product_variant_views.xml',
        'views/product_template_views.xml',
        'views/shopify_dashboard_views.xml',
        'views/shopify_customer_views.xml',
        'views/shopify_order_views.xml',
        'views/shopify_queue_views.xml',
        'views/shopify_location_views.xml',
        'views/res_config_settings_views.xml',
        'views/sale_order_views.xml',
        'views/res_partner_views.xml',
        'views/product_product_views.xml',
        'views/auto_workflow_views.xml',
        'views/account_move_views.xml',
        'views/shopify_payment_gateway_views.xml',
        'views/shopify_payout_report_views.xml',
        'views/shopify_financial_status_views.xml',
        'views/shopify_bank_statement_views.xml',
        'views/shopify_webhooks.xml',
        'report/shopify_sale_report_views.xml',
        'views/shopify_connector_menus.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'external_dependencies': {
        'python': ['ShopifyAPI']
    },
    'assets': {
        'web.assets_backend': [
            'sk_shopify_connector_for_odoo/static/src/scss/shopify_graph_widget.scss',
            'sk_shopify_connector_for_odoo/static/src/views/*.js',
            'sk_shopify_connector_for_odoo/static/src/views/*.xml',
            'sk_shopify_connector_for_odoo/static/src/**/*.js',
            'sk_shopify_connector_for_odoo/static/src/**/*.xml',
        ],
    },        
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,
}
