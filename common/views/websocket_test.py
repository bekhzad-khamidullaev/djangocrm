"""
WebSocket test page view.
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required


def websocket_test(request):
    """
    Display WebSocket test client page.
    
    This view renders a simple HTML/JavaScript client for testing
    WebSocket connections to the Daphne server.
    """
    return render(request, 'websocket_test.html')
