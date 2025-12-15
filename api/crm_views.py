"""
ViewSets for CRM models API endpoints
"""
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from django.db.models import Q

from crm.models import (
    Request, Output, Payment, Product, ProductCategory,
    Currency, Country, City, Industry, LeadSource,
    ClientType, ClosingReason, CrmEmail, Shipment, Rate
)
from crm.utils.ticketproc import new_ticket

from .crm_serializers import (
    RequestSerializer, OutputSerializer, PaymentSerializer,
    ProductSerializer, ProductCategorySerializer, CurrencySerializer,
    CountrySerializer, CitySerializer, IndustrySerializer,
    LeadSourceSerializer, ClientTypeSerializer, ClosingReasonSerializer,
    CrmEmailSerializer, ShipmentSerializer, RateSerializer
)
from .permissions import OwnedObjectPermission


# Reference data ViewSets (read-only)

@extend_schema(tags=['CRM Reference'])
class CurrencyViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only API for currencies"""
    serializer_class = CurrencySerializer
    queryset = Currency.objects.all().order_by('name')
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']
    
    @action(detail=True, methods=['get'])
    def rates(self, request, pk=None):
        """Get exchange rate history for a currency"""
        currency = self.get_object()
        rates = Rate.objects.filter(currency=currency).order_by('-date')[:30]
        serializer = RateSerializer(rates, many=True)
        return Response(serializer.data)


@extend_schema(tags=['CRM Reference'])
class CountryViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only API for countries"""
    serializer_class = CountrySerializer
    queryset = Country.objects.all().order_by('name')
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['name']
    ordering_fields = ['name']
    filterset_fields = ['name']


@extend_schema(tags=['CRM Reference'])
class CityViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only API for cities"""
    serializer_class = CitySerializer
    queryset = City.objects.select_related('country').all().order_by('name')
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['name', 'country__name']
    ordering_fields = ['name']
    filterset_fields = ['country']


@extend_schema(tags=['CRM Reference'])
class IndustryViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only API for industries"""
    serializer_class = IndustrySerializer
    queryset = Industry.objects.all().order_by('name')
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


@extend_schema(tags=['CRM Reference'])
class LeadSourceViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only API for lead sources"""
    serializer_class = LeadSourceSerializer
    queryset = LeadSource.objects.all().order_by('name')
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


@extend_schema(tags=['CRM Reference'])
class ClientTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only API for client types"""
    serializer_class = ClientTypeSerializer
    queryset = ClientType.objects.all().order_by('name')
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


@extend_schema(tags=['CRM Reference'])
class ClosingReasonViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only API for closing reasons"""
    serializer_class = ClosingReasonSerializer
    queryset = ClosingReason.objects.all().order_by('name')
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


@extend_schema(tags=['CRM Reference'])
class ProductCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only API for product categories"""
    serializer_class = ProductCategorySerializer
    queryset = ProductCategory.objects.all().order_by('name')
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


# Transactional data ViewSets

@extend_schema(tags=['Products'])
class ProductViewSet(viewsets.ModelViewSet):
    """CRUD API for products/services"""
    serializer_class = ProductSerializer
    queryset = Product.objects.select_related('category', 'currency').all().order_by('name')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product_category', 'currency', 'on_sale', 'type']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price']


