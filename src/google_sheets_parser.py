import os
import json
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


class GoogleSheetsParser:
    def __init__(self, credentials_file: str, spreadsheet_url: str, batch_size: int = 10):
        self.credentials_file = credentials_file
        self.spreadsheet_url = spreadsheet_url
        self.batch_size = batch_size
        self.client = None
        self.spreadsheet = None
        self.current_worksheet = None
        
    def authenticate(self) -> None:
        if not os.path.exists(self.credentials_file):
            raise FileNotFoundError(f"Credentials file not found: {self.credentials_file}")
            
        scope = ['https://spreadsheets.google.com/feeds', 
                'https://www.googleapis.com/auth/drive']
        
        creds = Credentials.from_service_account_file(self.credentials_file, scopes=scope)
        self.client = gspread.authorize(creds)
        
    def connect_to_spreadsheet(self) -> None:
        if not self.client:
            self.authenticate()
            
        spreadsheet_id = self._extract_spreadsheet_id(self.spreadsheet_url)
        self.spreadsheet = self.client.open_by_key(spreadsheet_id)
        
    def _set_worksheet(self, sheet_name: str) -> None:
        if not self.spreadsheet:
            self.connect_to_spreadsheet()
            
        try:
            self.current_worksheet = self.spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            available_sheets = [ws.title for ws in self.spreadsheet.worksheets()]
            raise ValueError(f"Лист '{sheet_name}' не найден. Доступные листы: {available_sheets}")
        
    def _extract_spreadsheet_id(self, url: str) -> str:
        if "/d/" in url:
            return url.split("/d/")[1].split("/")[0]
        raise ValueError(f"Invalid Google Sheets URL: {url}")
        
    def parse_warehouses(self) -> List[str]:
        cell_value = self.current_worksheet.acell('B4').value
        if not cell_value:
            return []
        return [warehouse.strip() for warehouse in cell_value.split(',')]
        
    def parse_dates(self) -> Tuple[str, str]:
        start_date = self.current_worksheet.acell('B5').value
        end_date = self.current_worksheet.acell('B6').value
        return start_date, end_date
        
    def parse_products(self) -> List[ProductInfo]:
        start_row = 8
        products = []
        
        batch_start = start_row
        while True:
            batch_end = batch_start + self.batch_size - 1
            
            barcode_range = f'B{batch_start}:B{batch_end}'
            quantity_range = f'C{batch_start}:C{batch_end}'
            
            barcode_values = self.current_worksheet.batch_get([barcode_range])[0]
            quantity_values = self.current_worksheet.batch_get([quantity_range])[0]
            
            barcode_list = barcode_values if barcode_values else []
            quantity_list = quantity_values if quantity_values else []
            
            has_data = False
            for i in range(len(barcode_list)):
                barcode = barcode_list[i][0] if barcode_list[i] else None
                quantity_str = quantity_list[i][0] if i < len(quantity_list) and quantity_list[i] else None
                
                if barcode and barcode.strip():
                    has_data = True
                    try:
                        quantity = int(quantity_str) if quantity_str else 0
                    except (ValueError, TypeError):
                        quantity = 0
                        
                    products.append(ProductInfo(barcode=barcode.strip(), quantity=quantity))
                    
            if not has_data:
                break
                
            batch_start = batch_end + 1
            
        return products
        
    def get_available_sheets(self) -> List[str]:
        if not self.spreadsheet:
            self.connect_to_spreadsheet()
        
        return [ws.title for ws in self.spreadsheet.worksheets()]
        
    def _parse_sheet_data(self, sheet_name: str) -> SheetsData:
        self._set_worksheet(sheet_name)
            
        warehouses = self.parse_warehouses()
        start_date, end_date = self.parse_dates()
        products = self.parse_products()
        
        return SheetsData(
            warehouses=warehouses,
            start_date=start_date,
            end_date=end_date,
            products=products
        )
        
    def parse_all_sheets(self) -> Dict[str, SheetsData]:
        available_sheets = self.get_available_sheets()
        results = {}
        
        for sheet_name in available_sheets:
            try:
                print(f"Парсинг листа: {sheet_name}")
                data = self._parse_sheet_data(sheet_name)
                results[sheet_name] = data
            except Exception as e:
                print(f"Ошибка при парсинге листа '{sheet_name}': {e}")
                
        return results
        
    def to_dict(self, all_sheets_data: Dict[str, SheetsData]) -> Dict:
        result = {
            'sheets': {},
            'parsed_at': datetime.now().isoformat(),
            'total_sheets': len(all_sheets_data)
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
                'total_products': len(sheet_data.products)
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