from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth import get_user_model

from donors.models import DonorProfile
from donors.forms import DonorRegisterForm
from hospitals.models import HospitalProfile
from accounts.decorators import user_type_required

CustomUser = get_user_model()

# -----------------------------
# REGISTER VIEW
# -----------------------------
def register(request):
    user_type = request.GET.get('type') or request.POST.get('user_type')
    
    # Validate user type early
    if user_type not in ['donor', 'hospital']:
        messages.error(request, 'Please select a valid registration type.')
        return redirect('home')

    if request.method == 'POST':
        if user_type == 'donor':
            form = DonorRegisterForm(request.POST)
            if form.is_valid():
                user = form.save()
                login(request, user)
                messages.success(request, "Welcome! Your donor account has been created successfully.")
                return redirect('donor_dashboard')
            else:
                # Display form errors
                for field, errors in form.errors.items():
                    for error in errors:
                        if field == '__all__':
                            messages.error(request, error)
                        else:
                            messages.error(request, f"{field.replace('_', ' ').title()}: {error}")
                # Return form with errors
                return render(request, 'accounts/register.html', {
                    'form': form,
                    'user_type': user_type
                })
        
        elif user_type == 'hospital':
            # Get form data
            username = request.POST.get('username')
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')
            email = request.POST.get('email')
            hospital_name = request.POST.get('hospital_name')
            phone = request.POST.get('phone')
            address = request.POST.get('address')
            
            # Validate required fields
            if not all([username, password1, password2, email, hospital_name, phone, address]):
                messages.error(request, "All fields are required.")
                return render(request, 'accounts/register.html', {'user_type': user_type})
            
            # Validate passwords match
            if password1 != password2:
                messages.error(request, "Passwords do not match.")
                return render(request, 'accounts/register.html', {'user_type': user_type})
            
            # Check if username already exists
            if CustomUser.objects.filter(username=username).exists():
                messages.error(request, "Username already exists.")
                return render(request, 'accounts/register.html', {'user_type': user_type})
            
            # Check if email already exists
            if CustomUser.objects.filter(email=email).exists():
                messages.error(request, "Email already registered.")
                return render(request, 'accounts/register.html', {'user_type': user_type})
            
            try:
                # Create user
                user = CustomUser.objects.create_user(
                    username=username,
                    email=email,
                    password=password1,
                    user_type='hospital'
                )
                
                # Create hospital profile
                HospitalProfile.objects.create(
                    user=user,
                    hospital_name=hospital_name,
                    phone=phone,
                    address=address
                )
                
                login(request, user)
                messages.success(request, f"Welcome! {hospital_name} has been registered successfully.")
                return redirect('hospital_dashboard')
                
            except Exception as e:
                messages.error(request, f"Registration failed: {str(e)}")
                return render(request, 'accounts/register.html', {'user_type': user_type})
    
    # GET request - show empty form
    form = DonorRegisterForm() if user_type == 'donor' else None
    return render(request, 'accounts/register.html', {
        'form': form,
        'user_type': user_type
    })


# -----------------------------
# LOGIN VIEW
# -----------------------------
def user_login(request):
    # Redirect if already logged in
    if request.user.is_authenticated:
        if request.user.user_type == 'donor':
            return redirect('donor_dashboard')
        elif request.user.user_type == 'hospital':
            return redirect('hospital_dashboard')
        else:
            return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Authenticate user
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            
            # Redirect based on user type
            if user.user_type == 'donor':
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect('donor_dashboard')
            elif user.user_type == 'hospital':
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect('hospital_dashboard')
            else:
                messages.error(request, "Account type not recognized. Please contact support.")
                logout(request)
                return redirect('login')
        else:
            messages.error(request, "Invalid username or password. Please try again.")
            return redirect('login')

    return render(request, 'accounts/login.html')


# -----------------------------
# LOGOUT VIEW
# -----------------------------
def user_logout(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('login')


# -----------------------------
# DASHBOARD VIEWS
# -----------------------------
@user_type_required('donor')
def donor_dashboard(request):
    return render(request, 'donors/dashboard.html')

@user_type_required('hospital')
def hospital_dashboard(request):
    return render(request, 'hospitals/dashboard.html')