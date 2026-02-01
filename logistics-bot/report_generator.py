"""
Генератор PDF отчетов для Margiana Logistic Services
"""

import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.units import inch, cm
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import pytz
from supabase import Client

def generate_pdf_report(supabase_client: Client) -> str:
    """Генерация PDF отчета"""
    
    TIMEZONE = pytz.timezone('Asia/Ashgabat')
    now = datetime.now(TIMEZONE)
    
    # Создаем временный файл
    pdf_path = f"Margiana_Report_{now.strftime('%Y%m%d_%H%M')}.pdf"
    
    try:
        # Получаем данные
        orders_response = supabase_client.table('cloud_orders').select('*').execute()
        orders = orders_response.data
        
        tasks_response = supabase_client.table('cloud_tasks').select('*').execute()
        tasks = tasks_response.data
        
        containers_response = supabase_client.table('cloud_containers').select('*').execute()
        containers = containers_response.data
        
        # Создаем документ
        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Стили
        styles = getSampleStyleSheet()
        
        # Создаем собственные стили
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2C3E50'),
            alignment=TA_CENTER,
            spaceAfter=30
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#34495E'),
            alignment=TA_LEFT,
            spaceAfter=12
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.black,
            alignment=TA_LEFT
        )
        
        # Содержимое документа
        story = []
        
        # Заголовок
        title = Paragraph("MARGIANA LOGISTIC SERVICES", title_style)
        story.append(title)
        
        subtitle = Paragraph(f"Отчет от {now.strftime('%d.%m.%Y %H:%M')}", subtitle_style)
        story.append(subtitle)
        
        story.append(Spacer(1, 20))
        
        # Раздел 1: Статистика
        stats_title = Paragraph("📊 ОБЩАЯ СТАТИСТИКА", subtitle_style)
        story.append(stats_title)
        
        total_orders = len(orders)
        active_orders = sum(1 for o in orders if o.get('status') not in ['Completed', 'Cancelled'])
        completed_orders = sum(1 for o in orders if o.get('status') == 'Completed')
        
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.get('status') == 'Completed')
        
        total_containers = len(containers)
        in_transit = sum(1 for c in containers if c.get('arrival_turkmenistan_date') is None)
        
        stats_data = [
            ["Показатель", "Значение"],
            ["Всего заказов", str(total_orders)],
            ["Активные заказы", str(active_orders)],
            ["Завершенные заказы", str(completed_orders)],
            ["Всего задач", str(total_tasks)],
            ["Выполненные задачи", str(completed_tasks)],
            ["Всего контейнеров", str(total_containers)],
            ["Контейнеров в пути", str(in_transit)]
        ]
        
        stats_table = Table(stats_data, colWidths=[3*inch, 1.5*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        
        story.append(stats_table)
        story.append(Spacer(1, 20))
        
        # Раздел 2: Активные заказы
        active_title = Paragraph("🚚 АКТИВНЫЕ ЗАКАЗЫ", subtitle_style)
        story.append(active_title)
        
        active_statuses = ['New', 'In Progress CHN', 'In Transit CHN-IR', 
                         'In Progress IR', 'In Transit IR-TKM']
        active_orders_list = [o for o in orders if o.get('status') in active_statuses][:10]
        
        if active_orders_list:
            active_data = [["Номер", "Клиент", "Статус", "ETA"]]
            
            for order in active_orders_list:
                order_num = order.get('order_number', 'N/A')[:15]
                client = order.get('client_name', 'N/A')[:20]
                status = order.get('status', 'N/A')[:15]
                eta = order.get('eta_date', '')
                
                if eta:
                    try:
                        eta_date = datetime.fromisoformat(eta.replace('Z', '+00:00')).astimezone(TIMEZONE)
                        eta_str = eta_date.strftime('%d.%m')
                    except:
                        eta_str = eta[:10]
                else:
                    eta_str = "-"
                
                active_data.append([order_num, client, status, eta_str])
            
            active_table = Table(active_data, colWidths=[1.5*inch, 2*inch, 1.5*inch, 1*inch])
            active_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.whitesmoke]),
            ]))
            
            story.append(active_table)
        else:
            story.append(Paragraph("Нет активных заказов", normal_style))
        
        story.append(Spacer(1, 20))
        
        # Раздел 3: Требующие внимания
        attention_title = Paragraph("⚠️ ТРЕБУЕТ ВНИМАНИЯ", subtitle_style)
        story.append(attention_title)
        
        no_photo = sum(1 for o in orders if not o.get('has_loading_photo') and o.get('status') in active_statuses)
        no_local = sum(1 for o in orders if not o.get('has_local_charges') and o.get('status') in active_statuses)
        no_tex = sum(1 for o in orders if not o.get('has_tex') and o.get('status') in active_statuses)
        
        attention_data = [
            ["Проблема", "Количество"],
            ["Без фото загрузки", str(no_photo)],
            ["Без местных сборов", str(no_local)],
            ["Без TLX", str(no_tex)]
        ]
        
        attention_table = Table(attention_data, colWidths=[2.5*inch, 1*inch])
        attention_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E74C3C')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        
        story.append(attention_table)
        story.append(Spacer(1, 20))
        
        # Подвал
        footer = Paragraph(
            f"Отчет сгенерирован автоматически<br/>"
            f"Margiana Logistic Services • {now.strftime('%d.%m.%Y %H:%M')}<br/>"
            f"Туркменистан, Ашхабад • +993 61 55 77 79",
            ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=8,
                textColor=colors.grey,
                alignment=TA_CENTER,
                spaceBefore=20
            )
        )
        story.append(footer)
        
        # Собираем PDF
        doc.build(story)
        
        return pdf_path
        
    except Exception as e:
        print(f"Ошибка при генерации PDF: {e}")
        return None