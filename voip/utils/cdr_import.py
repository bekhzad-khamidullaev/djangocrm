"""
CDR Import - импорт Call Detail Records из Asterisk
"""
import logging
import csv
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


class AsteriskCDRImporter:
    """
    Класс для импорта CDR записей из Asterisk в Django CRM.
    """
    
    def __init__(self):
        self.imported_count = 0
        self.skipped_count = 0
        self.error_count = 0
        self.errors = []
    
    def import_from_ami(self, ami_client, limit: int = 100) -> Dict[str, Any]:
        """
        Импорт CDR записей через AMI события.
        Примечание: Требует включения CDR событий в Asterisk.
        
        Args:
            ami_client: Экземпляр AmiClient
            limit: Максимальное количество записей для импорта
        
        Returns:
            Словарь с результатами импорта
        """
        cdr_records = []
        
        def collect_cdr(responses):
            for resp in responses:
                if resp.get('Event') == 'Cdr':
                    cdr_records.append(resp)
        
        try:
            # Запрашиваем CDR через AMI
            # Примечание: не все версии Asterisk поддерживают это
            ami_client.send_action('Command', 
                                   Command='cdr show last 100',
                                   callback=collect_cdr)
            
            import time
            time.sleep(1)  # Ждем сбора данных
            
            for cdr in cdr_records[:limit]:
                self._process_cdr_record(cdr)
            
        except Exception as e:
            logger.error(f"Failed to import CDR from AMI: {e}")
            self.errors.append(str(e))
            self.error_count += 1
        
        return self._get_import_summary()
    
    def import_from_csv(self, csv_path: str) -> Dict[str, Any]:
        """
        Импорт CDR из CSV файла.
        
        Args:
            csv_path: Путь к CSV файлу с CDR
        
        Returns:
            Словарь с результатами импорта
        """
        try:
            with open(csv_path, 'r', encoding='utf-8') as csvfile:
                # Определяем формат CSV (Master.csv обычно использует определенные колонки)
                reader = csv.DictReader(csvfile)
                
                for row in reader:
                    try:
                        self._process_csv_row(row)
                    except Exception as e:
                        logger.error(f"Error processing CSV row: {e}")
                        self.errors.append(f"Row error: {e}")
                        self.error_count += 1
        
        except Exception as e:
            logger.error(f"Failed to read CSV file: {e}")
            self.errors.append(str(e))
            self.error_count += 1
        
        return self._get_import_summary()
    
    def import_from_database(
        self,
        db_config: Dict[str, str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Импорт CDR напрямую из базы данных Asterisk.
        
        Args:
            db_config: Конфигурация подключения к БД (host, user, password, database)
            start_date: Начальная дата для импорта
            end_date: Конечная дата для импорта
        
        Returns:
            Словарь с результатами импорта
        """
        try:
            import pymysql
            
            connection = pymysql.connect(
                host=db_config.get('host', 'localhost'),
                user=db_config.get('user', 'asterisk'),
                password=db_config.get('password', ''),
                database=db_config.get('database', 'asteriskcdrdb'),
                charset='utf8mb4'
            )
            
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                query = """
                    SELECT 
                        calldate, clid, src, dst, dcontext, channel, dstchannel,
                        lastapp, lastdata, duration, billsec, disposition,
                        amaflags, accountcode, uniqueid, userfield, did, recordingfile,
                        cnum, cnam, outbound_cnum, outbound_cnam, dst_cnam
                    FROM cdr
                    WHERE 1=1
                """
                params = []
                
                if start_date:
                    query += " AND calldate >= %s"
                    params.append(start_date)
                
                if end_date:
                    query += " AND calldate <= %s"
                    params.append(end_date)
                
                query += " ORDER BY calldate DESC LIMIT 1000"
                
                cursor.execute(query, params)
                
                for row in cursor:
                    try:
                        self._process_db_row(row)
                    except Exception as e:
                        logger.error(f"Error processing DB row: {e}")
                        self.errors.append(f"DB row error: {e}")
                        self.error_count += 1
            
            connection.close()
            
        except ImportError:
            error_msg = "pymysql not installed. Install it with: pip install pymysql"
            logger.error(error_msg)
            self.errors.append(error_msg)
            self.error_count += 1
        except Exception as e:
            logger.error(f"Failed to import from database: {e}")
            self.errors.append(str(e))
            self.error_count += 1
        
        return self._get_import_summary()
    
    def _process_cdr_record(self, cdr: Dict[str, Any]) -> None:
        """
        Обработать CDR запись из AMI события.
        """
        from crm.models.others import CallLog
        from voip.utils import normalize_number, find_objects_by_phone
        
        # Извлекаем данные
        caller_num = normalize_number(cdr.get('Source', ''))
        destination = normalize_number(cdr.get('Destination', ''))
        duration = int(cdr.get('BillableSeconds', 0) or cdr.get('Duration', 0))
        call_date_str = cdr.get('StartTime', '')
        disposition = cdr.get('Disposition', 'UNKNOWN')
        uniqueid = cdr.get('UniqueID', '')
        
        if not caller_num or not uniqueid:
            self.skipped_count += 1
            return
        
        # Проверяем, не импортирован ли уже этот звонок
        if CallLog.objects.filter(voip_call_id=uniqueid).exists():
            self.skipped_count += 1
            return
        
        # Ищем контакт по номеру
        contact, lead, deal, error = find_objects_by_phone(caller_num)
        matched_obj = contact or lead
        
        # Определяем направление
        direction = 'inbound' if cdr.get('Direction') == 'inbound' else 'outbound'
        
        # Создаем запись CallLog
        with transaction.atomic():
            CallLog.objects.create(
                contact=matched_obj if hasattr(matched_obj, 'id') and matched_obj.__class__.__name__ == 'Contact' else None,
                number=caller_num,
                direction=direction,
                duration=duration,
                voip_call_id=uniqueid,
                disposition=disposition,
                # created_date будет установлена автоматически
            )
        
        self.imported_count += 1
    
    def _process_csv_row(self, row: Dict[str, str]) -> None:
        """
        Обработать строку из CSV файла.
        """
        # Стандартный формат Asterisk CDR CSV
        self._process_db_row({
            'calldate': row.get('calldate'),
            'src': row.get('src'),
            'dst': row.get('dst'),
            'duration': row.get('duration'),
            'billsec': row.get('billsec'),
            'disposition': row.get('disposition'),
            'uniqueid': row.get('uniqueid'),
            'accountcode': row.get('accountcode'),
        })
    
    def _process_db_row(self, row: Dict[str, Any]) -> None:
        """
        Обработать запись из базы данных CDR.
        """
        from crm.models.others import CallLog
        from voip.utils import normalize_number, find_objects_by_phone
        
        # Извлекаем данные
        caller_num = normalize_number(row.get('src', ''))
        destination = normalize_number(row.get('dst', ''))
        duration = int(row.get('billsec', 0) or row.get('duration', 0))
        call_date = row.get('calldate')
        disposition = row.get('disposition', 'UNKNOWN')
        uniqueid = row.get('uniqueid', '')
        
        if not caller_num or not uniqueid:
            self.skipped_count += 1
            return
        
        # Проверяем дубликаты
        if CallLog.objects.filter(voip_call_id=uniqueid).exists():
            self.skipped_count += 1
            return
        
        # Ищем контакт
        contact, lead, deal, error = find_objects_by_phone(caller_num)
        matched_obj = contact or lead
        
        # Определяем направление (упрощенная логика)
        # В реальности нужно анализировать контекст и каналы
        direction = 'inbound'  # По умолчанию входящий
        
        # Создаем запись
        with transaction.atomic():
            call_log = CallLog.objects.create(
                contact=matched_obj if hasattr(matched_obj, 'id') and matched_obj.__class__.__name__ == 'Contact' else None,
                number=caller_num,
                direction=direction,
                duration=duration,
                voip_call_id=uniqueid,
                disposition=disposition,
            )
            
            # Обновляем дату создания если указана в CDR
            if call_date and isinstance(call_date, (datetime, str)):
                if isinstance(call_date, str):
                    try:
                        call_date_str = call_date.strip()
                        if call_date_str:
                            call_date = datetime.fromisoformat(call_date_str.replace('Z', '+00:00'))
                        else:
                            call_date = None
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid call_date format: {call_date}: {e}")
                        call_date = None
                
                if call_date and isinstance(call_date, datetime):
                    call_log.created_date = call_date
                    call_log.save(update_fields=['created_date'])
        
        self.imported_count += 1
    
    def _get_import_summary(self) -> Dict[str, Any]:
        """
        Получить сводку по импорту.
        """
        return {
            'success': self.error_count == 0,
            'imported': self.imported_count,
            'skipped': self.skipped_count,
            'errors': self.error_count,
            'error_details': self.errors[:10],  # Первые 10 ошибок
            'total_processed': self.imported_count + self.skipped_count + self.error_count
        }
