from django.shortcuts import render, redirect
from django.contrib import messages

from .models import ContactRequest

def create_request(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        subject = request.POST.get('subject')
        message = request.POST.get('message')

        ContactRequest.objects.create(
            name=name,
            email=email,
            phone=phone,
            subject=subject,
            message=message
        )

        messages.success(request, "Your message has been sent successfully!")
        return redirect('contact')

    return render(request, 'contact.html')


def home(request):
    # List of all blood groups
    blood_types = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

    return render(request, "home.html", {
        "blood_types": blood_types
    })

def about(request):
    return render(request, 'about.html')

def contact(request):
    return render(request, 'contact.html')
