"""
Интеграция с Asterisk PBX
Обработка AMI (Asterisk Manager Interface) событий для маршрутизации звонков
"""
import asyncio
import logging
import re
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from voip.utils.routing import route_call, update_call_status
from voip.utils.notifications import notify_missed_call, notify_queue_overflow
from voip.models import CallLog, NumberGroup

logger = logging.getLogger(__name__)


class AsteriskAMIClient:
    """
    Клиент для подключения к Asterisk Manager Interface
    """
    
    def __init__(self, host, port, username, secret, use_ssl=False):
        self.host = host
        self.port = port
        self.username = username
        self.secret = secret
        self.use_ssl = use_ssl
        self.reader = None
        self.writer = None
        self.authenticated = False
        self.running = False
        self.event_handlers = {}
        
    async def connect(self):
        """Подключиться к AMI"""
        try:
            if self.use_ssl:
                import ssl
                ssl_context = ssl.create_default_context()
                self.reader, self.writer = await asyncio.open_connection(
                    self.host, self.port, ssl=ssl_context
                )
            else:
                self.reader, self.writer = await asyncio.open_connection(
                    self.host, self.port
                )
            
            logger.info(f"Подключились к Asterisk AMI {self.host}:{self.port}")
            
            # Читаем приветствие
            greeting = await self.reader.readline()
            logger.debug(f"AMI приветствие: {greeting.decode().strip()}")
            
            # Аутентификация
            await self.authenticate()
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка подключения к AMI: {e}")
            return False
    
    async def authenticate(self):
        """Аутентификация в AMI"""
        try:
            login_action = (
                f"Action: Login\r\n"
                f"Username: {self.username}\r\n"
                f"Secret: {self.secret}\r\n"
                f"Events: call,agent,queue\r\n"
                f"\r\n"
            )
            
            self.writer.write(login_action.encode())
            await self.writer.drain()
            
            # Читаем ответ
            response = await self.read_message()
            
            if response.get('Response') == 'Success':
                self.authenticated = True
                logger.info("Успешная аутентификация в AMI")
                return True
            else:
                logger.error(f"Ошибка аутентификации AMI: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка аутентификации AMI: {e}")
            return False
    
    async def read_message(self):
        """Прочитать AMI сообщение"""
        message = {}
        
        while True:
            line = await self.reader.readline()
            if not line:
                break
                
            line = line.decode().strip()
            
            if not line:  # Пустая строка означает конец сообщения
                break
            
            if ':' in line:
                key, value = line.split(':', 1)
                message[key.strip()] = value.strip()
        
        return message
    
    async def listen_for_events(self):
        """Слушать события AMI"""
        self.running = True
        
        while self.running:
            try:
                message = await self.read_message()
                
                if not message:
                    continue
                
                event_type = message.get('Event')
                if event_type:
                    await self.handle_event(event_type, message)
                    
            except Exception as e:
                logger.error(f"Ошибка чтения события AMI: {e}")
                await asyncio.sleep(1)
    
    async def handle_event(self, event_type, message):
        """Обработать событие AMI"""
        handler = self.event_handlers.get(event_type)
        if handler:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"Ошибка обработки события {event_type}: {e}")
        else:
            logger.debug(f"Нет обработчика для события {event_type}")
    
    def register_handler(self, event_type, handler):
        """Зарегистрировать обработчик события"""
        self.event_handlers[event_type] = handler
    
    async def send_action(self, action, **params):
        """Отправить действие в AMI"""
        if not self.authenticated:
            logger.warning("Не аутентифицированы в AMI")
            return None
        
        try:
            action_text = f"Action: {action}\r\n"
            
            for key, value in params.items():
                action_text += f"{key}: {value}\r\n"
            
            action_text += "\r\n"
            
            self.writer.write(action_text.encode())
            await self.writer.drain()
            
            # Читаем ответ
            response = await self.read_message()
            return response
            
        except Exception as e:
            logger.error(f"Ошибка отправки действия {action}: {e}")
            return None
    
    async def disconnect(self):
        """Отключиться от AMI"""
        self.running = False
        
        if self.writer:
            try:
                await self.send_action("Logoff")
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as e:
                logger.error(f"Ошибка отключения от AMI: {e}")
        
        self.authenticated = False
        logger.info("Отключились от AMI")


