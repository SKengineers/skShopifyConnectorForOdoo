/** @odoo-module */

import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart } from "@odoo/owl";

export class ShopifyQueueDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        onWillStart(async () => {
            this.queueData = await this.orm.call("shopify.queue", "retrieve_dashboard");
            
        });


    }

    /**
     * This method clears the current search query and activates
     * the filters found in `filter_name` attibute from button pressed
     */
    setSearchContext(ev) {
        const xml_id = this.action.currentController.action.xml_id; 
        const action = xml_id.split('.').pop();

        let filter_name = ev.currentTarget.getAttribute("filter_name");
        let filters = filter_name.split(",");

        // Define a mapping for action to filter names
        const actionFilterMap = {
            shopify_queue_order_action: 'orders',
            shopify_queue_product_action: 'products',
            shopify_queue_customer_action: 'customers',
            shopify_queue_location_action: 'locations',
            shopify_queue_stock_action: 'stocks',
        };

        // if (action in actionFilterMap) {
        //     filters.push(actionFilterMap[action]);
        // }

        const searchItems = this.env.searchModel.getSearchItems((item) =>
            filters.includes(item.name)
        );
        this.env.searchModel.query = [];
        for (const item of searchItems) {
            this.env.searchModel.toggleSearchItem(item.id);
        }
    }
}

ShopifyQueueDashboard.template = "sk_shopify_connector_for_odoo.ShopifyQueueDashboard";