@extend_schema(tags=['Requests'])
class RequestViewSet(viewsets.ModelViewSet):
    """CRUD API for customer requests/tickets"""
    serializer_class = RequestSerializer
    queryset = Request.objects.select_related(
        'owner', 'company', 'contact', 'lead', 'country', 'city'
    ).all().order_by('-creation_date')
    permission_classes = [IsAuthenticated, OwnedObjectPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['owner', 'company', 'contact', 'lead', 'country', 'lead_source']
    search_fields = ['ticket', 'description', 'email', 'first_name', 'last_name', 'phone']
    ordering_fields = ['creation_date', 'update_date']
    
    def get_queryset(self):
        qs = self.queryset
        user = self.request.user
        
        if user.is_superuser:
            return qs
        
        # Filter by owner or department
        departments = user.groups.all()
        return qs.filter(
            Q(owner=user) | Q(company__department__in=departments)
        ).distinct()
    
    def perform_create(self, serializer):
        """Auto-assign ticket number and owner"""
        ticket = serializer.validated_data.get('ticket') or new_ticket()
        serializer.save(owner=self.request.user, ticket=ticket)


@extend_schema(tags=['Outputs'])
class OutputViewSet(viewsets.ModelViewSet):
    """CRUD API for product outputs/shipments"""
    serializer_class = OutputSerializer
    queryset = Output.objects.select_related(
        'deal', 'product', 'currency'
    ).all().order_by('-shipping_date')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['deal', 'product', 'currency', 'product_is_shipped']
    search_fields = ['serial_number', 'deal__name', 'product__name']
    ordering_fields = ['shipping_date', 'actual_shipping_date', 'amount', 'quantity']
    
    def get_queryset(self):
        qs = self.queryset
        user = self.request.user
        
        if user.is_superuser:
            return qs
        
        # Filter by deal ownership
        return qs.filter(
            Q(deal__owner=user) | Q(deal__co_owner=user)
        ).distinct()


@extend_schema(tags=['Payments'])
class PaymentViewSet(viewsets.ModelViewSet):
    """CRUD API for payments"""
    serializer_class = PaymentSerializer
    queryset = Payment.objects.select_related(
        'deal', 'currency'
    ).all().order_by('-payment_date')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['deal', 'currency', 'status']
    search_fields = ['contract_number', 'invoice_number', 'order_number']
    ordering_fields = ['payment_date', 'amount']
    
    def get_queryset(self):
        qs = self.queryset
        user = self.request.user
        
        if user.is_superuser:
            return qs
        
        # Filter by deal ownership since Payment doesn't have owner
        return qs.filter(
            Q(deal__owner=user) | Q(deal__co_owner=user)
        ).distinct()
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get payment summary statistics"""
        qs = self.filter_queryset(self.get_queryset())
        
        from django.db.models import Sum, Count
        from django.db.models.functions import TruncMonth
        
        # Total by currency
        by_currency = qs.values('currency__code').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')
        
        # By month
        by_month = qs.annotate(
            month=TruncMonth('payment_date')
        ).values('month').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-month')[:12]
        
        return Response({
            'by_currency': list(by_currency),
            'by_month': list(by_month),
        })


@extend_schema(tags=['Shipments'])
class ShipmentViewSet(viewsets.ModelViewSet):
    """CRUD API for shipments (shipped outputs only)"""
    serializer_class = ShipmentSerializer
    queryset = Shipment.objects.select_related(
        'deal', 'product', 'currency'
    ).filter(product_is_shipped=True).order_by('-actual_shipping_date')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['deal', 'product', 'currency']
    search_fields = ['serial_number', 'deal__name', 'product__name']
    ordering_fields = ['shipping_date', 'actual_shipping_date', 'amount']
    
    def get_queryset(self):
        qs = self.queryset
        user = self.request.user
        
        if user.is_superuser:
            return qs
        
        # Filter by deal ownership
        return qs.filter(
            Q(deal__owner=user) | Q(deal__co_owner=user)
        ).distinct()


@extend_schema(tags=['CRM Emails'])
class CrmEmailViewSet(viewsets.ModelViewSet):
    """CRUD API for CRM emails"""
    serializer_class = CrmEmailSerializer
    queryset = CrmEmail.objects.select_related(
        'owner', 'company', 'contact', 'deal', 'request', 'lead'
    ).all().order_by('-creation_date')
    permission_classes = [IsAuthenticated, OwnedObjectPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['owner', 'company', 'contact', 'deal', 'request', 'lead', 'incoming']
    search_fields = ['subject', 'email_from', 'email_to', 'content', 'message_id']
    ordering_fields = ['creation_date']
    
    def get_queryset(self):
        qs = self.queryset
        user = self.request.user
        
        if user.is_superuser:
            return qs
        
        departments = user.groups.all()
        return qs.filter(
            Q(owner=user) | Q(company__department__in=departments)
        ).distinct()
    
    def perform_create(self, serializer):
        """Auto-assign owner"""
        serializer.save(owner=self.request.user)
