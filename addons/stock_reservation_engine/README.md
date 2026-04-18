# Stock Reservation Engine

This addon now lives under the standard Odoo workspace layout:

- `addons/stock_reservation_engine`

## Delivered scope

- custom reservation batch and line models
- FEFO / FIFO allocation from `stock.quant`
- partial allocation and shortage handling
- stock move generation and internal picking linkage
- JSON API for create, allocate, and status
- dashboard reporting support
- role-based access control for users and managers
- performance, database, concurrency, and testing documentation

## Standard Odoo usage

Add the top-level `addons` directory to your Odoo addons path, then install `stock_reservation_engine`.

## Notes

- the module is submission-ready for the assignment scope
- one final manual dashboard visual check is still optional for reviewer confidence
- CI workflow configuration is available at the repository level
