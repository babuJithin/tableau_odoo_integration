import json
import datetime
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

CORS_HEADERS = [
    ('Access-Control-Allow-Origin', '*'),
    ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
    ('Access-Control-Allow-Headers', 'Authorization, Content-Type'),
]

def json_response(payload, status=200, extra_headers=None):
    """Always attach CORS headers, on every status code, including errors."""
    headers = [('Content-Type', 'application/json')] + CORS_HEADERS
    if extra_headers:
        headers += extra_headers
    return request.make_response(json.dumps(payload), headers=headers, status=status)


def preflight_response():
    return request.make_response('', headers=CORS_HEADERS)


class TableauApiController(http.Controller):

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _check_token(self):
        """Return the tableau.api.token record for a valid Bearer token, or False."""
        auth_header = request.httprequest.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return False
        token = auth_header.split('Bearer ')[1].strip()
        if not token:
            return False
        token_rec = request.env['tableau.api.token'].sudo().search([
            ('name', '=', token),
            ('active', '=', True),
        ], limit=1)
        return token_rec

    def _audit(self, endpoint, token_rec, request_info, status):
        try:
            user_id = token_rec.user_id.id if token_rec and token_rec.user_id else False
            token_id = token_rec.id if token_rec else False
            vals = {
                'name': endpoint,
                'request_info': request_info,
                'response_status': str(status),
            }
            if user_id:
                vals['user_id'] = user_id
            if token_id:
                vals['token_id'] = token_id
            request.env['tableau.api.audit'].sudo().create(vals)
        except Exception:
            # Auditing must never break the actual API response.
            _logger.exception("Failed to write Tableau API audit record")

    # ------------------------------------------------------------------
    # /api/tbtables — list exposed models/tables
    # ------------------------------------------------------------------
    @http.route('/api/tbtables', type='http', auth='public', csrf=False, methods=['GET', 'OPTIONS'])
    def get_models(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return preflight_response()

        try:
            token_rec = self._check_token()
            if not token_rec:
                self._audit('/api/tbtables', False, "Fetch Database Tables for Navigation", 401)
                return json_response({'error': 'Unauthorized'}, status=401)

            model_list = []
            tableau_models = request.env['tableau.model'].sudo().search([('active', '=', True)])
            for tb_model in tableau_models:
                model_name = tb_model.model_id.model
                columns = []
                for field in tb_model.field_ids:
                    dtype = 'string'
                    if field.ttype in ('float', 'monetary'):
                        dtype = 'float'
                    elif field.ttype == 'integer':
                        dtype = 'int'
                    elif field.ttype == 'boolean':
                        dtype = 'bool'
                    elif field.ttype in ('date', 'datetime'):
                        dtype = 'datetime'
                    columns.append({"id": field.name, "dataType": dtype})

                model_list.append({
                    "id": model_name.replace(".", "_"),
                    "alias": model_name,
                    "columns": columns,
                })

            self._audit('/api/tbtables', token_rec, "Fetch Database Tables for Navigation", 200)
            return json_response({"tables": model_list}, status=200)

        except Exception:
            _logger.exception("Unexpected error in /api/tbtables")
            return json_response({'error': 'Internal server error'}, status=500)

    # ------------------------------------------------------------------
    # /api/tbtables/<model_name>/data — fetch rows for one model
    # ------------------------------------------------------------------
    @http.route('/api/tbtables/<string:model_name>/data', type='http', auth='public', csrf=False,
                methods=['GET', 'OPTIONS'])
    def get_data(self, model_name, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return preflight_response()

        endpoint = '/api/tbtables/<model_name>/data'

        try:
            token_rec = self._check_token()
            if not token_rec:
                self._audit(endpoint, False, "Fetch Data", 401)
                return json_response({'error': 'Unauthorized'}, status=401)

            if not model_name:
                self._audit(endpoint, token_rec, "Fetch Data - no model", 400)
                return json_response({'error': 'No model specified'}, status=400)

            odoo_model_name = model_name.replace("_", ".")
            tb_model = request.env['tableau.model'].sudo().search([
                ('model_id.model', '=', odoo_model_name),
                ('active', '=', True),
            ], limit=1)
            if not tb_model:
                self._audit(endpoint, token_rec, "Fetch Data - model not allowed", 403)
                return json_response({'error': 'Model not allowed'}, status=403)

            fields = [f.name for f in tb_model.field_ids]
            if not fields:
                self._audit(endpoint, token_rec, "Fetch Data - no fields configured", 403)
                return json_response({'error': 'No fields configured'}, status=403)

            try:
                limit = int(request.httprequest.args.get('limit', 50))
                offset = int(request.httprequest.args.get('offset', 0))
            except (TypeError, ValueError):
                limit, offset = 50, 0

            records = request.env[odoo_model_name].sudo().search([], limit=limit, offset=offset)
            data = []
            for rec in records:
                row = {}
                for fname in fields:
                    value = rec[fname]
                    if value is False:
                        value = ""
                    elif isinstance(value, (datetime.date, datetime.datetime)):
                        value = value.isoformat()
                    elif isinstance(value, (bytes, bytearray)):
                        value = value.decode('utf-8', errors='replace')
                    elif isinstance(value, (list, tuple)):
                        value = ','.join(str(v) for v in value)
                    elif hasattr(value, 'id') and hasattr(value, '_name'):
                        # many2one recordset -> display name, not the recordset object
                        value = value.display_name if value else ""
                    row[fname] = value
                data.append(row)

            self._audit(endpoint, token_rec, "Fetch Database Records", 200)
            # Returned as a flat list of row objects — matches what the
            # Tableau WDC connector's getData() expects from tbl.appendRows(rows).
            return json_response(data, status=200)

        except Exception:
            _logger.exception("Unexpected error in %s", endpoint)
            return json_response({'error': 'Internal server error'}, status=500)