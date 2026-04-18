# HttpCase runs before TransactionCase when this order is preserved (unittest load order).
from . import test_reservation_http
from . import test_reservation
