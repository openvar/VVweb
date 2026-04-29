# web/views_quota.py

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from dateutil.relativedelta import relativedelta
from .models import VariantQuota

@login_required
def quota_status(request):
    """
    Return remaining and total quota for the logged-in user.
    """
    # IMPORTANT: Reload from DB, do NOT use request.user.variant_quota
    quota = VariantQuota.objects.get(user=request.user)

    return JsonResponse({
        "user": request.user.username,
        "plan": quota.get_plan_display(),  # <-- FIXED
        "institution": quota.institution.name if quota.institution else None,
        "personal_allowance": quota.personal_allowance,
        "institution_allowance": (
            quota.institution.variant_limit if quota.institution else None
        ),
        "effective_allowance": quota.effective_allowance,
        "used": quota.count,
        "remaining": quota.remaining,
        "resets_at": (
                quota.last_reset + relativedelta(months=1)
        ).isoformat(),
    })


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
