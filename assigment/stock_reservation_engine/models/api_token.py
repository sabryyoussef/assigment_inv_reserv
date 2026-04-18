from odoo import fields, models


class ReservationApiToken(models.Model):
    _name = 'reservation.api.token'
    _description = 'Reservation API Token'
    _rec_name = 'name'

    name = fields.Char(required=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    token = fields.Char(required=True, copy=False, index=True)
    active = fields.Boolean(default=True)
