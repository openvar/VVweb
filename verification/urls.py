# verification/urls.py

from django.urls import path
from .views_verify import verify_identity, verify_pending
from .views_commercial import commercial_landing
from .views_banned import banned_landing  # <-- add this import

urlpatterns = [
    path("verify/", verify_identity, name="verify_identity"),
    path("verify/pending/", verify_pending, name="verify_pending"),
    path("commercial/", commercial_landing, name="commercial_landing"),
    path("banned/", banned_landing, name="banned_landing"),  # <-- add this route
]

# <LICENSE>
# Copyright (C) 2016-2026 VariantValidator Contributors
# (license text unchanged)
# </LICENSE>