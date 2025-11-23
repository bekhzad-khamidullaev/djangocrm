"""
Сигналы для автоматического управления SIP аккаунтами
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.conf import settings
from voip.utils.sip_helpers import create_sip_account_for_user
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=User)
def create_sip_account_for_new_user(sender, instance, created, **kwargs):
    """
    Автоматически создает SIP аккаунт для нового пользователя
    """
    if not created:
        return
        
    # Проверяем настройки - включена ли автоматическая генерация
    auto_create = getattr(settings, 'VOIP_AUTO_CREATE_SIP_ACCOUNTS', True)
    if not auto_create:
        return
    
    try:
        sip_account = create_sip_account_for_user(instance)
        logger.info(
            f"Автоматически создан SIP аккаунт для пользователя {instance.username}: "
            f"номер {sip_account.internal_number.number}"
        )
    except Exception as e:
        logger.error(
            f"Ошибка создания SIP аккаунта для пользователя {instance.username}: {e}"
        )


@receiver(post_save, sender=User)
def update_sip_display_name(sender, instance, created, **kwargs):
    """
    Обновляет отображаемое имя в SIP аккаунте при изменении профиля пользователя
    """
    if created:
        return
        
    try:
        sip_account = instance.sip_account
        new_display_name = instance.get_full_name() or instance.username
        
        if sip_account.internal_number.display_name != new_display_name:
            sip_account.internal_number.display_name = new_display_name
            sip_account.internal_number.save()
            
            logger.info(
                f"Обновлено отображаемое имя SIP для {instance.username}: {new_display_name}"
            )
    except AttributeError:
        # У пользователя нет SIP аккаунта
        pass
    except Exception as e:
        logger.error(
            f"Ошибка обновления отображаемого имени SIP для {instance.username}: {e}"
        )