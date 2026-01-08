from django.shortcuts import render

def emergency_request(request):
    context = {}

    if request.method == 'POST':
        context = {
            'success': True,
            'patient_name': request.POST.get('patient_name'),
            'blood_type': request.POST.get('blood_type'),
            'location': request.POST.get('location'),
            'contact_info': request.POST.get('contact_info'),
        }

    return render(request, 'blood_requests/emergency.html', context)