class AsteriskCallHandler:
    """
    Обработчик звонков Asterisk
    """
    
    def __init__(self, ami_client):
        self.ami_client = ami_client
        self.active_calls = {}  # Хранение активных звонков
        
        # Регистрируем обработчики событий
        self.ami_client.register_handler('Newchannel', self.handle_new_channel)
        self.ami_client.register_handler('Dial', self.handle_dial)
        self.ami_client.register_handler('Bridge', self.handle_bridge)
        self.ami_client.register_handler('Hangup', self.handle_hangup)
        self.ami_client.register_handler('DialEnd', self.handle_dial_end)
        
        # Дополнительные обработчики событий
        self.ami_client.register_handler('VarSet', self.handle_var_set)
        self.ami_client.register_handler('UserEvent', self.handle_user_event)
        self.ami_client.register_handler('QueueCallerJoin', self.handle_queue_caller_join)
        self.ami_client.register_handler('QueueCallerLeave', self.handle_queue_caller_leave)
        self.ami_client.register_handler('QueueCallerAbandon', self.handle_queue_caller_abandon)
        self.ami_client.register_handler('QueueMemberStatus', self.handle_queue_member_status)
        self.ami_client.register_handler('AgentConnect', self.handle_agent_connect)
        self.ami_client.register_handler('AgentComplete', self.handle_agent_complete)
        self.ami_client.register_handler('Redirect', self.handle_redirect)
        self.ami_client.register_handler('ParkedCall', self.handle_parked_call)
        self.ami_client.register_handler('ConfbridgeJoin', self.handle_conference_join)
        self.ami_client.register_handler('ConfbridgeLeave', self.handle_conference_leave)
        
        # События очередей
        self.ami_client.register_handler('QueueCallerJoin', self.handle_queue_join)
        self.ami_client.register_handler('QueueCallerLeave', self.handle_queue_leave)
        self.ami_client.register_handler('QueueMember', self.handle_queue_member)
    
    async def handle_new_channel(self, message):
        """Обработка создания нового канала"""
        channel = message.get('Channel')
        caller_id = message.get('CallerIDNum', '')
        
        logger.debug(f"Новый канал: {channel}, CallerID: {caller_id}")
        
        if channel:
            self.active_calls[channel] = {
                'channel': channel,
                'caller_id': caller_id,
                'state': 'new',
                'start_time': timezone.now(),
                'events': []
            }
    
    async def handle_dial(self, message):
        """Обработка начала набора номера"""
        channel = message.get('Channel')
        destination = message.get('Destination')
        caller_id = message.get('CallerIDNum', '')
        called_number = message.get('Exten', '')
        
        logger.info(f"Dial событие: {caller_id} -> {called_number} ({channel})")
        
        if channel in self.active_calls:
            call_data = self.active_calls[channel]
            call_data.update({
                'destination': destination,
                'called_number': called_number,
                'state': 'dialing'
            })
        
        # Запрос маршрутизации через нашу систему
        if caller_id and called_number:
            routing_result = await self.route_incoming_call(
                caller_id, called_number, channel
            )
            
            # Применяем результат маршрутизации
            await self.apply_routing_result(channel, routing_result)
    
    async def handle_bridge(self, message):
        """Обработка соединения каналов"""
        channel1 = message.get('Channel1')
        channel2 = message.get('Channel2')
        
        logger.info(f"Bridge: {channel1} <-> {channel2}")
        
        # Обновляем состояние звонка как отвеченный
        for channel in [channel1, channel2]:
            if channel in self.active_calls:
                self.active_calls[channel]['state'] = 'answered'
                self.active_calls[channel]['answer_time'] = timezone.now()
    
    async def handle_hangup(self, message):
        """Обработка завершения звонка"""
        channel = message.get('Channel')
        cause = message.get('Cause')
        cause_text = message.get('Cause-txt', '')
        
        logger.info(f"Hangup: {channel}, причина: {cause} ({cause_text})")
        
        if channel in self.active_calls:
            call_data = self.active_calls[channel]
            call_data.update({
                'end_time': timezone.now(),
                'hangup_cause': cause,
                'hangup_cause_text': cause_text,
                'state': 'ended'
            })
            
            # Определяем финальный статус звонка
            final_status = self.determine_call_status(call_data, cause)
            
            # Обновляем в базе данных
            await self.update_call_log(channel, final_status, call_data)
            
            # Уведомления
            if final_status in ['no_answer', 'busy']:
                await self.handle_missed_call(call_data)
            
            # Удаляем из активных звонков
            del self.active_calls[channel]
    
    async def handle_dial_end(self, message):
        """Обработка окончания набора"""
        channel = message.get('Channel')
        dial_status = message.get('DialStatus')
        
        logger.debug(f"DialEnd: {channel}, статус: {dial_status}")
        
        if channel in self.active_calls:
            self.active_calls[channel]['dial_status'] = dial_status
    
    async def handle_queue_join(self, message):
        """Обработка добавления в очередь"""
        queue_name = message.get('Queue')
        caller_id = message.get('CallerIDNum')
        position = message.get('Position')
        
        logger.info(f"Caller {caller_id} присоединился к очереди {queue_name} (позиция {position})")
        
        # Уведомляем о переполнении очереди если нужно
        await self.check_queue_overflow(queue_name)
    
    async def handle_queue_leave(self, message):
        """Обработка покидания очереди"""
        queue_name = message.get('Queue')
        caller_id = message.get('CallerIDNum')
        reason = message.get('Reason')
        
        logger.info(f"Caller {caller_id} покинул очередь {queue_name} ({reason})")
    
    async def handle_queue_member(self, message):
        """Обработка состояния участника очереди"""
        queue_name = message.get('Queue')
        member_name = message.get('MemberName')
        status = message.get('Status')
        
        logger.debug(f"Queue member {member_name} в очереди {queue_name}: {status}")
    
    async def route_incoming_call(self, caller_id, called_number, session_id):
        """Маршрутизировать входящий звонок через нашу систему"""
        try:
            # Используем синхронную функцию в асинхронном контексте
            from asgiref.sync import sync_to_async
            
            route_func = sync_to_async(route_call)
            routing_result = await route_func(caller_id, called_number, session_id)
            
            logger.info(f"Результат маршрутизации для {caller_id} -> {called_number}: {routing_result['action']}")
            
            return routing_result
            
        except Exception as e:
            logger.error(f"Ошибка маршрутизации звонка: {e}")
            return {'action': 'error', 'message': str(e)}
    
    async def apply_routing_result(self, channel, routing_result):
        """Применить результат маршрутизации в Asterisk"""
        action = routing_result.get('action')
        
        try:
            if action == 'route':
                target = routing_result.get('target')
                if target:
                    # Перенаправляем звонок на целевой номер
                    await self.ami_client.send_action(
                        'Redirect',
                        Channel=channel,
                        Context='internal',  # Контекст для внутренних номеров
                        Exten=target,
                        Priority='1'
                    )
            
            elif action == 'forward':
                external_number = routing_result.get('target')
                if external_number:
                    # Перенаправляем на внешний номер
                    await self.ami_client.send_action(
                        'Redirect',
                        Channel=channel,
                        Context='outbound',  # Контекст для внешних звонков
                        Exten=external_number,
                        Priority='1'
                    )
            
            elif action == 'hangup':
                # Завершаем звонок
                await self.ami_client.send_action(
                    'Hangup',
                    Channel=channel,
                    Cause='21'  # Call rejected
                )
            
            elif action == 'announcement':
                # Воспроизводим объявление
                announcement_text = routing_result.get('text', 'Service unavailable')
                await self.ami_client.send_action(
                    'Redirect',
                    Channel=channel,
                    Context='announcements',
                    Exten='s',
                    Priority='1'
                )
            
        except Exception as e:
            logger.error(f"Ошибка применения маршрутизации: {e}")
    
    async def update_call_log(self, channel, status, call_data):
        """Обновить лог звонка в базе данных"""
        try:
            from asgiref.sync import sync_to_async
            
            # Ищем лог звонка по session_id (channel)
            try:
                call_log = await sync_to_async(CallLog.objects.get)(session_id=channel)
                
                call_log.status = status
                call_log.end_time = call_data.get('end_time', timezone.now())
                
                if call_data.get('answer_time'):
                    call_log.answer_time = call_data['answer_time']
                
                call_log.user_agent = f"Asterisk/{channel}"
                call_log.notes = f"Hangup cause: {call_data.get('hangup_cause_text', 'Unknown')}"
                
                await sync_to_async(call_log.calculate_statistics)()
                
                logger.info(f"Обновлен лог звонка {channel}: {status}")
                
            except CallLog.DoesNotExist:
                logger.warning(f"Лог звонка не найден для session_id {channel}")
        
        except Exception as e:
            logger.error(f"Ошибка обновления лога звонка: {e}")
    
    def determine_call_status(self, call_data, hangup_cause):
        """Определить финальный статус звонка по причине завершения"""
        # Коды причин Asterisk
        # https://wiki.asterisk.org/wiki/display/AST/Hangup+Cause+Codes
        
        cause_code = int(hangup_cause) if hangup_cause else 0
        
        if call_data.get('state') == 'answered':
            return 'answered'
        elif cause_code in [17, 18, 19]:  # Busy, No answer, No route
            return 'no_answer' if cause_code == 19 else 'busy'
        elif cause_code in [21, 22]:  # Call rejected
            return 'failed'
        else:
            # По умолчанию считаем пропущенным
            return 'no_answer'
    
    async def handle_missed_call(self, call_data):
        """Обработать пропущенный звонок"""
        try:
            from asgiref.sync import sync_to_async
            
            # Найти лог звонка и отправить уведомление
            try:
                call_log = await sync_to_async(CallLog.objects.get)(
                    session_id=call_data['channel']
                )
                
                notify_func = sync_to_async(notify_missed_call)
                await notify_func(call_log)
                
            except CallLog.DoesNotExist:
                logger.warning(f"Лог звонка не найден для уведомления: {call_data['channel']}")
        
        except Exception as e:
            logger.error(f"Ошибка обработки пропущенного звонка: {e}")
    
    async def check_queue_overflow(self, queue_name):
        """Проверить переполнение очереди"""
        try:
            from asgiref.sync import sync_to_async
            
            # Найти группу по имени очереди
            try:
                group = await sync_to_async(NumberGroup.objects.get)(
                    name=queue_name,
                    active=True
                )
                
                # Получить текущий размер очереди через AMI
                queue_status = await self.ami_client.send_action(
                    'QueueStatus',
                    Queue=queue_name
                )
                
                # Парсинг ответа и проверка переполнения
                # (упрощенная версия)
                current_calls = 0  # Здесь нужно парсить ответ AMI
                
                if current_calls >= group.max_queue_size * 0.9:
                    notify_func = sync_to_async(notify_queue_overflow)
                    await notify_func(group, current_calls)
                
            except NumberGroup.DoesNotExist:
                logger.debug(f"Группа не найдена для очереди {queue_name}")
        
        except Exception as e:
            logger.error(f"Ошибка проверки переполнения очереди {queue_name}: {e}")
    
    async def handle_var_set(self, message):
        """Обработка установки переменной канала"""
        channel = message.get('Channel')
        variable = message.get('Variable')
        value = message.get('Value')
        
        logger.debug(f"VarSet: {channel} - {variable}={value}")
        
        if channel in self.active_calls:
            if 'variables' not in self.active_calls[channel]:
                self.active_calls[channel]['variables'] = {}
            self.active_calls[channel]['variables'][variable] = value
    
    async def handle_user_event(self, message):
        """Обработка пользовательских событий"""
        user_event = message.get('UserEvent')
        channel = message.get('Channel')
        
        logger.info(f"UserEvent: {user_event} на канале {channel}")
        
        # Можно обрабатывать кастомные события от диалплана Asterisk
        if user_event == 'CRMCallData':
            # Пример: извлечение данных CRM из Asterisk
            crm_id = message.get('CRMID')
            if crm_id and channel in self.active_calls:
                self.active_calls[channel]['crm_id'] = crm_id
    
    async def handle_queue_caller_join(self, message):
        """Обработка вхождения звонящего в очередь"""
        queue = message.get('Queue')
        position = message.get('Position')
        caller_id = message.get('CallerIDNum')
        channel = message.get('Channel')
        
        logger.info(f"Caller {caller_id} joined queue {queue} at position {position}")
        
        if channel in self.active_calls:
            self.active_calls[channel].update({
                'queue': queue,
                'queue_position': position,
                'queue_join_time': timezone.now()
            })
    
    async def handle_queue_caller_leave(self, message):
        """Обработка выхода звонящего из очереди"""
        queue = message.get('Queue')
        caller_id = message.get('CallerIDNum')
        channel = message.get('Channel')
        count = message.get('Count', 0)
        
        logger.info(f"Caller {caller_id} left queue {queue} (waited {count}s)")
        
        if channel in self.active_calls:
            self.active_calls[channel]['queue_leave_time'] = timezone.now()
            self.active_calls[channel]['queue_wait_time'] = count
    
    async def handle_queue_caller_abandon(self, message):
        """Обработка брошенного звонка в очереди"""
        queue = message.get('Queue')
        caller_id = message.get('CallerIDNum')
        position = message.get('Position')
        original_position = message.get('OriginalPosition')
        hold_time = message.get('HoldTime', 0)
        
        logger.warning(f"Abandoned call: {caller_id} in queue {queue} after {hold_time}s")
        
        # Уведомление о брошенном звонке
        try:
            from asgiref.sync import sync_to_async
            from voip.utils.notifications import notify_abandoned_call
            
            notify_func = sync_to_async(notify_abandoned_call)
            await notify_func(queue, caller_id, hold_time)
        except Exception as e:
            logger.error(f"Error notifying abandoned call: {e}")
    
    async def handle_queue_member_status(self, message):
        """Обработка изменения статуса члена очереди"""
        queue = message.get('Queue')
        member_name = message.get('MemberName')
        status = message.get('Status')
        paused = message.get('Paused', '0')
        
        status_text = self._member_status_to_text(int(status))
        paused_text = "paused" if paused == '1' else "active"
        
        logger.info(f"Queue member {member_name} in {queue}: {status_text} ({paused_text})")
    
    async def handle_agent_connect(self, message):
        """Обработка соединения агента со звонком из очереди"""
        queue = message.get('Queue')
        member = message.get('Member')
        caller_id = message.get('CallerIDNum')
        channel = message.get('Channel')
        hold_time = message.get('HoldTime', 0)
        
        logger.info(f"Agent {member} connected to caller {caller_id} from queue {queue} (hold: {hold_time}s)")
        
        if channel in self.active_calls:
            self.active_calls[channel].update({
                'agent_connected': member,
                'agent_connect_time': timezone.now(),
                'queue_hold_time': hold_time
            })
    
    async def handle_agent_complete(self, message):
        """Обработка завершения разговора агента"""
        queue = message.get('Queue')
        member = message.get('Member')
        caller_id = message.get('CallerIDNum')
        hold_time = message.get('HoldTime', 0)
        talk_time = message.get('TalkTime', 0)
        reason = message.get('Reason', 'transfer')
        
        logger.info(f"Agent {member} completed call with {caller_id} from queue {queue} "
                   f"(hold: {hold_time}s, talk: {talk_time}s, reason: {reason})")
    
    async def handle_redirect(self, message):
        """Обработка переадресации звонка"""
        channel = message.get('Channel')
        extra_channel = message.get('ExtraChannel')
        context = message.get('Context')
        exten = message.get('Exten')
        
        logger.info(f"Call redirected: {channel} -> {exten} in context {context}")
        
        if channel in self.active_calls:
            self.active_calls[channel].update({
                'redirected': True,
                'redirect_to': exten,
                'redirect_time': timezone.now()
            })
    
    async def handle_parked_call(self, message):
        """Обработка парковки звонка"""
        parkinglot = message.get('Parkinglot', 'default')
        parking_space = message.get('ParkingSpace')
        channel = message.get('Channel')
        caller_id = message.get('CallerIDNum')
        timeout = message.get('Timeout', 0)
        
        logger.info(f"Call parked: {caller_id} at space {parking_space} in lot {parkinglot} (timeout: {timeout}s)")
        
        if channel in self.active_calls:
            self.active_calls[channel].update({
                'parked': True,
                'parking_space': parking_space,
                'parking_lot': parkinglot,
                'park_time': timezone.now(),
                'park_timeout': timeout
            })
    
    async def handle_conference_join(self, message):
        """Обработка входа в конференцию"""
        conference = message.get('Conference')
        channel = message.get('Channel')
        caller_id = message.get('CallerIDNum')
        
        logger.info(f"Participant {caller_id} joined conference {conference}")
        
        if channel in self.active_calls:
            self.active_calls[channel].update({
                'conference': conference,
                'conference_join_time': timezone.now()
            })
    
    async def handle_conference_leave(self, message):
        """Обработка выхода из конференции"""
        conference = message.get('Conference')
        channel = message.get('Channel')
        caller_id = message.get('CallerIDNum')
        
        logger.info(f"Participant {caller_id} left conference {conference}")
        
        if channel in self.active_calls:
            self.active_calls[channel]['conference_leave_time'] = timezone.now()
    
    @staticmethod
    def _member_status_to_text(status_code):
        """Преобразовать код статуса члена очереди в текст"""
        status_map = {
            0: 'unknown',
            1: 'not_inuse',
            2: 'inuse',
            3: 'busy',
            4: 'invalid',
            5: 'unavailable',
            6: 'ringing',
            7: 'ringinuse',
            8: 'onhold'
        }
        return status_map.get(status_code, f'unknown_{status_code}')


