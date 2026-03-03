from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def banned_landing(request):
    return render(request, "banned.html", {"profile": request.user.profile})