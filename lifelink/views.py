from django.shortcuts import render

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