async def start_asterisk_integration():
    """
    Запустить интеграцию с Asterisk
    """
    # Получаем настройки из конфигурации Django
    ami_config = getattr(settings, 'ASTERISK_AMI', {})
    
    if not ami_config:
        logger.warning("Конфигурация ASTERISK_AMI не найдена")
        return
    
    host = ami_config.get('HOST', 'localhost')
    port = ami_config.get('PORT', 5038)
    username = ami_config.get('USERNAME', '')
    secret = ami_config.get('SECRET', '')
    use_ssl = ami_config.get('USE_SSL', False)
    
    if not username or not secret:
        logger.error("Не указаны учетные данные для AMI")
        return
    
    # Создаем клиент AMI
    ami_client = AsteriskAMIClient(host, port, username, secret, use_ssl)
    
    # Создаем обработчик звонков
    call_handler = AsteriskCallHandler(ami_client)
    
    try:
        # Подключаемся
        if await ami_client.connect():
            logger.info("Интеграция с Asterisk запущена")
            
            # Слушаем события
            await ami_client.listen_for_events()
        else:
            logger.error("Не удалось подключиться к Asterisk AMI")
    
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    
    except Exception as e:
        logger.error(f"Ошибка интеграции с Asterisk: {e}")
    
    finally:
        await ami_client.disconnect()
        logger.info("Интеграция с Asterisk остановлена")


# Пример конфигурации для settings.py:
"""
ASTERISK_AMI = {
    'HOST': 'localhost',
    'PORT': 5038,
    'USERNAME': 'django_crm',
    'SECRET': 'your_secret_password',
    'USE_SSL': False,
    'CONNECT_TIMEOUT': 5,
    'RECONNECT_DELAY': 5
}
"""