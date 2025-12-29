"""
Модуль для генерации Word документов
"""

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
import json
from datetime import datetime
import io


class SimpleWordDocumentGenerator:
    """Простой генератор Word документов"""
    
    def __init__(self):
        self.document = Document()
    
    def create_document(self, template_data, fields_data, document_name, user_info=None):
        """
        Создание Word документа
        
        Args:
            template_data: данные шаблона
            fields_data: заполненные поля
            document_name: название документа
            user_info: информация о пользователе
        """
        # Добавляем заголовок
        title = self.document.add_heading(document_name, 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Добавляем информацию о шаблоне
        if template_data.get('name'):
            template_info = self.document.add_paragraph()
            template_info.add_run('Шаблон: ').bold = True
            template_info.add_run(template_data['name'])
        
        if template_data.get('category'):
            category_info = self.document.add_paragraph()
            category_info.add_run('Категория: ').bold = True
            category_info.add_run(template_data['category'])
        
        # Информация о создании
        creation_info = self.document.add_paragraph()
        creation_info.add_run('Дата создания: ').bold = True
        creation_info.add_run(datetime.now().strftime('%d.%m.%Y %H:%M'))
        
        if user_info:
            user_line = self.document.add_paragraph()
            user_line.add_run('Пользователь: ').bold = True
            user_line.add_run(user_info.get('username', 'Неизвестно'))
            if user_info.get('full_name'):
                user_line.add_run(f" ({user_info['full_name']})")
        
        # Разделитель
        self.document.add_paragraph()
        self.document.add_paragraph('_' * 50)
        self.document.add_paragraph()
        
        # Заголовок для заполненных данных
        data_title = self.document.add_heading('Заполненные данные:', level=1)
        
        # Добавляем заполненные поля в виде таблицы
        if fields_data:
            table = self.document.add_table(rows=1, cols=2)
            table.style = 'Light Shading'
            
            # Заголовки таблицы
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = 'Поле'
            hdr_cells[1].text = 'Значение'
            
            # Делаем заголовки жирными
            for cell in hdr_cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.bold = True
            
            # Добавляем данные
            for key, value in fields_data.items():
                if value:  # Пропускаем пустые значения
                    row_cells = table.add_row().cells
                    row_cells[0].text = str(key)
                    row_cells[1].text = str(value)
        
        # Добавляем сноску
        self.document.add_page_break()
        footnote = self.document.add_paragraph()
        footnote.alignment = WD_ALIGN_PARAGRAPH.CENTER
        footnote.add_run('Документ сгенерирован автоматически с помощью Document Generator').italic = True
        footnote.add_run('\n')
        footnote.add_run(f'Дата создания: {datetime.now().strftime("%d.%m.%Y %H:%M")}').italic = True
        
        return self.document
    
    def get_document_bytes(self):
        """Получение документа в виде байтов"""
        output = io.BytesIO()
        self.document.save(output)
        output.seek(0)
        return output.getvalue()


def generate_word_document(template_data, fields_data, document_name, user_info=None):
    """
    Функция для генерации Word документа
    
    Args:
        template_data: данные шаблона
        fields_data: заполненные поля
        document_name: название документа
        user_info: информация о пользователе
    
    Returns:
        bytes: содержимое Word документа
    """
    try:
        generator = SimpleWordDocumentGenerator()
        generator.create_document(template_data, fields_data, document_name, user_info)
        return generator.get_document_bytes()
    except Exception as e:
        # В случае ошибки создаем простейший документ
        print(f"Ошибка генерации Word документа: {e}")
        return create_fallback_document(document_name, fields_data)


def create_fallback_document(document_name, fields_data):
    """Создание простого документа на случай ошибки"""
    doc = Document()
    
    # Заголовок
    title = doc.add_heading(document_name, 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Дата
    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_para.add_run(f'Создано: {datetime.now().strftime("%d.%m.%Y %H:%M")}').italic = True
    
    # Разделитель
    doc.add_paragraph()
    doc.add_paragraph('=' * 50)
    doc.add_paragraph()
    
    # Данные
    doc.add_heading('Данные документа:', level=1)
    
    for key, value in fields_data.items():
        if value:
            para = doc.add_paragraph()
            para.add_run(f'{key}: ').bold = True
            para.add_run(str(value))
    
    # Сохраняем в bytes
    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    return output.getvalue()


def generate_contract_document(fields_data, document_name, user_info=None):
    """
    Генерация договора в формате Word
    
    Args:
        fields_data: данные для заполнения договора
        document_name: название документа
        user_info: информация о пользователе
    
    Returns:
        bytes: содержимое Word документа
    """
    doc = Document()
    
    # Заголовок
    title = doc.add_heading('ДОГОВОР', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Номер и дата
    if fields_data.get('contract_number'):
        doc.add_paragraph(f"№ {fields_data['contract_number']}")
    
    if fields_data.get('contract_date'):
        date_para = doc.add_paragraph(f"«{fields_data['contract_date']}» г.")
        date_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    
    # Разделитель
    doc.add_paragraph()
    
    # 1. ПРЕДМЕТ ДОГОВОРА
    doc.add_heading('1. ПРЕДМЕТ ДОГОВОРА', level=1)
    
    if fields_data.get('customer'):
        doc.add_paragraph(f"Заказчик: {fields_data['customer']}")
    
    if fields_data.get('executor'):
        doc.add_paragraph(f"Исполнитель: {fields_data['executor']}")
    
    if fields_data.get('subject'):
        doc.add_paragraph(f"Предмет договора: {fields_data['subject']}")
    
    # 2. ОБЯЗАННОСТИ СТОРОН
    doc.add_heading('2. ОБЯЗАННОСТИ СТОРОН', level=1)
    
    if fields_data.get('customer_obligations'):
        doc.add_paragraph(f"2.1. Заказчик обязуется: {fields_data['customer_obligations']}")
    
    if fields_data.get('executor_obligations'):
        doc.add_paragraph(f"2.2. Исполнитель обязуется: {fields_data['executor_obligations']}")
    
    # 3. СРОК ДЕЙСТВИЯ ДОГОВОРА
    if fields_data.get('term'):
        doc.add_heading('3. СРОК ДЕЙСТВИЯ ДОГОВОРА', level=1)
        doc.add_paragraph(f"Договор действует: {fields_data['term']}")
    
    # 4. СТОИМОСТЬ И ПОРЯДОК РАСЧЕТОВ
    if fields_data.get('price'):
        doc.add_heading('4. СТОИМОСТЬ И ПОРЯДОК РАСЧЕТОВ', level=1)
        doc.add_paragraph(f"Стоимость работ/услуг: {fields_data['price']}")
    
    # 5. ПОДПИСИ СТОРОН
    doc.add_heading('5. ПОДПИСИ СТОРОН', level=1)
    
    doc.add_paragraph("ЗАКАЗЧИК:")
    doc.add_paragraph("___________________________")
    if fields_data.get('customer_position'):
        doc.add_paragraph(f"Должность: {fields_data['customer_position']}")
    if fields_data.get('customer_name'):
        doc.add_paragraph(f"ФИО: {fields_data['customer_name']}")
    
    doc.add_paragraph()
    doc.add_paragraph("ИСПОЛНИТЕЛЬ:")
    doc.add_paragraph("___________________________")
    if fields_data.get('executor_position'):
        doc.add_paragraph(f"Должность: {fields_data['executor_position']}")
    if fields_data.get('executor_name'):
        doc.add_paragraph(f"ФИО: {fields_data['executor_name']}")
    
    # Сноска
    doc.add_page_break()
    footnote = doc.add_paragraph()
    footnote.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footnote.add_run('Документ сгенерирован автоматически').italic = True
    footnote.add_run('\n')
    footnote.add_run(f'Дата: {datetime.now().strftime("%d.%m.%Y")}').italic = True
    
    # Сохраняем в bytes
    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    return output.getvalue()