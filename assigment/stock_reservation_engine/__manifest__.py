{
    'name': 'Stock Reservation Engine',
    'version': '18.0.1.5.0',
    'summary': 'Reservation and allocation engine with API exposure',
    'description': """
Stock reservation and allocation engine with FEFO/FIFO logic, HTTP API, and demo data.

Screenshots and visuals live under standard Odoo paths: ``static/description/screenshots/capture/`` (UI tour) and ``static/description/screenshots/walkthrough/`` (delivery set). See ``static/description/screenshots/README.md``.
""",
    'author': 'OpenAI',
    'license': 'LGPL-3',
    'category': 'Inventory/Inventory',
    'depends': ['stock', 'mail', 'product_expiry'],
    'images': [
        'static/description/screenshots/capture/04-reservation-batches-list.png',
        'static/description/screenshots/capture/06-reservation-batch-draft.png',
        'static/description/screenshots/capture/07-api-tokens-list.png',
        'static/description/screenshots/capture/22-inventory-overview-kanban.png',
        'static/description/screenshots/capture/27-stock-reservations-menu-expanded.png',
    ],
    'data': [
        'security/reservation_security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/demo_inventory_master.xml',
        'data/reservation_demo_data.xml',
        'views/reservation_batch_views.xml',
        'views/api_token_views.xml',
        'views/reservation_menu.xml',
    ],
    'installable': True,
    'application': True,
    'post_init_hook': 'post_init_hook',
}
