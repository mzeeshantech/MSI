from django.shortcuts import render
from .models import WalletEntry

def wallet_home(request):
    context = {
        'selected_page': 'wallet',
    }
    return render(request, 'wallet/home.html', context)

def wallet_entries(request):
    entries = WalletEntry.objects.all()
    context = {
        'selected_page': 'wallet',
        'entries' : entries
    }
    return render(request, 'wallet/entries.html', context)
