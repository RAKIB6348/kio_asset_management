# -*- coding: utf-8 -*-
{
    'name': "kio_asset_management",

    'summary': "Enterprise asset management dashboard",

    'description': """
Modern OWL dashboard for tracking assets, assignments, maintenance, and depreciation.
    """,

    'author': "KIO",
    'website': "https://www.kio.com",

    'category': 'Operations/Inventory',
    'version': '0.1',

    'depends': ['base', 'web'],

    'data': [
        # 'security/ir.model.access.csv',
        'views/dashboard_action.xml',
        'views/views.xml',
        'views/templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'kio_asset_management/static/src/js/asset_dashboard.js',
            'kio_asset_management/static/src/xml/asset_dashboard.xml',
            'kio_asset_management/static/src/scss/asset_dashboard.css',
        ],
    },
    'demo': [
        'demo/demo.xml',
    ],
    'application': True,
    'installable': True,
}
