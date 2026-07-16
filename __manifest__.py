# -*- coding: utf-8 -*-
{
    'name': "Kendroo Asset Management",

    'summary': "Enterprise asset management dashboard by Kendroo",

    'description': """
Kendroo Asset Management provides a modern OWL dashboard for tracking assets, assignments, maintenance, and depreciation.
    """,

    'author': "Kendroo Ltd",
    'website': "https://kendroo.io/",

    'category': 'Operations/Inventory',
    'version': '0.1',

    'depends': ['base', 'web', 'product', 'account', 'hr', 'purchase'],

    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/asset_sequence.xml',
        'data/depreciation_cron.xml',
        'data/sync_assignment_status.xml',
        'data/sync_asset_type_relations.xml',
        'views/dashboard_action.xml',
        'views/asset_location_views.xml',
        'views/views.xml',
        'views/templates.xml',
        'views/kio_asset_condition_views.xml',
        'views/kio_asset_type_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'kio_asset_management/static/src/js/asset_list_data.js',
            'kio_asset_management/static/src/js/add_asset_data.js',
            'kio_asset_management/static/src/js/asset_details_data.js',
            'kio_asset_management/static/src/js/asset_dashboard.js',
            'kio_asset_management/static/src/js/depreciation_dashboard.js',
            'kio_asset_management/static/src/xml/asset_dashboard.xml',
            'kio_asset_management/static/src/xml/asset_list_page.xml',
            'kio_asset_management/static/src/xml/add_asset_page.xml',
            'kio_asset_management/static/src/xml/asset_details_page.xml',
            'kio_asset_management/static/src/xml/depreciation_dashboard.xml',
            'kio_asset_management/static/src/scss/asset_dashboard.css',
            'kio_asset_management/static/src/scss/asset_list_page.css',
            'kio_asset_management/static/src/scss/add_asset_page.css',
            'kio_asset_management/static/src/scss/asset_details_page.css',
            'kio_asset_management/static/src/scss/depreciation_dashboard.css',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'application': True,
    'installable': True,
}
