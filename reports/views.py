from django.shortcuts import render

def reports_home(request):
    context = {
        'selected_page': 'reports',
    }
    return render(request, 'reports/home.html', context)
