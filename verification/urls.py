# verification/urls.py

from django.urls import path
from .views_verify import verify_identity, verify_pending
from .views_commercial import commercial_landing

urlpatterns = [
    path("verify/", verify_identity, name="verify_identity"),
    path("verify/pending/", verify_pending, name="verify_pending"),
    path("commercial/", commercial_landing, name="commercial_landing"),
]

# <LICENSE>
# Copyright (C) 2016-2026 VariantValidator Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# </LICENSE>
