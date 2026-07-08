# -*- coding: utf-8 -*-
# from odoo import http


# class KioAssetManagement(http.Controller):
#     @http.route('/kio_asset_management/kio_asset_management', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/kio_asset_management/kio_asset_management/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('kio_asset_management.listing', {
#             'root': '/kio_asset_management/kio_asset_management',
#             'objects': http.request.env['kio_asset_management.kio_asset_management'].search([]),
#         })

#     @http.route('/kio_asset_management/kio_asset_management/objects/<model("kio_asset_management.kio_asset_management"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('kio_asset_management.object', {
#             'object': obj
#         })

