import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, PageBreak, Image)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from config import REPORTS_DIR, SENSOR_TYPES

logger = logging.getLogger(__name__)

FONT_PATHS = [
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]

def register_polish_fonts():
    font_registered = False
    
    try:
        pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
        pdfmetrics.registerFont(TTFont('Arial-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
        font_registered = True
        return 'Arial', 'Arial-Bold'
    except:
        pass
    
    try:
        pdfmetrics.registerFont(TTFont('DejaVuSans', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
        font_registered = True
        return 'DejaVuSans', 'DejaVuSans-Bold'
    except:
        pass
    
    try:
        pdfmetrics.registerFont(TTFont('Liberation', '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'))
        pdfmetrics.registerFont(TTFont('Liberation-Bold', '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'))
        font_registered = True
        return 'Liberation', 'Liberation-Bold'
    except:
        pass
    
    logger.warning("Could not register Polish fonts, using Helvetica (Polish characters may not display)")
    return 'Helvetica', 'Helvetica-Bold'


FONT_NORMAL, FONT_BOLD = register_polish_fonts()


class CalibrationReportGenerator:
    def __init__(self):
        self.reports_dir = Path(REPORTS_DIR)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.styles = self._create_styles()

    def _create_styles(self) -> Dict:
        base_styles = getSampleStyleSheet()
        
        styles = {
            'Title': ParagraphStyle(
                'Title',
                parent=base_styles['Heading1'],
                fontName=FONT_BOLD,
                fontSize=16,
                alignment=TA_CENTER,
                spaceAfter=12*mm
            ),
            'Heading1': ParagraphStyle(
                'Heading1',
                parent=base_styles['Heading1'],
                fontName=FONT_BOLD,
                fontSize=14,
                spaceBefore=8*mm,
                spaceAfter=4*mm
            ),
            'Heading2': ParagraphStyle(
                'Heading2',
                parent=base_styles['Heading2'],
                fontName=FONT_BOLD,
                fontSize=12,
                spaceBefore=6*mm,
                spaceAfter=3*mm
            ),
            'Normal': ParagraphStyle(
                'Normal',
                parent=base_styles['Normal'],
                fontName=FONT_NORMAL,
                fontSize=10,
                alignment=TA_JUSTIFY,
                spaceBefore=2*mm,
                spaceAfter=2*mm
            ),
            'TableHeader': ParagraphStyle(
                'TableHeader',
                parent=base_styles['Normal'],
                fontName=FONT_BOLD,
                fontSize=9,
                alignment=TA_CENTER
            ),
            'TableCell': ParagraphStyle(
                'TableCell',
                parent=base_styles['Normal'],
                fontName=FONT_NORMAL,
                fontSize=9,
                alignment=TA_CENTER
            ),
            'Footer': ParagraphStyle(
                'Footer',
                parent=base_styles['Normal'],
                fontName=FONT_NORMAL,
                fontSize=8,
                alignment=TA_CENTER
            ),
            'Small': ParagraphStyle(
                'Small',
                parent=base_styles['Normal'],
                fontName=FONT_NORMAL,
                fontSize=8,
                spaceBefore=1*mm,
                spaceAfter=1*mm
            )
        }
        return styles

    def generate_report(self, session_data: Dict, output_path: str = None) -> str:
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = session_data.get('session', {}).get('session_id', 'unknown')
            output_path = str(self.reports_dir / f"swiadectwo_{session_id}_{timestamp}.pdf")
        
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=25*mm,
            bottomMargin=20*mm
        )
        
        story = []
        
        story.extend(self._create_header(session_data))
        story.extend(self._create_session_info(session_data))
        story.extend(self._create_methodology_section())
        story.extend(self._create_equipment_section(session_data))
        story.extend(self._create_results_section(session_data))
        story.extend(self._create_uncertainty_section())
        story.extend(self._create_conclusion_section(session_data))
        story.extend(self._create_signature_section(session_data))
        
        doc.build(story)
        logger.info(f"Report generated: {output_path}")
        return output_path

    def _create_header(self, session_data: Dict) -> List:
        elements = []
        
        elements.append(Paragraph("ŚWIADECTWO WZORCOWANIA", self.styles['Title']))
        
        session = session_data.get('session', {})
        session_id = session.get('session_id', 'N/A')
        order_number = session.get('order_number', '')
        
        cert_number = f"SW/{session_id}/{datetime.now().strftime('%Y')}"
        if order_number:
            cert_number += f"/{order_number}"
        
        elements.append(Paragraph(f"Nr: {cert_number}", self.styles['Heading2']))
        elements.append(Spacer(1, 5*mm))
        
        return elements

    def _create_session_info(self, session_data: Dict) -> List:
        elements = []
        session = session_data.get('session', {})
        
        elements.append(Paragraph("1. Informacje ogólne", self.styles['Heading1']))
        
        info_data = [
            ["Zleceniodawca:", session.get('client', 'N/A')],
            ["Nr zlecenia:", session.get('order_number', 'N/A')],
            ["Data wzorcowania:", session.get('start_time', 'N/A')[:10] if session.get('start_time') else 'N/A'],
            ["Wykonawca:", session.get('operator', 'N/A')],
        ]
        
        if session.get('ambient_temperature'):
            info_data.append(["Temperatura otoczenia:", f"{session['ambient_temperature']:.1f} °C"])
        if session.get('relative_humidity'):
            info_data.append(["Wilgotność względna:", f"{session['relative_humidity']:.1f} %"])
        
        table = Table(info_data, colWidths=[50*mm, 100*mm])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), FONT_BOLD),
            ('FONTNAME', (1, 0), (1, -1), FONT_NORMAL),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3*mm),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 5*mm))
        
        return elements

    def _create_methodology_section(self) -> List:
        elements = []
        
        elements.append(Paragraph("2. Metodologia wzorcowania", self.styles['Heading1']))
        
        methodology_text = """
        Wzorcowanie przeprowadzono metodą porównawczą w piecu kalibracyjnym. 
        Czujniki wzorcowane umieszczono w jednolitym polu temperatury wraz z 
        termometrem referencyjnym. Dla każdego punktu wzorcowania wykonano serię 
        pomiarów po ustabilizowaniu temperatury pieca. Błąd wzorcowania wyznaczono 
        jako różnicę między wskazaniem czujnika wzorcowanego a wskazaniem 
        termometru referencyjnego.
        """
        elements.append(Paragraph(methodology_text.strip(), self.styles['Normal']))
        
        elements.append(Paragraph(
            "Niepewność pomiarową obliczono zgodnie z przewodnikiem GUM "
            "(Guide to the Expression of Uncertainty in Measurement), "
            "uwzględniając składowe niepewności typu A i typu B.",
            self.styles['Normal']
        ))
        
        return elements

    def _create_equipment_section(self, session_data: Dict) -> List:
        elements = []
        
        elements.append(Paragraph("3. Aparatura pomiarowa", self.styles['Heading1']))
        
        equipment = [
            ["Przyrząd", "Typ/Model", "Nr fabryczny", "Nr certyfikatu"],
            ["Termometr precyzyjny", "Cropico 3001", "SN-001", "CAL-2024-001"],
            ["Piec wzorcowy", "Pegasus", "SN-002", "CAL-2024-002"],
            ["Termometr referencyjny", "PT100 klasy AA", "REF-001", "CAL-2024-003"],
        ]
        
        table = Table(equipment, colWidths=[45*mm, 40*mm, 35*mm, 35*mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('FONTNAME', (0, 0), (-1, 0), FONT_BOLD),
            ('FONTNAME', (0, 1), (-1, -1), FONT_NORMAL),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2*mm),
            ('TOPPADDING', (0, 0), (-1, -1), 2*mm),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 5*mm))
        
        return elements

    def _create_results_section(self, session_data: Dict) -> List:
        elements = []
        
        elements.append(Paragraph("4. Wyniki wzorcowania", self.styles['Heading1']))
        
        results = session_data.get('results', [])
        sensors = session_data.get('sensors', [])
        
        if not results:
            elements.append(Paragraph("Brak wyników wzorcowania.", self.styles['Normal']))
            return elements
        
        channels = sorted(set(r['channel_name'] for r in results))
        
        for channel in channels:
            channel_results = [r for r in results if r['channel_name'] == channel]
            
            if not channel_results:
                continue
            
            sensor_info = next((s for s in sensors if s.get('channel_name') == channel), {})
            sensor_type = sensor_info.get('sensor_type', 'N/A')
            serial_number = sensor_info.get('serial_number', 'N/A')
            
            elements.append(Paragraph(
                f"Kanał {channel} - Typ: {sensor_type}, Nr fab.: {serial_number}",
                self.styles['Heading2']
            ))
            
            table_data = [
                ["T zadana\n[°C]", "T zmierzona\n[°C]", "T referencyjna\n[°C]", 
                 "Błąd\n[°C]", "U(k=2)\n[°C]", "Klasa"]
            ]
            
            for r in sorted(channel_results, key=lambda x: x['point_temperature']):
                error = r['avg_measured_temp'] - r['avg_reference_temp']
                table_data.append([
                    f"{r['point_temperature']:.1f}",
                    f"{r['avg_measured_temp']:.3f}",
                    f"{r['avg_reference_temp']:.3f}",
                    f"{error:+.3f}",
                    f"±{r['expanded_uncertainty']:.3f}",
                    r['sensor_class']
                ])
            
            table = Table(table_data, colWidths=[25*mm, 28*mm, 28*mm, 22*mm, 22*mm, 25*mm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('FONTNAME', (0, 0), (-1, 0), FONT_BOLD),
                ('FONTNAME', (0, 1), (-1, -1), FONT_NORMAL),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2*mm),
                ('TOPPADDING', (0, 0), (-1, -1), 2*mm),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 5*mm))
        
        return elements

    def _create_uncertainty_section(self) -> List:
        elements = []
        
        elements.append(Paragraph("5. Budżet niepewności", self.styles['Heading1']))
        
        uncertainty_sources = [
            ["Źródło niepewności", "Wartość [°C]", "Rozkład", "u [°C]"],
            ["Niepewność wzorca", "0.01", "Normalny", "0.010"],
            ["Rozdzielczość przyrządu", "0.001", "Prostokątny", "0.0006"],
            ["Stabilność temperatury pieca", "0.02", "Prostokątny", "0.0115"],
            ["Jednorodność pola temperatury", "0.05", "Prostokątny", "0.0289"],
            ["Dryft międzywzorcowy", "0.01", "Prostokątny", "0.0058"],
        ]
        
        table = Table(uncertainty_sources, colWidths=[55*mm, 30*mm, 30*mm, 25*mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('FONTNAME', (0, 0), (-1, 0), FONT_BOLD),
            ('FONTNAME', (0, 1), (-1, -1), FONT_NORMAL),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2*mm),
            ('TOPPADDING', (0, 0), (-1, -1), 2*mm),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 3*mm))
        
        elements.append(Paragraph(
            "Niepewność rozszerzona U obliczona dla współczynnika rozszerzenia k=2, "
            "co odpowiada poziomowi ufności około 95%.",
            self.styles['Small']
        ))
        
        return elements

    def _create_conclusion_section(self, session_data: Dict) -> List:
        elements = []
        
        elements.append(Paragraph("6. Podsumowanie", self.styles['Heading1']))
        
        results = session_data.get('results', [])
        
        if results:
            compliant_count = sum(1 for r in results if r.get('is_compliant'))
            total_count = len(results)
            
            if compliant_count == total_count:
                conclusion = "Wszystkie wzorcowane czujniki spełniają wymagania swoich klas dokładności."
            elif compliant_count > 0:
                conclusion = f"Spośród {total_count} pomiarów, {compliant_count} spełnia wymagania klas dokładności."
            else:
                conclusion = "Żaden z wzorcowanych czujników nie spełnia wymagań deklarowanej klasy dokładności."
        else:
            conclusion = "Brak wyników do oceny."
        
        elements.append(Paragraph(conclusion, self.styles['Normal']))
        
        return elements

    def _create_signature_section(self, session_data: Dict) -> List:
        elements = []
        
        elements.append(Spacer(1, 20*mm))
        
        session = session_data.get('session', {})
        
        signature_data = [
            ["", ""],
            ["_" * 30, "_" * 30],
            ["Wykonawca", "Kierownik laboratorium"],
            [session.get('operator', ''), ""],
        ]
        
        table = Table(signature_data, colWidths=[70*mm, 70*mm])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), FONT_NORMAL),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 5*mm),
        ]))
        elements.append(table)
        
        elements.append(Spacer(1, 10*mm))
        elements.append(Paragraph(
            f"Data wystawienia: {datetime.now().strftime('%Y-%m-%d')}",
            self.styles['Small']
        ))
        
        return elements


def generate_calibration_certificate(session_data: Dict, output_path: str = None) -> str:
    generator = CalibrationReportGenerator()
    return generator.generate_report(session_data, output_path)