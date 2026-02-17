from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect


def signup(request):
    """Handle user signup/registration"""
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Auto-login after signup
            return redirect("record_list")
    else:
        form = UserCreationForm()
    
    return render(request, "registration/signup.html", {
        "form": form
    })
