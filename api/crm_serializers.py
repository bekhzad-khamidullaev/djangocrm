"""
Serializers for CRM models API endpoints
"""
from rest_framework import serializers
from crm.models import (
    Request, Output, Payment, Product, ProductCategory,
    Currency, Country, City, Industry, LeadSource,
    ClientType, ClosingReason, CrmEmail, Shipment, Rate
)


# Reference data serializers (read-only)

class CurrencySerializer(serializers.ModelSerializer):
    """Serializer for Currency model"""
    class Meta:
        model = Currency
        fields = ['id', 'name', 'auto_update', 'rate_to_state_currency', 'rate_to_marketing_currency']


class CountrySerializer(serializers.ModelSerializer):
    """Serializer for Country model"""
    class Meta:
        model = Country
        fields = ['id', 'name', 'url_name', 'alternative_names']


class CitySerializer(serializers.ModelSerializer):
    """Serializer for City model"""
    country_name = serializers.CharField(source='country.name', read_only=True)
    
    class Meta:
        model = City
        fields = ['id', 'name', 'country', 'country_name', 'alternative_names']


class IndustrySerializer(serializers.ModelSerializer):
    """Serializer for Industry model"""
    class Meta:
        model = Industry
        fields = ['id', 'name']


class LeadSourceSerializer(serializers.ModelSerializer):
    """Serializer for LeadSource model"""
    class Meta:
        model = LeadSource
        fields = ['id', 'name', 'sla_hours']


class ClientTypeSerializer(serializers.ModelSerializer):
    """Serializer for ClientType model"""
    class Meta:
        model = ClientType
        fields = ['id', 'name']


class ClosingReasonSerializer(serializers.ModelSerializer):
    """Serializer for ClosingReason model"""
    class Meta:
        model = ClosingReason
        fields = ['id', 'name', 'index_number', 'success_reason']


class ProductCategorySerializer(serializers.ModelSerializer):
    """Serializer for ProductCategory model"""
    class Meta:
        model = ProductCategory
        fields = ['id', 'name']


# Transactional data serializers

class ProductSerializer(serializers.ModelSerializer):
    """Serializer for Product model"""
    category_name = serializers.CharField(source='product_category.name', read_only=True)
    currency_name = serializers.CharField(source='currency.name', read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'product_category', 'category_name',
            'price', 'currency', 'currency_name', 'type', 'on_sale'
        ]


class RequestSerializer(serializers.ModelSerializer):
    """Serializer for Request (tickets/inquiries) model"""
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    company_name = serializers.CharField(source='company.full_name', read_only=True)
    contact_name = serializers.CharField(source='contact.full_name', read_only=True)
    lead_name = serializers.CharField(source='lead.full_name', read_only=True)
    
    class Meta:
        model = Request
        fields = [
            'id', 'ticket', 'description', 
            'owner', 'owner_name', 'company', 'company_name',
            'contact', 'contact_name', 'lead', 'lead_name',
            'email', 'first_name', 'middle_name', 'last_name',
            'phone', 'country', 'city', 
            'creation_date', 'update_date'
        ]
        read_only_fields = ['ticket', 'creation_date', 'update_date']


class OutputSerializer(serializers.ModelSerializer):
    """Serializer for Output (product shipments) model"""
    deal_name = serializers.CharField(source='deal.name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    currency_name = serializers.CharField(source='currency.name', read_only=True)
    
    class Meta:
        model = Output
        fields = [
            'id', 'deal', 'deal_name', 'product', 'product_name',
            'quantity', 'amount', 'currency', 'currency_name',
            'shipping_date', 'planned_shipping_date', 'actual_shipping_date',
            'product_is_shipped', 'serial_number'
        ]


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model"""
    deal_name = serializers.CharField(source='deal.name', read_only=True)
    currency_name = serializers.CharField(source='currency.name', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'deal', 'deal_name', 'amount', 'currency', 'currency_name',
            'payment_date', 'status', 'contract_number', 'invoice_number', 'order_number'
        ]


class ShipmentSerializer(serializers.ModelSerializer):
    """Serializer for Shipment model (proxy of Output, only shipped items)"""
    deal_name = serializers.CharField(source='deal.name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    currency_name = serializers.CharField(source='currency.name', read_only=True)
    
    class Meta:
        model = Shipment
        fields = [
            'id', 'deal', 'deal_name', 'product', 'product_name',
            'quantity', 'amount', 'currency', 'currency_name',
            'shipping_date', 'planned_shipping_date', 'actual_shipping_date',
            'product_is_shipped', 'serial_number'
        ]


class CrmEmailSerializer(serializers.ModelSerializer):
    """Serializer for CrmEmail model"""
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    company_name = serializers.CharField(source='company.full_name', read_only=True)
    contact_name = serializers.CharField(source='contact.full_name', read_only=True)
    deal_name = serializers.CharField(source='deal.name', read_only=True)
    
    class Meta:
        model = CrmEmail
        fields = [
            'id', 'owner', 'owner_name', 'company', 'company_name',
            'contact', 'contact_name', 'deal', 'deal_name', 'request',
            'lead', 'from_field', 'to', 'subject', 'message_id',
            'content', 'incoming', 'sent', 'creation_date'
        ]
        read_only_fields = ['creation_date']


class RateSerializer(serializers.ModelSerializer):
    """Serializer for Currency Rate model"""
    currency_name = serializers.CharField(source='currency.name', read_only=True)
    
    class Meta:
        model = Rate
        fields = ['id', 'currency', 'currency_name', 'payment_date', 
                  'rate_to_state_currency', 'rate_to_marketing_currency', 'rate_type']
