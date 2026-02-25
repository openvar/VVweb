from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from allauth.account.utils import send_email_confirmation

@login_required
def resend_confirmation(request):
    send_email_confirmation(request, request.user)
    messages.success(request, "A new confirmation email has been sent.")
    return redirect("account_email_verification_sent")

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
