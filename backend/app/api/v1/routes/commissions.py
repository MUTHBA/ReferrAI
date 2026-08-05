# -----------------------------------------------------------------------------
# backend/app/api/v1/routes/commissions.py
#
# Scaffold placeholder — commission endpoints were not implemented as a
# standalone router. Commission calculation is triggered automatically inside
# the conversion recording flow (POST /api/v1/referrals/conversions in
# referrals.py) via CommissionService.calculate_for_conversion(). Commission
# data is surfaced to partners through the wallet transaction history
# (GET /api/v1/wallet/transactions) and to admins through the dashboard
# CSV export (GET /api/v1/reports/commissions.csv in dashboard.py).
# If a dedicated read-only commissions list endpoint is needed in future,
# add it here and register the router in main.py.
# -----------------------------------------------------------------------------
