"""
Интеграция с FreeSWITCH
Обработка ESL (Event Socket Library) событий для маршрутизации звонков
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from voip.utils.routing import route_call, update_call_status
from voip.utils.notifications import notify_missed_call, notify_queue_overflow
from voip.models import CallLog, NumberGroup

logger = logging.getLogger(__name__)


class FreeSWITCHESLClient:
    """
    Клиент для подключения к FreeSWITCH Event Socket Library
    """
    
    def __init__(self, host, port, password, inbound=True):
        self.host = host
        self.port = port
        self.password = password
        self.inbound = inbound  # True для inbound, False для outbound
        self.reader = None
        self.writer = None
        self.authenticated = False
        self.running = False
        self.event_handlers = {}
        
    async def connect(self):
        """Подключиться к ESL"""
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
            
            logger.info(f"Подключились к FreeSWITCH ESL {self.host}:{self.port}")
            
            if self.inbound:
                # Для inbound соединений читаем приветствие
                greeting = await self.read_message()
                logger.debug(f"ESL приветствие: {greeting}")
                
                # Аутентификация
                await self.authenticate()
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка подключения к ESL: {e}")
            return False
    
    async def authenticate(self):
        """Аутентификация в ESL"""
        try:
            auth_command = f"auth {self.password}\n\n"
            self.writer.write(auth_command.encode())
            await self.writer.drain()
            
            # Читаем ответ
            response = await self.read_message()
            
            if '+OK accepted' in response.get('body', ''):
                self.authenticated = True
                logger.info("Успешная аутентификация в ESL")
                
                # Подписываемся на события
                await self.send_command("event plain ALL")
                return True
            else:
                logger.error(f"Ошибка аутентификации ESL: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка аутентификации ESL: {e}")
            return False
    
    async def read_message(self):
        """Прочитать ESL сообщение"""
        headers = {}
        body = ""
        
        # Читаем заголовки
        while True:
            line = await self.reader.readline()
            if not line:
                break
                
            line = line.decode().strip()
            
            if not line:  # Пустая строка означает конец заголовков
                break
            
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip()] = value.strip()
        
        # Читаем тело если указана длина
        content_length = headers.get('Content-Length')
        if content_length:
            try:
                length = int(content_length)
                if length > 0:
                    body_bytes = await self.reader.readexactly(length)
                    body = body_bytes.decode()
            except Exception as e:
                logger.warning(f"Ошибка чтения тела сообщения: {e}")
        
        return {
            'headers': headers,
            'body': body
        }
    
    async def send_command(self, command):
        """Отправить команду в ESL"""
        try:
            command_text = f"{command}\n\n"
            self.writer.write(command_text.encode())
            await self.writer.drain()
            
            # Читаем ответ
            response = await self.read_message()
            return response
            
        except Exception as e:
            logger.error(f"Ошибка отправки команды {command}: {e}")
            return None
    
    async def send_api_command(self, command):
        """Отправить API команду"""
        return await self.send_command(f"api {command}")
    
    async def listen_for_events(self):
        """Слушать события ESL"""
        self.running = True
        
        while self.running:
            try:
                message = await self.read_message()
                
                if not message or not message.get('headers'):
                    continue
                
                headers = message['headers']
                event_name = headers.get('Event-Name')
                
                if event_name:
                    await self.handle_event(event_name, headers, message.get('body', ''))
                    
            except Exception as e:
                logger.error(f"Ошибка чтения события ESL: {e}")
                await asyncio.sleep(1)
    
    async def handle_event(self, event_name, headers, body):
        """Обработать событие ESL"""
        handler = self.event_handlers.get(event_name)
        if handler:
            try:
                await handler(headers, body)
            except Exception as e:
                logger.error(f"Ошибка обработки события {event_name}: {e}")
        else:
            logger.debug(f"Нет обработчика для события {event_name}")
    
    def register_handler(self, event_name, handler):
        """Зарегистрировать обработчик события"""
        self.event_handlers[event_name] = handler
    
    async def originate_call(self, endpoint, destination, context='default'):
        """Создать исходящий звонок"""
        command = f"originate {endpoint} &bridge({destination})"
        return await self.send_api_command(command)
    
    async def transfer_call(self, uuid, destination, context='default'):
        """Перевести звонок"""
        command = f"uuid_transfer {uuid} {destination} {context}"
        return await self.send_api_command(command)
    
    async def hangup_call(self, uuid, cause='NORMAL_CLEARING'):
        """Завершить звонок"""
        command = f"uuid_kill {uuid} {cause}"
        return await self.send_api_command(command)
    
    async def play_file(self, uuid, filename):
        """Воспроизвести файл"""
        command = f"uuid_broadcast {uuid} {filename} both"
        return await self.send_api_command(command)
    
    async def disconnect(self):
        """Отключиться от ESL"""
        self.running = False
        
        if self.writer:
            try:
                await self.send_command("exit")
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as e:
                logger.error(f"Ошибка отключения от ESL: {e}")
        
        self.authenticated = False
        logger.info("Отключились от ESL")


class FreeSWITCHCallHandler:
    """
    Обработчик звонков FreeSWITCH
    """
    
    def __init__(self, esl_client):
        self.esl_client = esl_client
        self.active_calls = {}  # Хранение активных звонков
        
        # Регистрируем обработчики событий
        self.esl_client.register_handler('CHANNEL_CREATE', self.handle_channel_create)
        self.esl_client.register_handler('CHANNEL_ANSWER', self.handle_channel_answer)
        self.esl_client.register_handler('CHANNEL_BRIDGE', self.handle_channel_bridge)
        self.esl_client.register_handler('CHANNEL_HANGUP', self.handle_channel_hangup)
        self.esl_client.register_handler('CHANNEL_HANGUP_COMPLETE', self.handle_hangup_complete)
        
        # События маршрутизации
        self.esl_client.register_handler('CHANNEL_PARK', self.handle_channel_park)
        self.esl_client.register_handler('CHANNEL_UNPARK', self.handle_channel_unpark)
        
        # События FIFO (очереди FreeSWITCH)
        self.esl_client.register_handler('FIFO::info', self.handle_fifo_info)
        
    async def handle_channel_create(self, headers, body):
        """Обработка создания канала"""
        uuid = headers.get('Unique-ID')
        caller_id = headers.get('Caller-Caller-ID-Number', '')
        called_number = headers.get('Caller-Destination-Number', '')
        direction = headers.get('Call-Direction', 'inbound')
        
        logger.debug(f"Новый канал: {uuid}, {caller_id} -> {called_number} ({direction})")
        
        if uuid:
            self.active_calls[uuid] = {
                'uuid': uuid,
                'caller_id': caller_id,
                'called_number': called_number,
                'direction': direction,
                'state': 'created',
                'start_time': timezone.now(),
                'events': []
            }
            
            # Если это входящий звонок, запрашиваем маршрутизацию
            if direction == 'inbound' and caller_id and called_number:
                await self.route_incoming_call(caller_id, called_number, uuid)
    
    async def handle_channel_answer(self, headers, body):
        """Обработка ответа на звонок"""
        uuid = headers.get('Unique-ID')
        
        logger.info(f"Звонок отвечен: {uuid}")
        
        if uuid in self.active_calls:
            self.active_calls[uuid].update({
                'state': 'answered',
                'answer_time': timezone.now()
            })
    
    async def handle_channel_bridge(self, headers, body):
        """Обработка соединения каналов"""
        uuid = headers.get('Unique-ID')
        other_uuid = headers.get('Other-Leg-Unique-ID')
        
        logger.info(f"Bridge: {uuid} <-> {other_uuid}")
        
        # Обновляем состояние обоих каналов
        for call_uuid in [uuid, other_uuid]:
            if call_uuid and call_uuid in self.active_calls:
                self.active_calls[call_uuid].update({
                    'state': 'bridged',
                    'bridge_time': timezone.now(),
                    'bridged_with': other_uuid if call_uuid == uuid else uuid
                })
    
    async def handle_channel_hangup(self, headers, body):
        """Обработка начала завершения звонка"""
        uuid = headers.get('Unique-ID')
        hangup_cause = headers.get('Hangup-Cause', 'NORMAL_CLEARING')
        
        logger.info(f"Hangup начат: {uuid}, причина: {hangup_cause}")
        
        if uuid in self.active_calls:
            self.active_calls[uuid].update({
                'hangup_cause': hangup_cause,
                'hangup_time': timezone.now(),
                'state': 'hangup'
            })
    
    async def handle_hangup_complete(self, headers, body):
        """Обработка завершения звонка"""
        uuid = headers.get('Unique-ID')
        hangup_cause = headers.get('Hangup-Cause', 'NORMAL_CLEARING')
        duration = headers.get('variable_duration', '0')
        billsec = headers.get('variable_billsec', '0')
        
        logger.info(f"Hangup завершен: {uuid}, длительность: {billsec}s")
        
        if uuid in self.active_calls:
            call_data = self.active_calls[uuid]
            call_data.update({
                'end_time': timezone.now(),
                'duration': int(billsec) if billsec.isdigit() else 0,
                'total_duration': int(duration) if duration.isdigit() else 0,
                'final_hangup_cause': hangup_cause,
                'state': 'completed'
            })
            
            # Определяем финальный статус звонка
            final_status = self.determine_call_status(call_data, hangup_cause)
            
            # Обновляем в базе данных
            await self.update_call_log(uuid, final_status, call_data)
            
            # Уведомления
            if final_status in ['no_answer', 'busy']:
                await self.handle_missed_call(call_data)
            
            # Удаляем из активных звонков
            del self.active_calls[uuid]
    
    async def handle_channel_park(self, headers, body):
        """Обработка парковки канала (ожидание)"""
        uuid = headers.get('Unique-ID')
        
        logger.debug(f"Канал припаркован: {uuid}")
        
        if uuid in self.active_calls:
            self.active_calls[uuid]['state'] = 'parked'
    
    async def handle_channel_unpark(self, headers, body):
        """Обработка снятия с парковки"""
        uuid = headers.get('Unique-ID')
        
        logger.debug(f"Канал снят с парковки: {uuid}")
        
        if uuid in self.active_calls:
            self.active_calls[uuid]['state'] = 'unparked'
    
    async def handle_fifo_info(self, headers, body):
        """Обработка информации о FIFO очереди"""
        fifo_name = headers.get('FIFO-Name')
        fifo_action = headers.get('FIFO-Action')
        caller_uuid = headers.get('Caller-Unique-ID')
        
        logger.debug(f"FIFO {fifo_name}: {fifo_action} ({caller_uuid})")
        
        # Проверяем переполнение очереди
        if fifo_action == 'push':
            await self.check_fifo_overflow(fifo_name)
    
    async def route_incoming_call(self, caller_id, called_number, uuid):
        """Маршрутизировать входящий звонок"""
        try:
            from asgiref.sync import sync_to_async
            
            route_func = sync_to_async(route_call)
            routing_result = await route_func(caller_id, called_number, uuid)
            
            logger.info(f"Результат маршрутизации для {caller_id} -> {called_number}: {routing_result['action']}")
            
            # Применяем результат маршрутизации
            await self.apply_routing_result(uuid, routing_result)
            
        except Exception as e:
            logger.error(f"Ошибка маршрутизации звонка: {e}")
    
    async def apply_routing_result(self, uuid, routing_result):
        """Применить результат маршрутизации в FreeSWITCH"""
        action = routing_result.get('action')
        
        try:
            if action == 'route':
                target = routing_result.get('target')
                if target:
                    # Перенаправляем звонок на целевой номер
                    await self.esl_client.transfer_call(uuid, target, 'internal')
            
            elif action == 'forward':
                external_number = routing_result.get('target')
                if external_number:
                    # Перенаправляем на внешний номер
                    await self.esl_client.transfer_call(uuid, external_number, 'outbound')
            
            elif action == 'hangup':
                # Завершаем звонок
                await self.esl_client.hangup_call(uuid, 'CALL_REJECTED')
            
            elif action == 'announcement':
                # Воспроизводим объявление
                announcement_file = self.get_announcement_file(
                    routing_result.get('text', 'Service unavailable')
                )
                await self.esl_client.play_file(uuid, announcement_file)
                
                # Через некоторое время завершаем звонок
                await asyncio.sleep(10)
                await self.esl_client.hangup_call(uuid, 'NORMAL_CLEARING')
            
            elif action == 'busy':
                # Возвращаем сигнал "занято"
                await self.esl_client.hangup_call(uuid, 'USER_BUSY')
        
        except Exception as e:
            logger.error(f"Ошибка применения маршрутизации: {e}")
    
    def get_announcement_file(self, text):
        """Получить файл объявления (упрощенная версия)"""
        # В реальной реализации можно использовать TTS или предзаписанные файлы
        return '/usr/local/freeswitch/sounds/en/us/callie/misc/call_cannot_be_completed.wav'
    
    async def update_call_log(self, uuid, status, call_data):
        """Обновить лог звонка в базе данных"""
        try:
            from asgiref.sync import sync_to_async
            
            try:
                call_log = await sync_to_async(CallLog.objects.get)(session_id=uuid)
                
                call_log.status = status
                call_log.end_time = call_data.get('end_time', timezone.now())
                call_log.duration = call_data.get('duration', 0)
                
                if call_data.get('answer_time'):
                    call_log.answer_time = call_data['answer_time']
                
                call_log.user_agent = f"FreeSWITCH/{uuid}"
                call_log.notes = f"Hangup cause: {call_data.get('final_hangup_cause', 'Unknown')}"
                
                await sync_to_async(call_log.calculate_statistics)()
                
                logger.info(f"Обновлен лог звонка {uuid}: {status}")
                
            except CallLog.DoesNotExist:
                logger.warning(f"Лог звонка не найден для session_id {uuid}")
        
        except Exception as e:
            logger.error(f"Ошибка обновления лога звонка: {e}")
    
    def determine_call_status(self, call_data, hangup_cause):
        """Определить финальный статус звонка по причине завершения"""
        # Коды причин FreeSWITCH
        # https://freeswitch.org/confluence/display/FREESWITCH/Hangup+Cause+Code+Table
        
        if call_data.get('state') in ['answered', 'bridged']:
            return 'answered'
        elif hangup_cause in ['NO_ANSWER', 'NO_USER_RESPONSE']:
            return 'no_answer'
        elif hangup_cause in ['USER_BUSY', 'NORMAL_CIRCUIT_CONGESTION']:
            return 'busy'
        elif hangup_cause in ['CALL_REJECTED', 'NUMBER_CHANGED']:
            return 'failed'
        else:
            return 'no_answer'
    
    async def handle_missed_call(self, call_data):
        """Обработать пропущенный звонок"""
        try:
            from asgiref.sync import sync_to_async
            
            try:
                call_log = await sync_to_async(CallLog.objects.get)(
                    session_id=call_data['uuid']
                )
                
                notify_func = sync_to_async(notify_missed_call)
                await notify_func(call_log)
                
            except CallLog.DoesNotExist:
                logger.warning(f"Лог звонка не найден для уведомления: {call_data['uuid']}")
        
        except Exception as e:
            logger.error(f"Ошибка обработки пропущенного звонка: {e}")
    
    async def check_fifo_overflow(self, fifo_name):
        """Проверить переполнение FIFO очереди"""
        try:
            from asgiref.sync import sync_to_async
            
            try:
                group = await sync_to_async(NumberGroup.objects.get)(
                    name=fifo_name,
                    active=True
                )
                
                # Получаем информацию о FIFO через API
                fifo_info = await self.esl_client.send_api_command(f"fifo list {fifo_name}")
                
                # Парсим информацию о количестве ожидающих (упрощенно)
                current_waiting = 0
                if fifo_info and fifo_info.get('body'):
                    # Здесь нужно парсить вывод команды fifo list
                    pass
                
                if current_waiting >= group.max_queue_size * 0.9:
                    notify_func = sync_to_async(notify_queue_overflow)
                    await notify_func(group, current_waiting)
                
            except NumberGroup.DoesNotExist:
                logger.debug(f"Группа не найдена для FIFO {fifo_name}")
        
        except Exception as e:
            logger.error(f"Ошибка проверки переполнения FIFO {fifo_name}: {e}")


class FreeSWITCHDialplan:
    """
    Генератор dialplan для FreeSWITCH
    """
    
    def __init__(self, esl_client):
        self.esl_client = esl_client
    
    async def generate_routing_dialplan(self):
        """Генерировать dialplan на основе правил маршрутизации"""
        try:
            from asgiref.sync import sync_to_async
            from voip.models import CallRoutingRule
            
            # Получаем активные правила маршрутизации
            rules = await sync_to_async(list)(
                CallRoutingRule.objects.filter(active=True).order_by('priority')
            )
            
            dialplan_xml = self._build_dialplan_xml(rules)
            
            # Обновляем dialplan в FreeSWITCH
            await self._reload_dialplan(dialplan_xml)
            
        except Exception as e:
            logger.error(f"Ошибка генерации dialplan: {e}")
    
    def _build_dialplan_xml(self, rules):
        """Построить XML dialplan"""
        xml_parts = [
            '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
            '<document type="freeswitch/xml">',
            '  <section name="dialplan" description="Django CRM Generated Dialplan">',
            '    <context name="django_routing">',
        ]
        
        for rule in rules:
            condition_xml = self._build_condition_xml(rule)
            xml_parts.append(condition_xml)
        
        xml_parts.extend([
            '    </context>',
            '  </section>',
            '</document>'
        ])
        
        return '\n'.join(xml_parts)
    
    def _build_condition_xml(self, rule):
        """Построить XML для условия правила"""
        conditions = []
        
        # Условие по номеру звонящего
        if rule.caller_id_pattern:
            conditions.append(f'caller_id_number="{rule.caller_id_pattern}"')
        
        # Условие по вызываемому номеру
        if rule.called_number_pattern:
            conditions.append(f'destination_number="{rule.called_number_pattern}"')
        
        condition_str = ' && '.join(conditions) if conditions else 'true'
        
        # Действие
        action_xml = self._build_action_xml(rule)
        
        return f'''
      <extension name="rule_{rule.id}_{rule.name}">
        <condition field="${{{condition_str}}}">
          {action_xml}
        </condition>
      </extension>'''
    
    def _build_action_xml(self, rule):
        """Построить XML для действия правила"""
        if rule.action == 'route_to_number' and rule.target_number:
            return f'<action application="transfer" data="{rule.target_number} XML internal"/>'
        
        elif rule.action == 'route_to_group' and rule.target_group:
            return f'<action application="fifo" data="{rule.target_group.name} in"/>'
        
        elif rule.action == 'forward_external' and rule.target_external:
            return f'<action application="bridge" data="sofia/gateway/external/{rule.target_external}"/>'
        
        elif rule.action == 'play_announcement':
            announcement_file = '/usr/local/freeswitch/sounds/announcement.wav'
            return f'''
          <action application="playback" data="{announcement_file}"/>
          <action application="hangup"/>'''
        
        elif rule.action == 'hangup':
            return '<action application="hangup" data="CALL_REJECTED"/>'
        
        else:
            return '<action application="hangup" data="NO_ROUTE_DESTINATION"/>'
    
    async def _reload_dialplan(self, dialplan_xml):
        """Перезагрузить dialplan в FreeSWITCH"""
        # Сохраняем dialplan в файл
        dialplan_file = '/usr/local/freeswitch/conf/dialplan/django_routing.xml'
        
        try:
            with open(dialplan_file, 'w') as f:
                f.write(dialplan_xml)
            
            # Перезагружаем dialplan
            await self.esl_client.send_api_command('reloadxml')
            
            logger.info("Dialplan успешно обновлен в FreeSWITCH")
            
        except Exception as e:
            logger.error(f"Ошибка обновления dialplan: {e}")


async def start_freeswitch_integration():
    """
    Запустить интеграцию с FreeSWITCH
    """
    # Получаем настройки из конфигурации Django
    esl_config = getattr(settings, 'FREESWITCH_ESL', {})
    
    if not esl_config:
        logger.warning("Конфигурация FREESWITCH_ESL не найдена")
        return
    
    host = esl_config.get('HOST', 'localhost')
    port = esl_config.get('PORT', 8021)
    password = esl_config.get('PASSWORD', 'ClueCon')
    
    # Создаем клиент ESL
    esl_client = FreeSWITCHESLClient(host, port, password)
    
    # Создаем обработчик звонков
    call_handler = FreeSWITCHCallHandler(esl_client)
    
    # Создаем генератор dialplan
    dialplan_generator = FreeSWITCHDialplan(esl_client)
    
    try:
        # Подключаемся
        if await esl_client.connect():
            logger.info("Интеграция с FreeSWITCH запущена")
            
            # Генерируем начальный dialplan
            await dialplan_generator.generate_routing_dialplan()
            
            # Слушаем события
            await esl_client.listen_for_events()
        else:
            logger.error("Не удалось подключиться к FreeSWITCH ESL")
    
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    
    except Exception as e:
        logger.error(f"Ошибка интеграции с FreeSWITCH: {e}")
    
    finally:
        await esl_client.disconnect()
        logger.info("Интеграция с FreeSWITCH остановлена")


# Пример конфигурации для settings.py:
"""
FREESWITCH_ESL = {
    'HOST': 'localhost',
    'PORT': 8021,
    'PASSWORD': 'ClueCon',
    'CONNECT_TIMEOUT': 5,
    'RECONNECT_DELAY': 5
}
"""