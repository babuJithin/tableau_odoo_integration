
from odoo import http
from odoo.http import request
import json
import datetime

class TableauApiController(http.Controller):

    def _check_token(self):
        auth_header = request.httprequest.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return False
        token = auth_header.split('Bearer ')[1].strip()
        token_rec = request.env['tableau.api.token'].sudo().search([
            ('name', '=', token),
            ('active', '=', True)
        ], limit=1)
        return token_rec

    @http.route('/api/tbtables', type='http', auth='public', csrf=False, methods=['GET','OPTIONS'])
    def get_models(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            headers = [
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods', 'GET, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Authorization, Content-Type'),
            ]
            return request.make_response('', headers=headers)
        token_rec = self._check_token()
        if not token_rec:
            request.env['tableau.api.audit'].sudo().create({
                'name': '/api/tables',
                'user_id': 2,  # resolved from token
                'token_id': 2,  # resolved from token string
                'request_info': "Fetch Database Tables for Navigation",  # or other details
                'response_status': '401',
            })
            return http.Response('Unauthorized', status=401)
        models_data = []
        tableau_models = request.env['tableau.model'].sudo().search([('active', '=', True)])
        model_list=[]
        for pb_model in tableau_models:
            model_name = pb_model.model_id.model
            fields = [f.name for f in pb_model.field_ids]
            columns = []
            for field in pb_model.field_ids:
                dtype = 'string'  # default
                if field.ttype in ['float', 'monetary']:
                    dtype = 'float'
                elif field.ttype in ['integer']:
                    dtype = 'int'
                elif field.ttype in ['boolean']:
                    dtype = 'bool'
                elif field.ttype in ['date', 'datetime']:
                    dtype = 'datetime'

                columns.append({
                    "id": field.name,
                    "dataType": dtype
                })

            model_list.append({
                "id": model_name.replace(".", "_"),
                "alias": model_name,
                "columns": columns
            })
            # model_list.append(pb_model.model_id.model)
        response_data = json.dumps({"tables":model_list})

        print(token_rec)

        user_id = token_rec.user_id.id if token_rec.user_id else 2
        token_id = token_rec.id

        request.env['tableau.api.audit'].sudo().create({
            'name': '/api/tables',
            'user_id': user_id,
            'token_id': token_id,
            'request_info': "Fetch Database Tables for Navigation",  # or other details
            'response_status': '200',
        })

        return request.make_response(
            response_data,
            headers=[
                ('Content-Type', 'application/json'),
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Authorization, Content-Type'),
            ],
            status=200
        )

    def _check_token(self):
        auth_header = request.httprequest.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return False
        token = auth_header.split('Bearer ')[1].strip()
        token_rec = request.env['tableau.api.token'].sudo().search([
            ('name', '=', token),
            ('active', '=', True)
        ], limit=1)
        return token_rec
        # Replace with your token logic

    @http.route('/api/tbtables/<string:model_name>/data', type='http', auth='public', csrf=False, methods=['GET','OPTIONS'])
    def get_data(self, model_name, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            headers = [
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods', 'GET, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Authorization, Content-Type'),
            ]
            return request.make_response('', headers=headers)
        token_rec = self._check_token()
        if not token_rec:
            request.env['tableau.api.audit'].sudo().create({
                'name': '/api/tables/<string:model_name>/data',
                'user_id': 2,  # resolved from token
                'token_id': 2,  # resolved from token string
                'request_info': "Fetch Data",  # or other details
                'response_status': '401',
            })
            return request.make_response(
                json.dumps({'error': 'Unauthorized'}),
                headers=[('Content-Type', 'application/json')],
                status=401
            )
        # model_name = request.httprequest.args.get('model')
        if not model_name:
            return request.make_response(
                json.dumps({'error': 'No model specified'}),
                headers=[('Content-Type', 'application/json')],
                status=400
            )

        # Find the matching powerbi.model record
        model_name = model_name.replace("_", ".")
        pb_model = request.env['tableau.model'].sudo().search([
            ('model_id.model', '=', model_name),
            ('active', '=', True)
        ], limit=1)
        if not pb_model:
            return request.make_response(
                json.dumps({'error': 'Model not allowed'}),
                headers=[('Content-Type', 'application/json')],
                status=403
            )
        fields = [f.name for f in pb_model.field_ids]
        if not fields:
            return request.make_response(
                json.dumps({'error': 'No fields configured'}),
                headers=[('Content-Type', 'application/json')],
                status=403
            )

        # Pagination support (optional)
        limit = int(request.httprequest.args.get('limit', 50))
        offset = int(request.httprequest.args.get('offset', 0))

        records = request.env[model_name].sudo().search([], limit=limit, offset=offset)
        data = []

        for rec in records:
            row = {}
            for fname in fields:
                value = rec[fname]
                if value is False:
                    value = ""
                if isinstance(value, (datetime.date, datetime.datetime)):
                    value = value.isoformat()
                # Convert bytes or lists if needed
                if isinstance(value, (bytes, bytearray)):
                    value = value.decode('utf-8', errors='replace')
                if isinstance(value, (list, tuple)):
                    value = ','.join(str(v) for v in value)
                row[fname] = value
                # row.append(value)
            data.append(row)

        response = {
            "columns": fields,
            "data": data
        }

        user_id = token_rec.user_id.id if token_rec.user_id else 2
        token_id = token_rec.id

        request.env['tableau.api.audit'].sudo().create({
            'name': '/api/tables/<string:model_name>/data',
            'user_id': user_id,
            'token_id': token_id,
            'request_info': "Fetch Database Records",  # or other details
            'response_status': '200',
        })

        return request.make_response(
            json.dumps(data),
            headers=[
                ('Content-Type', 'application/json'),
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Authorization, Content-Type'),
            ],
            status=200
        )


