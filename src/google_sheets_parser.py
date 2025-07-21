import os
import json
import logging
import time
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from dataclasses import dataclass


@dataclass
class ProductInfo:
    barcode: str
    quantity: int


@dataclass
class SheetsData:
    warehouses: List[str]
    start_date: str
    end_date: str
    products: List[ProductInfo]
    max_coefficient: float


class GoogleSheetsParser:
    def __init__(self, credentials_file: str, spreadsheet_url: str, batch_size: int = 10):
        self.credentials_file = credentials_file
        self.spreadsheet_url = spreadsheet_url
        self.batch_size = batch_size
        self.client = None
        self.spreadsheet = None
        self.current_worksheet = None
        self.api_requests_count = 0  # Счетчик API запросов
        self._setup_logger()
        
    def _setup_logger(self):
        os.makedirs('logs/google', exist_ok=True)
        
        self.logger = logging.getLogger('google_sheets_parser')
        self.logger.setLevel(logging.ERROR)
        
        if not self.logger.handlers:
            handler = logging.FileHandler('logs/google/parsing_errors.log', encoding='utf-8')
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        
    def authenticate(self) -> None:
        try:
            if not os.path.exists(self.credentials_file):
                error_msg = f"Credentials file not found: {self.credentials_file}"
                self.logger.error(error_msg)
                raise FileNotFoundError(error_msg)
                
            scope = ['https://spreadsheets.google.com/feeds', 
                    'https://www.googleapis.com/auth/drive']
            
            creds = Credentials.from_service_account_file(self.credentials_file, scopes=scope)
            self.client = gspread.authorize(creds)
        except Exception as e:
            self.logger.error(f"Ошибка аутентификации: {str(e)} | API запросов выполнено: {self.api_requests_count}")
            raise
        
    def connect_to_spreadsheet(self) -> None:
        try:
            if not self.client:
                self.authenticate()
                
            spreadsheet_id = self._extract_spreadsheet_id(self.spreadsheet_url)
            self.spreadsheet = self.client.open_by_key(spreadsheet_id)
        except Exception as e:
            self.logger.error(f"Ошибка подключения к таблице {self.spreadsheet_url}: {str(e)} | API запросов выполнено: {self.api_requests_count}")
            raise
        
    def _set_worksheet(self, sheet_name: str) -> None:
        try:
            if not self.spreadsheet:
                self.connect_to_spreadsheet()
                
            self.current_worksheet = self.spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            available_sheets = [ws.title for ws in self.spreadsheet.worksheets()]
            error_msg = f"Лист '{sheet_name}' не найден. Доступные листы: {available_sheets}"
            self.logger.error(error_msg + f" | API запросов выполнено: {self.api_requests_count}")
            raise ValueError(error_msg)
        except Exception as e:
            self.logger.error(f"Ошибка подключения к листу '{sheet_name}': {str(e)} | API запросов выполнено: {self.api_requests_count}")
            raise
        
    def _extract_spreadsheet_id(self, url: str) -> str:
        if "/d/" in url:
            return url.split("/d/")[1].split("/")[0]
        raise ValueError(f"Invalid Google Sheets URL: {url}")
        
    def _retry_with_backoff(self, func, max_retries=3):
        """Выполняет функцию с exponential backoff при ошибках API"""
        for attempt in range(max_retries):
            try:
                result = func()
                self.api_requests_count += 1  # Увеличиваем счетчик при успешном запросе
                return result
            except Exception as e:
                if attempt == max_retries - 1:
                    self.api_requests_count += 1  # Учитываем неудачный запрос тоже
                    raise
                
                if "429" in str(e) or "quota" in str(e).lower() or "limit" in str(e).lower():
                    wait_time = (2 ** attempt) + (attempt * 0.1)
                    self.logger.warning(f"API limit hit, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    self.api_requests_count += 1  # Учитываем каждую попытку
                else:
                    self.api_requests_count += 1  # Учитываем неудачный запрос
                    raise
    
    def parse_metadata(self) -> Tuple[List[str], str, str, float]:
        """Парсит метаданные листа одним batch запросом"""
        def _get_metadata():
            return self.current_worksheet.batch_get(['B4', 'B5', 'B6', 'E1'])
        
        try:
            batch_result = self._retry_with_backoff(_get_metadata)
            
            # Извлекаем значения из batch результата
            warehouses_value = batch_result[0][0][0] if batch_result[0] and batch_result[0][0] else None
            start_date = batch_result[1][0][0] if batch_result[1] and batch_result[1][0] else None
            end_date = batch_result[2][0][0] if batch_result[2] and batch_result[2][0] else None
            coefficient_value = batch_result[3][0][0] if batch_result[3] and batch_result[3][0] else None
            
            # Обрабатываем warehouses
            warehouses = []
            if warehouses_value:
                warehouses = [warehouse.strip() for warehouse in warehouses_value.split(',')]
            
            # Обрабатываем коэффициент
            max_coefficient = 1.0
            try:
                max_coefficient = float(coefficient_value) if coefficient_value else 1.0
            except (ValueError, TypeError):
                max_coefficient = 1.0
            
            return warehouses, start_date, end_date, max_coefficient
            
        except Exception as e:
            self.logger.error(f"Ошибка получения метаданных листа '{self.current_worksheet.title}': {str(e)} | API запросов выполнено: {self.api_requests_count}")
            return [], None, None, 1.0
        
    def parse_products(self) -> List[ProductInfo]:
        start_row = 8
        products = []
        
        try:
            batch_start = start_row
            while True:
                batch_end = batch_start + self.batch_size - 1
                
                barcode_range = f'B{batch_start}:B{batch_end}'
                quantity_range = f'C{batch_start}:C{batch_end}'
                
                def _get_batch_data():
                    return self.current_worksheet.batch_get([barcode_range, quantity_range])
                
                try:
                    batch_result = self._retry_with_backoff(_get_batch_data)
                    barcode_values = batch_result[0] if batch_result[0] else []
                    quantity_values = batch_result[1] if batch_result[1] else []
                except Exception as e:
                    self.logger.error(f"Ошибка получения данных в диапазоне {barcode_range}-{quantity_range} листа '{self.current_worksheet.title}': {str(e)} | API запросов выполнено: {self.api_requests_count}")
                    break
                
                barcode_list = barcode_values if barcode_values else []
                quantity_list = quantity_values if quantity_values else []
                
                has_data = False
                for i in range(len(barcode_list)):
                    try:
                        barcode = barcode_list[i][0] if barcode_list[i] else None
                        quantity_str = quantity_list[i][0] if i < len(quantity_list) and quantity_list[i] else None
                        
                        if barcode and barcode.strip():
                            has_data = True
                            try:
                                quantity = int(quantity_str) if quantity_str else 0
                            except (ValueError, TypeError):
                                quantity = 0
                                self.logger.error(f"Некорректное количество '{quantity_str}' для товара '{barcode}' в строке {batch_start + i} листа '{self.current_worksheet.title}' | API запросов выполнено: {self.api_requests_count}")
                                
                            products.append(ProductInfo(barcode=barcode.strip(), quantity=quantity))
                    except Exception as e:
                        self.logger.error(f"Ошибка обработки строки {batch_start + i} листа '{self.current_worksheet.title}': {str(e)} | API запросов выполнено: {self.api_requests_count}")
                        continue
                        
                if not has_data:
                    break
                    
                batch_start = batch_end + 1
        except Exception as e:
            self.logger.error(f"Критическая ошибка парсинга товаров в листе '{self.current_worksheet.title}': {str(e)} | API запросов выполнено: {self.api_requests_count}")
            
        return products
        
    def get_available_sheets(self) -> List[str]:
        if not self.spreadsheet:
            self.connect_to_spreadsheet()
        
        self.api_requests_count += 1  # Запрос списка листов
        return [ws.title for ws in self.spreadsheet.worksheets()]
        
    def _parse_sheet_data(self, sheet_name: str) -> SheetsData:
        self._set_worksheet(sheet_name)
            
        warehouses, start_date, end_date, max_coefficient = self.parse_metadata()
        products = self.parse_products()
        
        return SheetsData(
            warehouses=warehouses,
            start_date=start_date,
            end_date=end_date,
            products=products,
            max_coefficient=max_coefficient
        )
        
    def parse_all_sheets(self) -> Dict[str, SheetsData]:
        self.api_requests_count = 0  # Сбрасываем счетчик в начале парсинга
        available_sheets = self.get_available_sheets()
        results = {}
        
        for sheet_name in available_sheets:
            try:
                print(f"Парсинг листа: {sheet_name}")
                data = self._parse_sheet_data(sheet_name)
                results[sheet_name] = data
            except Exception as e:
                error_msg = f"Ошибка при парсинге листа '{sheet_name}': {e} | API запросов выполнено: {self.api_requests_count}"
                print(error_msg)
                self.logger.error(error_msg)
                
        return results
        
    def to_dict(self, all_sheets_data: Dict[str, SheetsData]) -> Dict:
        result = {
            'sheets': {},
            'parsed_at': datetime.now().isoformat(),
            'total_sheets': len(all_sheets_data),
            'google_api_requests': self.api_requests_count  # Добавляем количество запросов
        }
        
        for sheet_name, sheet_data in all_sheets_data.items():
            result['sheets'][sheet_name] = {
                'warehouses': sheet_data.warehouses,
                'start_date': sheet_data.start_date,
                'end_date': sheet_data.end_date,
                'products': [
                    {'barcode': product.barcode, 'quantity': product.quantity}
                    for product in sheet_data.products
                ],
                'total_products': len(sheet_data.products),
                'max_coefficient': sheet_data.max_coefficient
            }
            
        return result


def create_parser_from_env() -> GoogleSheetsParser:
    from dotenv import load_dotenv
    load_dotenv()
    
    credentials_file = os.getenv('GOOGLE_CREDENTIALS_FILE')
    spreadsheet_url = os.getenv('GOOGLE_SHEETS_URL')
    batch_size = int(os.getenv('BATCH_SIZE', '10'))
    
    if not credentials_file or not spreadsheet_url:
        raise ValueError("GOOGLE_CREDENTIALS_FILE and GOOGLE_SHEETS_URL must be set in .env")
        
    return GoogleSheetsParser(credentials_file, spreadsheet_url, batch_size)