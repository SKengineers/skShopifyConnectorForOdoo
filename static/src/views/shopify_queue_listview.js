/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";
import { ShopifyQueueDashboard } from '@sk_shopify_connector_for_odoo/views/shopify_queue_dashboard';

export class QueueDashboardRenderer extends ListRenderer {};

QueueDashboardRenderer.template = 'sk_shopify_connector_for_odoo.QueueListView';
QueueDashboardRenderer.components= Object.assign({}, ListRenderer.components, {ShopifyQueueDashboard})

export const QueueDashboardListView = {
    ...listView,
    Renderer: QueueDashboardRenderer,
};

registry.category("views").add("shopify_queue_dashboard_list", QueueDashboardListView);
