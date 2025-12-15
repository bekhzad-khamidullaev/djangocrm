"""
Asterisk Call Control - управление звонками через AMI
"""
import logging
from typing import Optional, Dict, Any, List
from django.conf import settings

logger = logging.getLogger(__name__)


class AsteriskCallControl:
    """
    Класс для управления звонками в Asterisk через AMI.
    Предоставляет методы для инициации, переадресации, парковки звонков и т.д.
    """
    
    def __init__(self, ami_client):
        """
        Args:
            ami_client: Экземпляр AmiClient для отправки команд
        """
        self.ami = ami_client
    
    def originate(
        self,
        channel: str,
        extension: str,
        context: str = 'from-internal',
        priority: int = 1,
        caller_id: Optional[str] = None,
        timeout: int = 30000,
        variables: Optional[Dict[str, str]] = None,
        async_mode: bool = True
    ) -> Dict[str, Any]:
        """
        Инициировать исходящий звонок.
        
        Args:
            channel: Канал для вызова (например, 'SIP/1001')
            extension: Номер назначения
            context: Контекст диалплана
            priority: Приоритет в диалплане
            caller_id: CallerID для звонка
            timeout: Таймаут в миллисекундах
            variables: Дополнительные переменные канала
            async_mode: Асинхронный режим (не ждать ответа)
        
        Returns:
            Словарь с результатом операции
        """
        action_params = {
            'Channel': channel,
            'Exten': extension,
            'Context': context,
            'Priority': str(priority),
            'Timeout': str(timeout),
            'Async': 'true' if async_mode else 'false',
        }
        
        if caller_id:
            action_params['CallerID'] = caller_id
        
        if variables:
            for i, (key, value) in enumerate(variables.items(), 1):
                action_params[f'Variable'] = f'{key}={value}'
        
        try:
            response = self.ami.send_action_sync('Originate', **action_params)
            logger.info(f"Originate call: {channel} -> {extension}, Response: {response.get('Response')}")
            return response
        except Exception as e:
            logger.error(f"Failed to originate call: {e}")
            return {'Response': 'Error', 'Message': str(e)}
    
    def hangup(self, channel: str, cause: Optional[int] = None) -> Dict[str, Any]:
        """
        Завершить звонок на указанном канале.
        
        Args:
            channel: Канал для завершения
            cause: Код причины завершения (Hangup Cause)
        
        Returns:
            Словарь с результатом операции
        """
        action_params = {'Channel': channel}
        if cause:
            action_params['Cause'] = str(cause)
        
        try:
            response = self.ami.send_action_sync('Hangup', **action_params)
            logger.info(f"Hangup call on channel: {channel}, Response: {response.get('Response')}")
            return response
        except Exception as e:
            logger.error(f"Failed to hangup call: {e}")
            return {'Response': 'Error', 'Message': str(e)}
    
    def transfer(
        self,
        channel: str,
        extension: str,
        context: str = 'from-internal'
    ) -> Dict[str, Any]:
        """
        Перевести звонок на другой номер.
        
        Args:
            channel: Канал для переадресации
            extension: Номер назначения
            context: Контекст диалплана
        
        Returns:
            Словарь с результатом операции
        """
        try:
            response = self.ami.send_action_sync(
                'Redirect',
                Channel=channel,
                Exten=extension,
                Context=context,
                Priority='1'
            )
            logger.info(f"Transfer call: {channel} -> {extension}, Response: {response.get('Response')}")
            return response
        except Exception as e:
            logger.error(f"Failed to transfer call: {e}")
            return {'Response': 'Error', 'Message': str(e)}
    
    def park(
        self,
        channel: str,
        parking_lot: str = 'default',
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Припарковать звонок.
        
        Args:
            channel: Канал для парковки
            parking_lot: Имя парковочной зоны
            timeout: Таймаут парковки в секундах
        
        Returns:
            Словарь с результатом и номером парковки
        """
        action_params = {
            'Channel': channel,
            'ParkingLot': parking_lot,
        }
        if timeout:
            action_params['Timeout'] = str(timeout * 1000)  # Конвертация в мс
        
        try:
            response = self.ami.send_action_sync('Park', **action_params)
            logger.info(f"Park call: {channel}, Response: {response.get('Response')}")
            return response
        except Exception as e:
            logger.error(f"Failed to park call: {e}")
            return {'Response': 'Error', 'Message': str(e)}
    
    def spy(
        self,
        spy_channel: str,
        target_channel: str,
        mode: str = 'whisper'
    ) -> Dict[str, Any]:
        """
        Прослушивание/вмешательство в звонок.
        
        Args:
            spy_channel: Канал прослушивающего
            target_channel: Целевой канал
            mode: Режим ('listen', 'whisper', 'barge')
        
        Returns:
            Словарь с результатом операции
        """
        mode_map = {
            'listen': 'o',  # Только прослушивание
            'whisper': 'w',  # Шептание агенту
            'barge': 'b',   # Вмешательство в разговор
        }
        
        spy_options = mode_map.get(mode, 'o')
        
        try:
            response = self.ami.send_action_sync(
                'Originate',
                Channel=spy_channel,
                Application='ChanSpy',
                Data=f'{target_channel},{spy_options}',
                Async='true'
            )
            logger.info(f"Spy on call: {target_channel} by {spy_channel}, Mode: {mode}")
            return response
        except Exception as e:
            logger.error(f"Failed to spy on call: {e}")
            return {'Response': 'Error', 'Message': str(e)}
    
    def bridge_channels(
        self,
        channel1: str,
        channel2: str
    ) -> Dict[str, Any]:
        """
        Создать мост между двумя каналами.
        
        Args:
            channel1: Первый канал
            channel2: Второй канал
        
        Returns:
            Словарь с результатом операции
        """
        try:
            response = self.ami.send_action_sync(
                'Bridge',
                Channel1=channel1,
                Channel2=channel2
            )
            logger.info(f"Bridge channels: {channel1} <-> {channel2}")
            return response
        except Exception as e:
            logger.error(f"Failed to bridge channels: {e}")
            return {'Response': 'Error', 'Message': str(e)}
    
    def send_dtmf(
        self,
        channel: str,
        digit: str,
        duration: int = 100
    ) -> Dict[str, Any]:
        """
        Отправить DTMF сигнал на канал.
        
        Args:
            channel: Канал
            digit: Цифра или символ DTMF
            duration: Длительность в миллисекундах
        
        Returns:
            Словарь с результатом операции
        """
        try:
            response = self.ami.send_action_sync(
                'PlayDTMF',
                Channel=channel,
                Digit=digit,
                Duration=str(duration)
            )
            return response
        except Exception as e:
            logger.error(f"Failed to send DTMF: {e}")
            return {'Response': 'Error', 'Message': str(e)}
    
    def get_channel_info(self, channel: str) -> Dict[str, Any]:
        """
        Получить информацию о канале.
        
        Args:
            channel: Имя канала
        
        Returns:
            Словарь с информацией о канале
        """
        try:
            response = self.ami.send_action_sync('Status', Channel=channel)
            return response
        except Exception as e:
            logger.error(f"Failed to get channel info: {e}")
            return {'Response': 'Error', 'Message': str(e)}
    
    def get_active_channels(self) -> List[Dict[str, Any]]:
        """
        Получить список всех активных каналов.
        
        Returns:
            Список словарей с информацией о каналах
        """
        channels = []
        
        def collect_channels(responses):
            for resp in responses:
                if resp.get('Event') == 'CoreShowChannel':
                    channels.append(resp)
        
        try:
            self.ami.send_action('CoreShowChannels', callback=collect_channels)
            # Ждем сбора данных
            import time
            time.sleep(0.5)
            return channels
        except Exception as e:
            logger.error(f"Failed to get active channels: {e}")
            return []
