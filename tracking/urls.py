from django.urls import path

from .api_views import OrderCreateAPIView
from .views import OrderProcessingView


urlpatterns = [
    path("api/orders/", OrderCreateAPIView.as_view(), name="api-order-create"),
    path("orders/process/", OrderProcessingView.as_view(), name="process-order"),
]
