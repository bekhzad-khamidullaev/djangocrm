from __future__ import annotations

from typing import Optional, Tuple
from django.contrib.auth import get_user_model
from django.db import transaction

from crm.models import Lead, Contact, Company, LeadSource
from common.models import Department


def _get_or_create_lead_source(name: str) -> Optional[LeadSource]:
    ls = LeadSource.objects.filter(name=name).first()
    if ls:
        return ls
    dept = Department.objects.first()
    if not dept:
        return None
    return LeadSource.objects.create(name=name, department=dept)


def _get_owner_and_department(lead_source: Optional[LeadSource]) -> Tuple[Optional[get_user_model()], Optional[Department]]:
    """Determine owner and department based on lead source or fallback."""
    User = get_user_model()
    department = None
    owner = None
    
    if lead_source and lead_source.department:
        department = lead_source.department
        # Try to find active user in this department
        owner = User.objects.filter(
            userprofile__department=department,
            is_active=True
        ).first()
    
    # Fallback: first department and first active user
    if not department:
        department = Department.objects.first()
    if not owner:
        owner = User.objects.filter(is_active=True).first()
    
    return owner, department


@transaction.atomic
def ensure_lead_and_contact(
    *,
    source_name: str,
    display_name: str,
    phone: str = '',
    email: str = '',
    company_name: Optional[str] = None,
) -> Tuple[Lead, Contact]:
    """
    Create minimal Lead and Contact (with Company) if not exist.
    Deduplicates by phone_e164 and email; assigns owner and department.
    """
    from common.utils.phone import to_e164
    from django.db.models import Q
    
    lead_source = _get_or_create_lead_source(source_name)
    owner, department = _get_owner_and_department(lead_source)
    
    phone_e164 = to_e164(phone)
    email_norm = email.lower().strip() if email else ''
    
    # Lead: deduplicate by phone_e164 or email
    lead = None
    if phone_e164:
        lead = Lead.objects.filter(
            Q(phone_e164=phone_e164) | Q(mobile_e164=phone_e164)
        ).first()
    if not lead and email_norm:
        lead = Lead.objects.filter(email__iexact=email_norm).first()
    
    if not lead:
        first_name = display_name or (phone or email or 'Unknown')
        lead = Lead.objects.create(
            first_name=first_name[:100],
            phone=phone or '',
            mobile=phone or '',
            email=email_norm or '',
            lead_source=lead_source,
            owner=owner,
            department=department,
            description=f'Auto-created from {source_name}',
        )

    # Contact requires Company; deduplicate company by phone_e164 or email
    contact = None
    if phone_e164:
        contact = Contact.objects.filter(
            Q(phone_e164=phone_e164) | Q(mobile_e164=phone_e164)
        ).first()
    if not contact and email_norm:
        contact = Contact.objects.filter(email__iexact=email_norm).first()
    
    if not contact:
        comp_name = company_name or f'{source_name} Client'
        # Deduplicate company by phone_e164 or email
        company = None
        if phone_e164:
            company = Company.objects.filter(phone_e164=phone_e164).first()
        if not company and email_norm:
            company = Company.objects.filter(email__iexact=email_norm).first()
        if not company:
            company = Company.objects.filter(full_name=comp_name).first()
        if not company:
            company = Company.objects.create(
                full_name=comp_name[:200],
                email=email_norm or '',
                phone=phone or '',
                owner=owner,
                department=department,
            )
        
        contact = Contact.objects.create(
            company=company,
            first_name=(display_name or (phone or email or 'Unknown'))[:100],
            phone=phone or '',
            mobile=phone or '',
            email=email_norm or '',
            owner=owner,
            department=department,
        )
    
    return lead, contact
