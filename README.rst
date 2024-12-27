SK Shopify Connector for Odoo
=========
* Shopify Connector for Odoo 17

Installation
------------

Install the package using pip:

.. code-block:: bash

    pip install ShopifyApi


How-to guide
------------

For full guide refer to this Link:

How to Guide in SK Shopify Connector App for Odoo

This guide provides a detailed walkthrough for installing and configuring the SK Shopify Connector App for Odoo. It also includes instructions for synchronizing Shopify operations like products, orders, and customers with Odoo, ensuring seamless integration.
Installation
Before installing the Shopify Connector App, ensure the required Python dependency is installed.
●	https://pypi.org/project/ShopifyAPI/
●	pip install ShopifyAPI

Setup: SK Shopify Odoo connector
Generate API Key in Shopify

1.	In your Shopify Admin Panel, type "Build Custom Apps" in the search bar.

2.	Click Create an App, provide the App Name, and select Create App.

3.	Set Admin API Permissions
Navigate to Configuration > Admin API integration:
●	Grant appropriate permissions to ensure proper synchronization between Shopify and Odoo.



4.	Generate Access Token
●	Go to the API Credentials tab.
●	Click Install App to generate the Access Token.




Create an Instance
In Odoo, navigate to Shopify > Create Instance. Follow the prompts to set up the Shopify instance for managing multiple accounts.




Upon successful completion of the instance, you can directly manage the configuration of the instance from the same panel.

Shopify Configuration in Odoo
Webhook Configuration
Enable Webhooks to automatically sync Shopify operations with Odoo. Below are the key webhook routes:

Refer on this router configuration:
●	Product Creation: /shopify_api/products/create
●	Product Update: /shopify_api/products/updated
●	Product Delete: /shopify_api/products/delete
●	Order Update: /shopify_api/orders/updated
●	Customer Create: /shopify_api/customers/create
●	Customer Update: /shopify_api/customers/update


Enable Scheduler
To automate operations like Import Order, Export Stock, and more, enable the Import Scheduler checkbox in the instance window.



Auto Workflow
It will save you a handsome amount of time, especially when the sales figure is higher than average. Navigate to Shopify > Configurations > Sale Auto Workflow

Payment Gateway
Configure payment options such as E-Wallets, Credit/Debit Cards, or Bank Wire.
Navigate to Shopify > Configuration > Payment Gateway.


Financial Status
Once you have successfully configured Workflow settings and added Payment Gateway, you will be able to configure your financial status. By configuring financial status, you can choose which orders you would like to import, the ones of which financial status is paid or unpaid.

Navigate to Shopify > Configuration > Financial Status











Shopify - Odoo Operations
Import Location
Import location allows you to import Shopify Location from Shopify Store to Odoo. It will fetch the active/deactivate locations. This operation will create a location record under Shopify / Configuration / Shopify Locations.

Import Customer
This operation starts fetching customers’ data from Shopify stores and will just add that data in Customer Queue for processing. (Shopify / Processes / Queues Logs / Customers).

Shopify - Product Operations
Import Products
You can Import Products from Shopify to Odoo by navigating to Shopify Dashboard > Operations. However, there are two types of Product Imports which can be carried out via this operation.
	Create Date: By selecting this option, all the products which were created on the specified date range will be imported into your Odoo. Add the date ranges just below to it.
	Update Date:By selecting this option, all the products which were updated on the specified date range will be imported into your Odoo.







Map Products
This operation allows importing Odoo Products to the Shopify layer. Uploading a csv file from shopify can import a product to odoo.

Import Stock
Import stock allows importing product stock from Shopify stores to Odoo. 


Export Stock

The export stock allows export product stock to Shopify stores for configured Shopify Locations.


Export Product

To export Odoo products to Shopify, go to Sales > Products (remove the filter search), select one or more products, then click Actions > Export to Shopify Middle Layer.

Go to Product > Product to verify if the product is in the middle layer, then click Operation > Export Product.

Shopify - Order Operations
Import Shipped Orders
Imports orders that have been shipped. Navigate to Operation > Import Shipped Orders

Import Unshipped Orders
Imports orders that are yet to be shipped. Navigate to Operation > Import Unshipped Orders

Import Cancel Orders
Import canceled orders based on the date range in sync options tab.  Navigate to Operation > Import Cancel Orders




Import Specific Orders
Imports or manages specific orders based on criteria.




Cancel Sales Order in Shopify
To cancel an order in Shopify from Odoo, set the sales order to the Cancelled state in Odoo, then click Cancel in Shopify. This will synchronize the cancellation with Shopify automatically.



Refund in Shopify

You can process refunds in Shopify directly from Odoo. After posting the invoice in Odoo, go to the order details and click Refund in Shopify. Fill in the required refund details, such as the amount and reason for the refund, and then click Refund in Shopify to complete the process. This syncs the refund action with Shopify automatically.




Payout Report
Shopify Payout is the simplest way to accept payments online. It eliminates the hassle of setting up a merchant account with a third-party payment provider and then entering your account credentials in Shopify. Navigate to Shopify > Operation > Import Payout Report.


Release Notes
Version 1.0.0
New Features
●	
Improvements
●	
Bug Fixes
●	
Future Roadmap
●	Improved UI for instance management and error reporting.
●	Enhanced scheduler options for custom intervals.
●	Improved Performance in import bulk operation in GraphQL.
●	Information banner on window for a quick guide.
●	Minimal reference on the module name (When renaming the app)

