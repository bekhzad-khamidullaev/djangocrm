"""
Утилиты для VoIP модуля
"""


def find_objects_by_phone(phone_number):
    """
    Найти объекты CRM (контакт, лид, сделка) по номеру телефона
    
    Returns:
        tuple: (contact, lead, deal, error)
    """
    contact = None
    lead = None
    deal = None
    error = None
    
    try:
        from crm.models import Contact, Lead, Deal
        from django.db.models import Q
        
        # Нормализуем номер до E.164 и ищем по нормализованным полям
        from common.utils.phone import to_e164
        e164 = to_e164(phone_number)
        if not e164:
            return contact, lead, deal, "Empty or invalid phone number"
        # Ищем контакт
        try:
            contact = Contact.objects.filter(
                Q(phone_e164=e164) | Q(mobile_e164=e164)
            ).first()
        except Exception as e:
            error = f"Error searching contact: {e}"
        
        # Ищем лид если не найден контакт
        if not contact:
            try:
                lead = Lead.objects.filter(
                    Q(phone__contains=clean_phone[-10:]) |
                    Q(mobile__contains=clean_phone[-10:]) |
                    Q(phone__icontains=phone_number) |
                    Q(mobile__icontains=phone_number)
                ).first()
            except Exception as e:
                if not error:
                    error = f"Error searching lead: {e}"
        
        # Ищем сделки связанные с контактом или лидом
        if contact or lead:
            try:
                obj = contact or lead
                if hasattr(obj, 'deal_set'):
                    deal = obj.deal_set.filter(stage__in_progress=True).first()
            except Exception as e:
                if not error:
                    error = f"Error searching deal: {e}"
        
    except ImportError:
        error = "CRM models not available"
    except Exception as e:
        error = f"General error: {e}"
    
    return contact, lead, deal, error


def normalize_number(phone_or_extension):
    """
    Extract digits only from phone number or extension.
    """
    if not phone_or_extension:
        return ""
    return "".join(filter(str.isdigit, str(phone_or_extension)))


def _get_settings_instance():
    from voip.models import VoipSettings
    from django.db.utils import OperationalError, ProgrammingError
    try:
        return VoipSettings.objects.first()
    except (OperationalError, ProgrammingError):
        return None


def load_incoming_ui_config():
    from django.conf import settings
    data = {
        'enabled': getattr(settings, 'VOIP_INCOMING_CALL_ENABLED', True),
        'poll_interval_ms': getattr(settings, 'VOIP_INCOMING_POLL_INTERVAL_MS', 4000),
        'popup_ttl_ms': getattr(settings, 'VOIP_INCOMING_POPUP_TTL_MS', 20000),
    }
    instance = _get_settings_instance()
    if instance:
        data = data | instance.incoming_ui_config
    return data


def resolve_targets(extension_or_did, crm_object=None):
    """
    Определить целевых пользователей по внутреннему номеру или DID
    
    Args:
        extension_or_did: Внутренний номер или DID
        crm_object: Объект CRM (контакт, лид или сделка)
    
    Returns:
        list: Список пользователей
    """
    targets = []
    
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Пытаемся найти пользователя по внутреннему номеру
        if extension_or_did:
            try:
                from voip.models import InternalNumber
                internal_number = InternalNumber.objects.filter(
                    number=extension_or_did,
                    active=True,
                    user__isnull=False
                ).first()
                
                if internal_number and internal_number.user:
                    targets.append(internal_number.user)
                    return targets
            except ImportError:
                pass
        
        # Если есть объект CRM, пытаемся найти его владельца
        if crm_object:
            try:
                if hasattr(crm_object, 'owner') and crm_object.owner:
                    targets.append(crm_object.owner)
                elif hasattr(crm_object, 'responsible') and crm_object.responsible:
                    targets.append(crm_object.responsible)
            except Exception:
                pass
        
        # Если ничего не найдено, возвращаем первого активного пользователя
        if not targets:
            first_user = User.objects.filter(is_active=True).first()
            if first_user:
                targets.append(first_user)
    
    except Exception as e:
        # В случае ошибки возвращаем пустой список
        pass
    
    return targets