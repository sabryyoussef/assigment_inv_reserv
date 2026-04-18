import hashlib

from odoo import api, fields, models


class ReservationApiToken(models.Model):
    _name = 'reservation.api.token'
    _description = 'Reservation API Token'
    _rec_name = 'name'

    name = fields.Char(required=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    token = fields.Char(required=True, copy=False, index=True)
    active = fields.Boolean(default=True)

    @staticmethod
    def _hash_token(raw_token):
        return hashlib.sha256(raw_token.encode()).hexdigest()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('token'):
                vals['token'] = self._hash_token(vals['token'])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('token'):
            vals['token'] = self._hash_token(vals['token'])
        return super().write(vals)
