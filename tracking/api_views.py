from __future__ import annotations

from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import OrderSerializer


class OrderCreateAPIView(APIView):
    """Create an order through the serializer and return a DRF response."""

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        serializer = OrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            order = serializer.save()
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": "Order created successfully.",
                "order_number": order.order_number,
                "status": order.status,
                "total": str(order.total),
            },
            status=status.HTTP_201_CREATED,
        )
