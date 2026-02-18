from __future__ import annotations

"""
Refactored PDFReportGenerator for TBDY‑2018 spectrum analysis reports.
Now embeds **Times New Roman** to render Turkish characters correctly.
- Stronger typing (dataclasses)
- Cleaner section builders
- Flexible theming & i18n (tr/en)
- Font embedding (Times New Roman) with graceful fallback
- Testable utilities (pure functions separated)
"""

import io
import os
import logging
from dataclasses import dataclass
import math
from urllib import request, error as urlerror
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from PIL import Image as PILImage
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    BaseDocTemplate,
    PageTemplate,
    Frame,
    NextPageTemplate,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

# Table highlight colors for selected soil class rows
SELECTED_ROW_COLOR = colors.HexColor("#365F91")
SELECTED_ROW_TEXT_COLOR = colors.white
# Global font bump for PDF output
FONT_SIZE_INCREMENT = 1


# ------------------------- Typed containers -------------------------------
@dataclass(frozen=True)
class InputParams:
    lat: Optional[float] = None
    lon: Optional[float] = None
    earthquake_level: str = "DD-2"
    soil_class: Optional[str] = None
    bks: int = 2
    author: str = "Otomatik Rapor"
    logo_path: Optional[str] = None
    locale: str = "tr"  # "tr" or "en"


@dataclass(frozen=True)
class CalculationResults:
    Ss: Optional[float] = None
    S1: Optional[float] = None
    Fs: Optional[float] = None
    F1: Optional[float] = None
    SDS: Optional[float] = None
    SD1: Optional[float] = None
    TL: Optional[float] = None


@dataclass(frozen=True)
class SpectrumSeries:
    T: Sequence[float]
    horizontal: Sequence[float]
    vertical: Sequence[float]


# --------------------------- Utilities -----------------------------------

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_array(x: Any, name: str) -> np.ndarray:
    arr = np.asarray(x, dtype=float)
    if arr.size == 0:
        raise ValueError(f"{name} verisi boş olamaz")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} verisi sayısal ve sonlu olmalı")
    return arr


def _coerce_input_params(input_params: Mapping[str, Any]) -> InputParams:
    """Map/dict girdisini `InputParams` tipine dönüştürür.

    Beklenen anahtarlar (opsiyoneller dahil):
    - lat, lon, earthquake_level, soil_class, bks, author, logo_path, locale
    """
    lat = _safe_float(input_params.get("lat")) if input_params is not None else None
    lon = _safe_float(input_params.get("lon")) if input_params is not None else None
    earthquake_level = (input_params.get("earthquake_level") if input_params else None) or "DD-2"
    soil_class = (input_params.get("soil_class") if input_params else None) or None
    # BKS kimi yerlerde str olabilir
    try:
        bks_raw = input_params.get("bks") if input_params else 2
        bks = int(bks_raw) if bks_raw is not None else 2
    except Exception:
        bks = 2
    author = (input_params.get("author") if input_params else None) or "Otomatik Rapor"
    logo_path = input_params.get("logo_path") if input_params else None
    locale = (input_params.get("locale") if input_params else None) or "tr"

    return InputParams(
        lat=lat,
        lon=lon,
        earthquake_level=str(earthquake_level),
        soil_class=str(soil_class) if soil_class is not None else None,
        bks=bks,
        author=str(author),
        logo_path=str(logo_path) if logo_path else None,
        locale=str(locale),
    )


def _coerce_calc_results(results: Mapping[str, Any]) -> CalculationResults:
    """Map/dict sonuçlarını `CalculationResults` tipine dönüştürür.

    Kullanılabilecek anahtarlar: Ss, S1, Fs, F1, SDS, SD1, TL
    Yoksa None döner; sayılar güvenli şekilde float'a çevrilir.
    """
    if results is None:
        return CalculationResults()

    def gf(key: str) -> Optional[float]:
        val = results.get(key)
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    return CalculationResults(
        Ss=gf("Ss"),
        S1=gf("S1"),
        Fs=gf("Fs"),
        F1=gf("F1"),
        SDS=gf("SDS"),
        SD1=gf("SD1"),
        TL=gf("TL"),
    )


def _coerce_spectrum_table_data(data: Mapping[str, Any]) -> Dict[str, np.ndarray]:
    """Tablo için gerekli T, H, V dizilerini elde eder.

    Kabul edilen formatlar:
    1) {"T": ..., "horizontal": ..., "vertical": ...}
    2) {"dataframe": pd.DataFrame}
    3) {"all_data": pd.DataFrame}

    DataFrame varsa kolon adları esnek eşleşme ile bulunur.
    """
    if data is None:
        raise ValueError("Spektrum verisi bulunamadı")

    # Doğrudan diziler verilmişse
    if "T" in data and "horizontal" in data and "vertical" in data:
        return {
            "T": _coerce_array(data["T"], "T"),
            "horizontal": _coerce_array(data["horizontal"], "horizontal"),
            "vertical": _coerce_array(data["vertical"], "vertical"),
        }

    # DataFrame üzerinden çıkarım
    df = data.get("dataframe") or data.get("all_data")
    if isinstance(df, pd.DataFrame):
        cols = list(df.columns)

        def find_col(candidates: Sequence[str]) -> Optional[str]:
            lc = [c.lower() for c in cols]
            for cand in candidates:
                if cand in cols:
                    return cand
                # esnek arama (lower-case içerir)
                for i, name in enumerate(lc):
                    if cand.lower() in name:
                        return cols[i]
            return None

        t_col = find_col(["Periyot", "Period", "T", "Periyot (s)"])
        h_col = find_col(["Yatay", "Horizontal", "Sae", "Yatay Spektral İvme"])
        v_col = find_col(["Düşey", "Dufey", "Vertical", "Dusey", "Düşey Spektral İvme"])  # çeşitli yazımlara tolerans

        if not (t_col and h_col and v_col):
            raise ValueError("Spektrum veri tablosu kolonları bulunamadı")

        return {
            "T": _coerce_array(df[t_col].to_numpy(), "T"),
            "horizontal": _coerce_array(df[h_col].to_numpy(), "horizontal"),
            "vertical": _coerce_array(df[v_col].to_numpy(), "vertical"),
        }

    raise ValueError("Desteklenmeyen spektrum veri formatı")


# DTS selection table (compact & testable)
_DTS_TABLE: Dict[Tuple[int, str], Tuple[float, float, float]] = {
    # (BKS, locale): thresholds for SDS in ascending order
    (1, "tr"): (0.333, 0.667, 1.000),
    (2, "tr"): (0.333, 0.667, 1.000),
    (3, "tr"): (0.333, 0.667, 1.000),
    (1, "en"): (0.333, 0.667, 1.000),
    (2, "en"): (0.333, 0.667, 1.000),
    (3, "en"): (0.333, 0.667, 1.000),
}

_DTS_LABELS_TR = {
    1: ("DTS=4a", "DTS=3a", "DTS=2a", "DTS=1a"),
    2: ("DTS=4", "DTS=3", "DTS=2", "DTS=1"),
    3: ("DTS=4", "DTS=3", "DTS=2", "DTS=1"),
}

_DTS_LABELS_EN = {
    1: ("DTS=4a", "DTS=3a", "DTS=2a", "DTS=1a"),
    2: ("DTS=4", "DTS=3", "DTS=2", "DTS=1"),
    3: ("DTS=4", "DTS=3", "DTS=2", "DTS=1"),
}

_RISK_TR = {
    "DTS=1a": "Çok yüksek risk",
    "DTS=1": "Yüksek risk",
    "DTS=2a": "Orta‑yüksek risk",
    "DTS=2": "Orta‑yüksek risk",
    "DTS=3a": "Orta risk",
    "DTS=3": "Orta risk",
    "DTS=4a": "Düşük risk",
    "DTS=4": "Düşük risk",
}

_RISK_EN = {
    "DTS=1a": "Very high risk",
    "DTS=1": "High risk",
    "DTS=2a": "Moderate‑high risk",
    "DTS=2": "Moderate‑high risk",
    "DTS=3a": "Moderate risk",
    "DTS=3": "Moderate risk",
    "DTS=4a": "Low risk",
    "DTS=4": "Low risk",
}


def compute_dts(sds: float, bks: int, locale: str = "tr") -> str:
    if bks not in (1, 2, 3):
        return "—"
    thresholds = _DTS_TABLE.get((bks, locale), (0.333, 0.667, 1.000))
    labels = (_DTS_LABELS_TR if locale == "tr" else _DTS_LABELS_EN)[bks]
    t1, t2, t3 = thresholds
    if sds < t1:
        return labels[0]
    if sds < t2:
        return labels[1]
    if sds < t3:
        return labels[2]
    return labels[3]


# ------------------------ Main generator ---------------------------------
class PDFReportGenerator:
    """Generate a TBDY‑2018 spectrum analysis report as PDF.

    Public API remains `generate_report(...) -> bool` for compatibility.
    """

    def __init__(self, *, theme_color=colors.black, zebra=(colors.white, colors.whitesmoke), font_path: Optional[str] = None) -> None:
        # Choose and register Times New Roman
        self._font_name = _register_times_new_roman(font_path)

        # Build styles after font registration so styles pick the right font
        self.styles = getSampleStyleSheet()
        self.theme_color = theme_color
        self.zebra = zebra
        self._setup_custom_styles()
        self._buffers: List[io.BytesIO] = []  # keep binary buffers alive
        self.last_output_path: Optional[str] = None  # actual path written

    # ---------- Public API -------------------------------------------------
    def generate_report(
        self,
        output_path: str,
        spectrum_data: Mapping[str, Any],
        input_params: Mapping[str, Any],
        calculation_results: Mapping[str, Any],
        plot_figure: Optional[plt.Figure] = None,
    ) -> bool:
        """Create the PDF report. Returns True on success."""
        self.last_output_path = None
        try:
            # Normalize inputs
            params = _coerce_input_params(input_params)
            results = _coerce_calc_results(calculation_results)

            # Reset per-report counters
            self._figure_counters = {}
            self._table_counters = {}

            # Hazır yazılabilir bir çıktı yolu seç
            output_path = self._resolve_output_path(output_path)
            self.last_output_path = output_path

            # --- Create document with custom page templates ---
            title_str = (
                "Deprem Yer Hareketi Spektrumları"
                if params.locale == "tr"
                else "Standard Earthquake Motion Spectra"
            )
            subject_str = (
                "Deprem Yer Hareketi Spektrumu"
                if params.locale == "tr"
                else "Earthquake Ground Motion Spectrum"
            )

            doc = BaseDocTemplate(
                output_path,
                pagesize=A4,
                rightMargin=2 * cm,
                leftMargin=2 * cm,
                topMargin=2 * cm,
                bottomMargin=2 * cm,
                title=title_str,
                author=params.author,
                subject=subject_str,
            )
            
            self._doc_width = doc.width

            # Single content frame used in all templates
            frame = Frame(
                doc.leftMargin,
                doc.bottomMargin,
                doc.width,
                doc.height,
                id="normal",
            )

            # Header/footer for non‑cover pages
            def _header_footer(canvas: Canvas, _doc: BaseDocTemplate) -> None:
                canvas.setTitle(title_str)
                canvas.saveState()
                canvas.setLineWidth(0.8)
                canvas.setStrokeColor(self.theme_color)
                # Top horizontal rule
                canvas.line(2 * cm, A4[1] - 2 * cm + 6, A4[0] - 2 * cm, A4[1] - 2 * cm + 6)

                # Date (top‑right)
                try:
                    canvas.setFont(self._font_name, 9 + FONT_SIZE_INCREMENT)
                except Exception:
                    canvas.setFont("Helvetica", 9 + FONT_SIZE_INCREMENT)
                now_tr = datetime.now(ZoneInfo("Europe/Istanbul"))
                date_str = now_tr.strftime("%d/%m/%Y")
                canvas.drawRightString(A4[0] - 2 * cm, A4[1] - 1.4 * cm, date_str)

                # Page number (bottom‑right)
                try:
                    canvas.setFont(self._font_name, 9 + FONT_SIZE_INCREMENT)
                except Exception:
                    canvas.setFont("Helvetica", 9 + FONT_SIZE_INCREMENT)
                canvas.setFillColor(colors.black)
                page_label = (
                    f"Sayfa {canvas.getPageNumber()}"
                    if params.locale == "tr"
                    else f"Page {canvas.getPageNumber()}"
                )
                canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, page_label)
                canvas.restoreState()

            # Cover page has no header or page number
            def _cover_page(canvas: Canvas, _doc: BaseDocTemplate) -> None:
                canvas.setTitle(title_str)
                canvas.saveState()
                try:
                    canvas.setFont(self._font_name, 9 + FONT_SIZE_INCREMENT)
                except Exception:
                    canvas.setFont("Helvetica", 9 + FONT_SIZE_INCREMENT)
                canvas.restoreState()

            cover_template = PageTemplate(id="Cover", frames=[frame], onPage=_cover_page)
            normal_template = PageTemplate(id="Normal", frames=[frame], onPage=_header_footer)
            doc.addPageTemplates([cover_template, normal_template])

            # --- Table of contents / lists of figures & tables ---
            toc = TableOfContents()
            toc.dotsMinLevel = 0  # tüm başlık seviyeleri için noktalı hizalama
            toc.levelStyles = [
                ParagraphStyle(
                    name="TOCLevel1",
                    parent=self.styles["Normal"],
                    fontName=self._font_name,
                    fontSize=10 + FONT_SIZE_INCREMENT,
                    leftIndent=20,
                    firstLineIndent=-10,
                    spaceBefore=2,
                    leading=12 + FONT_SIZE_INCREMENT,
                ),
                ParagraphStyle(
                    name="TOCLevel2",
                    parent=self.styles["Normal"],
                    fontName=self._font_name,
                    fontSize=9 + FONT_SIZE_INCREMENT,
                    leftIndent=36,
                    firstLineIndent=-10,
                    spaceBefore=0,
                    leading=11 + FONT_SIZE_INCREMENT,
                ),
            ]

            lof = TableOfContents()
            lof._notifyKind = "LoFEntry"  # yalnızca elle eklenen şekil girdilerini dinle
            lof.dotsMinLevel = 0
            lof.levelStyles = [
                ParagraphStyle(
                    name="LoFLevel1",
                    parent=self.styles["Normal"],
                    fontName=self._font_name,
                    fontSize=10 + FONT_SIZE_INCREMENT,
                    leftIndent=20,
                    firstLineIndent=-10,
                    spaceBefore=2,
                    leading=12 + FONT_SIZE_INCREMENT,
                )
            ]

            lot = TableOfContents()
            lot._notifyKind = "LoTEntry"  # yalnızca elle eklenen tablo girdilerini dinle
            lot.dotsMinLevel = 0
            lot.levelStyles = [
                ParagraphStyle(
                    name="LoTLevel1",
                    parent=self.styles["Normal"],
                    fontName=self._font_name,
                    fontSize=10 + FONT_SIZE_INCREMENT,
                    leftIndent=20,
                    firstLineIndent=-10,
                    spaceBefore=2,
                    leading=12 + FONT_SIZE_INCREMENT,
                )
            ]

            # Attach to doc so we can fill them in afterFlowable
            doc._toc = toc
            doc._lof = lof
            doc._lot = lot

            def _after_flowable(flowable) -> None:
                from reportlab.platypus import Paragraph as _Paragraph

                if isinstance(flowable, _Paragraph):
                    text = flowable.getPlainText()
                    style_name = flowable.style.name

                    # Headings → TOC
                    level = None
                    if style_name == "Heading1Blue":
                        level = 0
                    elif style_name in ("Heading2Center", "Heading2Green"):
                        level = 1
                    if level is not None:
                        try:
                            current_idx = len(getattr(doc, "_toc", toc)._entries) + 1
                        except Exception:
                            current_idx = doc.page
                        bookmark_name = f"toc-{level + 1}-{current_idx}"
                        try:
                            doc.canv.bookmarkPage(bookmark_name)
                        except Exception:
                            bookmark_name = None
                        doc.notify("TOCEntry", (level, text, doc.page, bookmark_name))

                    # Figure / table captions → LoF / LoT
                    if style_name == "FigureCaption":
                        try:
                            fig_counter = len(getattr(doc, "_lof", lof)._entries) + 1
                        except Exception:
                            fig_counter = doc.page
                        fig_bookmark = f"lof-{fig_counter}"
                        try:
                            doc.canv.bookmarkPage(fig_bookmark)
                        except Exception:
                            fig_bookmark = None
                        doc._lof.addEntry(0, text, doc.page, fig_bookmark)
                    elif style_name == "TableCaption":
                        try:
                            tab_counter = len(getattr(doc, "_lot", lot)._entries) + 1
                        except Exception:
                            tab_counter = doc.page
                        tab_bookmark = f"lot-{tab_counter}"
                        try:
                            doc.canv.bookmarkPage(tab_bookmark)
                        except Exception:
                            tab_bookmark = None
                        doc._lot.addEntry(0, text, doc.page, tab_bookmark)

            doc.afterFlowable = _after_flowable

            # --- Build story ---
            story: List[Any] = []

            # 0. Kapak sayfası
            story.append(NextPageTemplate("Cover"))
            self._add_cover_page(story, params)
            # Sonraki sayfalarda normal şablonu kullan
            story.append(NextPageTemplate("Normal"))
            story.append(PageBreak())

            # İçindekiler
            toc_title = "İçindekiler" if params.locale == "tr" else "Contents"
            story.append(Paragraph(toc_title, self.styles["TOCHeading"]))
            story.append(Spacer(1, 12))
            story.append(toc)
            story.append(PageBreak())

            # 2. Şekil Listesi
            lof_title = "Şekil Listesi" if params.locale == "tr" else "List of Figures"
            story.append(Paragraph(lof_title, self.styles["TOCHeading"]))
            story.append(Spacer(1, 12))
            story.append(lof)
            story.append(PageBreak())

            # 3. Tablo Listesi
            lot_title = "Tablo Listesi" if params.locale == "tr" else "List of Tables"
            story.append(Paragraph(lot_title, self.styles["TOCHeading"]))
            story.append(Spacer(1, 12))
            story.append(lot)
            story.append(PageBreak())

            # 4. Rapor gövdesi (başlık bölümü olmadan doğrudan simgelerle başlar)
            self._add_symbols_section(story, params)
            story.append(PageBreak())

            self._add_hazard_maps_section(story, params)
            self._add_input_parameters_section(story, params)
            story.append(PageBreak())
            self._add_standard_spectra_section(story, results, params)
            self._add_soil_coefficients_section(story, results, params)
            story.append(PageBreak())
            self._add_design_spectra_section(story, results, params)
            self._add_horizontal_elastic_spectrum_section(story, results, params)
            self._add_vertical_elastic_spectrum_section(story, results, params)

            next_section_no = 9

            if plot_figure is not None:
                self._add_spectrum_plots(story, plot_figure, params, next_section_no)
                next_section_no += 1

            if spectrum_data:
                story.append(PageBreak())
                self._add_spectrum_data_table(story, spectrum_data, results, params, next_section_no)
                next_section_no += 1

            self._add_conclusion(story, results, params, next_section_no)
            self._add_footer(story, params)

            # Trailing whitespace flowables can push an empty final page; trim them
            def _trim_trailing_flowables(flowables: List[Any]) -> None:
                removable = (Spacer, HRFlowable, NextPageTemplate)
                while flowables and isinstance(flowables[-1], removable):
                    flowables.pop()
                if flowables and isinstance(flowables[-1], PageBreak):
                    flowables.pop()
                    while flowables and isinstance(flowables[-1], removable):
                        flowables.pop()

            _trim_trailing_flowables(story)

            # Build the document (multiPass to fill TOC/LoF/LoT)
            doc.multiBuild(story)
            logger.info("Rapor başarıyla oluşturuldu → %s", output_path)
            return True
        except PermissionError as perm_err:
            logger.error("PDF için yazma izni yok: %s", perm_err, exc_info=True)
        except IOError as io_err:
            logger.error("Dosya hatası: %s", io_err, exc_info=True)
        except Exception as err:  # noqa: BLE001
            logger.error("Bilinmeyen hata: %s", err, exc_info=True)
        finally:
            self._cleanup_buffers()

        return False

    def _resolve_output_path(self, output_path: str) -> str:
        """Seçilen çıktı yolunu doğrula; gerekirse güvenli bir yedek dizine kaydır."""
        candidates: List[Path] = []
        user_path = Path(output_path).expanduser()
        candidates.append(user_path)

        # Güvenli yedek konum (~/.tbdyspektrum/reports) ve zaman damgalı isim
        safe_dir = Path.home() / ".tbdyspektrum" / "reports"
        timestamp = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y%m%d_%H%M%S")
        fallback_name = user_path.name or f"report_{timestamp}.pdf"
        candidates.append(safe_dir / fallback_name)

        last_err: Optional[BaseException] = None
        for idx, cand in enumerate(candidates):
            try:
                cand.parent.mkdir(parents=True, exist_ok=True)
                # Yazma iznini test et (varsa dosyayı TRUNCATE etmeden)
                with open(cand, "ab"):
                    pass
                if idx > 0:
                    logger.warning("İstenen çıktı yoluna yazılamadı, yedek dizine kaydediliyor: %s", cand)
                return str(cand)
            except PermissionError as e:
                last_err = e
                logger.error("Çıktı dosyası için yazma izni yok: %s", cand)
            except OSError as e:  # diğer IO hataları
                last_err = e
                logger.error("Çıktı dosyası hazırlanamadı: %s", cand)

        # Hiçbir aday yazılamadıysa son hatayı yeniden fırlat
        if last_err:
            raise last_err
        raise PermissionError("Uygun çıktı yolu bulunamadı")
# ---------- Private helpers -------------------------------------------
    def _setup_custom_styles(self) -> None:
        self.styles.add(
            ParagraphStyle(
                name="TitleCenter",
                parent=self.styles["Title"],
                fontSize=18 + FONT_SIZE_INCREMENT,
                spaceAfter=20,
                textColor=self.theme_color,
                alignment=TA_CENTER,
                fontName=self._font_name,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="Heading1Blue",
                parent=self.styles["Heading1"],
                fontSize=14 + FONT_SIZE_INCREMENT,
                spaceAfter=12,
                textColor=self.theme_color,
                fontName=self._font_name,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="Heading2Green",
                parent=self.styles["Heading2"],
                fontSize=12 + FONT_SIZE_INCREMENT,
                spaceAfter=8,
                textColor=colors.black,
                fontName=self._font_name,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="Heading2Center",
                parent=self.styles["Heading2Green"],
                alignment=TA_CENTER,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="Body",
                parent=self.styles["Normal"],
                fontSize=10 + FONT_SIZE_INCREMENT,
                spaceAfter=6,
                alignment=TA_JUSTIFY,
                fontName=self._font_name,
            )
        )
        body_font_size = self.styles["Body"].fontSize
        self.styles.add(
            ParagraphStyle(
                name="BodyWide",
                parent=self.styles["Body"],
                leading=body_font_size + 4,  # extra line spacing for dense inline formulas
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="BodyCenter",
                parent=self.styles["Body"],
                alignment=TA_CENTER,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SymbolLine",
                parent=self.styles["Normal"],
                fontSize=10 + FONT_SIZE_INCREMENT,
                spaceAfter=8,
                alignment=TA_LEFT,
                fontName=self._font_name,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SymbolLineCenter",
                parent=self.styles["SymbolLine"],
                alignment=TA_CENTER,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="TableCell",
                parent=self.styles["Normal"],
                fontSize=9 + FONT_SIZE_INCREMENT,
                alignment=TA_CENTER,
                fontName=self._font_name,
            )
        )

        # Görseller ve tablolar için alt yazı stilleri
        self.styles.add(
            ParagraphStyle(
                name="FigureCaption",
                parent=self.styles["Body"],
                fontSize=9 + FONT_SIZE_INCREMENT,
                alignment=TA_CENTER,
                spaceBefore=4,
                spaceAfter=8,
                fontName=self._font_name,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="TableCaption",
                parent=self.styles["Body"],
                fontSize=9 + FONT_SIZE_INCREMENT,
                alignment=TA_CENTER,
                spaceBefore=4,
                spaceAfter=6,
                fontName=self._font_name,
            )
        )

        # İçindekiler, Şekil Listesi ve Tablo Listesi başlıkları
        self.styles.add(
            ParagraphStyle(
                name="TOCHeading",
                parent=self.styles["Heading1"],
                fontSize=14 + FONT_SIZE_INCREMENT,
                alignment=TA_LEFT,
                spaceBefore=12,
                spaceAfter=12,
                fontName=self._font_name,
            )
        )

    def _default_table_style(self) -> TableStyle:
        return TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, -1), self._font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 9 + FONT_SIZE_INCREMENT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), list(self.zebra)),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ]
        )

    def _table_style_with_padding(self, padding: float = 4.0) -> TableStyle:
        """Return the base table style with extra vertical padding for breathing room."""
        style = self._default_table_style()
        style.add("TOPPADDING", (0, 0), (-1, -1), padding)
        style.add("BOTTOMPADDING", (0, 0), (-1, -1), padding)
        style.add("VALIGN", (0, 0), (-1, -1), "MIDDLE")
        return style

    def _create_fraction(self, num_str: str, den_str: str) -> Table:
        p_num = Paragraph(num_str, self.styles['SymbolLineCenter'])
        p_den = Paragraph(den_str, self.styles['SymbolLineCenter'])
        frac = Table([[p_num], [p_den]], colWidths=[2.8*cm], rowHeights=[0.5*cm, 0.5*cm])
        frac.setStyle(TableStyle([
            ('LINEABOVE', (0,1), (0,1), 0.8, colors.black),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 2),
            ('RIGHTPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        return frac

    
    # -- Caption helpers ----------------------------------------------------
    def _figure_caption(self, section_no: int, text: str, params: InputParams) -> Paragraph:
        """
        Create a numbered figure caption like "Şekil x.y" / "Figure x.y".
        Section number (x) is given by `section_no`; y is incremented per section.
        """
        if not hasattr(self, "_figure_counters"):
            self._figure_counters = {}
        counter = self._figure_counters.get(section_no, 0) + 1
        self._figure_counters[section_no] = counter

        if params.locale == "tr":
            prefix = f"Şekil {section_no}.{counter}. "
        else:
            prefix = f"Figure {section_no}.{counter}. "
        colored_prefix = f'<font color="#c00000"><b>{prefix}</b></font>'
        return Paragraph(colored_prefix + escape(text), self.styles["FigureCaption"])

    def _table_caption(self, section_no: int, text: str, params: InputParams) -> Paragraph:
        """
        Create a numbered table caption like "Tablo x.y" / "Table x.y".
        Section number (x) is given by `section_no`; y is incremented per section.
        """
        if not hasattr(self, "_table_counters"):
            self._table_counters = {}
        counter = self._table_counters.get(section_no, 0) + 1
        self._table_counters[section_no] = counter

        if params.locale == "tr":
            prefix = f"Tablo {section_no}.{counter}. "
        else:
            prefix = f"Table {section_no}.{counter}. "
        colored_prefix = f'<font color="#c00000"><b>{prefix}</b></font>'
        return Paragraph(colored_prefix + escape(text), self.styles["TableCaption"])

    # -- Section builders ---------------------------------------------------

    def _add_cover_page(self, story: List[Any], params: InputParams) -> None:
        """Kapak sayfasını oluşturur."""
        title_main = "Deprem Yer Hareketi Spektrumları" if params.locale == "tr" else "Standard Earthquake Motion Spectra"
        title_sub = (
            "TBDY‑2018 Bölüm 2 kapsamındaki spektrumların hesaplanmasına ilişkin rapor"
            if params.locale == "tr"
            else "Computation report for spectra defined in TBDY‑2018 Section 2"
        )

        story.append(Spacer(1, 5 * cm))
        story.append(Paragraph(title_main, self.styles["TitleCenter"]))

        subtitle_style = ParagraphStyle(
            name="CoverSubtitle",
            parent=self.styles["Normal"],
            fontSize=12 + FONT_SIZE_INCREMENT,
            textColor=self.theme_color,
            alignment=TA_CENTER,
            spaceAfter=30,
            fontName=self._font_name,
        )
        story.append(Paragraph(title_sub, subtitle_style))
        story.append(Spacer(1, 10))

        # Girdi özet tablosu
        today = datetime.now(ZoneInfo("Europe/Istanbul"))
        date_str = today.strftime("%d/%m/%Y")

        meta_rows = [
            [Paragraph("Rapor Tarihi" if params.locale == "tr" else "Report Date", self.styles["TableCell"]),
             Paragraph(date_str, self.styles["TableCell"])],
            [Paragraph("Konum (Enlem, Boylam)" if params.locale == "tr" else "Location (Lat, Lon)", self.styles["TableCell"]),
             Paragraph(f"{params.lat:.6f}, {params.lon:.6f}" if params.lat is not None and params.lon is not None else "—", self.styles["TableCell"])],
            [Paragraph("Deprem Düzeyi" if params.locale == "tr" else "Earthquake Level", self.styles["TableCell"]),
             Paragraph(params.earthquake_level or "—", self.styles["TableCell"])],
            [Paragraph("Zemin Sınıfı" if params.locale == "tr" else "Soil Class", self.styles["TableCell"]),
             Paragraph(params.soil_class or "—", self.styles["TableCell"])],
        ]
        meta_table = Table(meta_rows, colWidths=[6 * cm, 9 * cm], style=self._default_table_style())
        story.append(meta_table)

        story.append(Spacer(1, 30))

        # Logo varsa kapak sayfasında alt kısma ekle
        if params.logo_path:
            try:
                with PILImage.open(params.logo_path) as im:
                    max_w, max_h = 4 * cm, 4 * cm
                    scale = min(max_w / im.width, max_h / im.height)
                    img = Image(params.logo_path, width=im.width * scale, height=im.height * scale)
                    img.hAlign = "CENTER"
                    story.append(img)
            except Exception as e:  # noqa: BLE001
                logger.warning("Logo eklenemedi: %s", e)

        story.append(Spacer(1, 20))

    def _add_header(self, story: List[Any], params: InputParams) -> None:
        title_main = "Deprem Yer Hareketi Spektrumları" if params.locale == "tr" else "Standard Earthquake Motion Spectra"
        title_sub = (
            "TBDY - 2018 Bölüm 2'de bulunan Spektrumların Hesaplama Raporu"
            if params.locale == "tr"
            else "Computation Report for Spectra in TBDY - 2018 Section 2"
        )
        story.append(Paragraph(title_main, self.styles["TitleCenter"]))
        subtitle_style = ParagraphStyle(
            name="SubtitleCenter",
            parent=self.styles["Normal"],
            fontSize=12 + FONT_SIZE_INCREMENT,
            textColor=self.theme_color,
            alignment=TA_CENTER,
            spaceAfter=10,
            fontName=self._font_name,
        )
        story.append(Paragraph(title_sub, subtitle_style))

        # optional logo with safe scaling
        if params.logo_path:
            try:
                with PILImage.open(params.logo_path) as im:
                    max_w, max_h = 3.5 * cm, 3.5 * cm
                    scale = min(max_w / im.width, max_h / im.height)
                    story.append(Image(params.logo_path, width=im.width * scale, height=im.height * scale))
                    story.append(Spacer(1, 6))
            except Exception as e:  # noqa: BLE001
                logger.warning("Logo eklenemedi: %s", e)
        
        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=2, color=self.theme_color))
        story.append(Spacer(1, 20))

    def _add_symbols_section(self, story: List[Any], params: InputParams) -> None:
        story.append(Paragraph("1. Simgeler" if params.locale == "tr" else "1. Symbols", self.styles["Heading1Blue"]))
        
        symbol_line_style = self.styles["SymbolLine"]
        
        symbols_data_tr = [
            ("<i>F</i><sub>s</sub>", "Kısa periyot bölgesi için yerel zemin etki katsayısı"),
            ("<i>F</i><sub>1</sub>", "1.0 saniye periyot için yerel zemin etki katsayısı"),
            ("<i>g</i>", "Yerçekimi ivmesi [g = 9.81 m/s²]"),
            ("<i>S</i><sub>ae</sub>(<i>T</i>)", "Yatay elastik tasarım spektral ivmesi [g]"),
            ("<i>S</i><sub>aD</sub>(<i>T</i>)", "Düşey elastik tasarım spektral ivmesi [g]"),
            ("<i>S</i><sub>de</sub>(<i>T</i>)", "Yatay elastik tasarım spektral yerdeğiştirmesi [m]"),
            ("<i>S</i><sub>DS</sub>", "Kısa periyot tasarım spektral ivme katsayısı [boyutsuz]"),
            ("<i>S</i><sub>D1</sub>", "1.0 saniye periyot için tasarım spektral ivme katsayısı [boyutsuz]"),
            ("<i>S</i><sub>s</sub>", "Kısa periyot harita spektral ivme katsayısı [boyutsuz]"),
            ("<i>S</i><sub>1</sub>", "1.0 saniye periyot için harita spektral ivme katsayısı [boyutsuz]"),
            ("<i>T</i>", "Doğal titreşim periyodu [s]"),
            ("<i>T</i><sub>A</sub>", "Yatay elastik tasarım ivme spektrumu köşe periyodu [s]"),
            ("<i>T</i><sub>AD</sub>", "Düşey elastik tasarım ivme spektrumu köşe periyodu [s]"),
            ("<i>T</i><sub>B</sub>", "Yatay elastik tasarım ivme spektrumu köşe periyodu [s]"),
            ("<i>T</i><sub>BD</sub>", "Düşey elastik tasarım ivme spektrumu köşe periyodu [s]"),
            ("<i>T</i><sub>L</sub>", "Yatay elastik tasarım spektrumunda sabit yerdeğiştirme bölgesine geçiş periyodu [s]"),
            ("<i>T</i><sub>LD</sub>", "Düşey elastik tasarım spektrumunda sabit yerdeğiştirme bölgesine geçiş periyodu [s]"),
            ("<i>T</i><sub>p</sub>", "Binanın hakim doğal titreşim periyodu [s]"),
            ("(<i>V</i><sub>s</sub>)<sub>30</sub>", "Üst 30 metredeki ortalama kayma dalgası hızı [m/s]"),
        ]
        
        for symbol, description in symbols_data_tr:
            line_text = f"{symbol} = {description}"
            story.append(Paragraph(line_text, symbol_line_style))
        
        story.append(Spacer(1, 20))

    def _add_hazard_maps_section(self, story: List[Any], params: InputParams) -> None:
        story.append(Paragraph("2. Deprem Tehlike Haritaları" if params.locale == "tr" else "2. Earthquake Hazard Maps", self.styles["Heading1Blue"]))
        
        body_text_tr = (
            "Binaların deprem etkisi altında tasarımında esas alınacak deprem yer hareketlerine ilişkin veriler bu Bölüm'de tanımlanmıştır. (TBDY-2018, 2.1.1)"
            "<br/><br/>"
            "Dört farklı deprem yer hareketi düzeyi için deprem verileri, 22/01/2018 tarih ve 2018/11275 sayılı Bakanlar Kurulu kararı ile yürürlüğe konulan <i>Türkiye Deprem Tehlike Haritaları</i> ile tanımlanmıştır. "
            'Bu haritalara <a href="https://tdth.afad.gov.tr/" color="blue">https://tdth.afad.gov.tr/</a> adresli internet sitesinden erişilebilir. (TBDY-2018, 2.1.2)'
        )
        story.append(Paragraph(body_text_tr, self.styles["Body"]))
        story.append(Spacer(1, 20))

    def _add_input_parameters_section(self, story: List[Any], params: InputParams) -> None:
        # 3. Girdi Parametreleri
        heading = "3. Girdi Parametreleri" if params.locale == "tr" else "3. Input Parameters"
        story.append(Paragraph(heading, self.styles["Heading1Blue"]))

        intro = (
            "Bu rapor, aşağıda özetlenen konum ve deprem parametreleri kullanılarak oluşturulmuştur."
            if params.locale == "tr"
            else "This report has been generated using the location and earthquake parameters summarised below."
        )
        story.append(Paragraph(intro, self.styles["Body"]))
        story.append(Spacer(1, 10))

        story.append(self._table_caption(
            3,
            "Girdi parametreleri." if params.locale == "tr" else "Input parameters.",
            params,
        ))

        table_data = [
            [
                "Parametre" if params.locale == "tr" else "Parameter",
                "Değer" if params.locale == "tr" else "Value",
            ],
            [
                "Enlem (°)" if params.locale == "tr" else "Latitude (°)",
                f"{params.lat:.5f}" if params.lat is not None else "—",
            ],
            [
                "Boylam (°)" if params.locale == "tr" else "Longitude (°)",
                f"{params.lon:.5f}" if params.lon is not None else "—",
            ],
            [
                "Deprem Yer Hareketi Düzeyi" if params.locale == "tr" else "Earthquake Ground Motion Level",
                params.earthquake_level or "—",
            ],
            [
                "Zemin Sınıfı" if params.locale == "tr" else "Soil Class",
                params.soil_class or "—",
            ],
        ]
        story.append(Table(table_data, colWidths=[8 * cm, 7 * cm], style=self._default_table_style()))
        story.append(Spacer(1, 12))

        # Konum uydu görüntüsü (varsa)
        if params.lat is not None and params.lon is not None:
            try:
                buf, size = _compose_satellite_image(float(params.lat), float(params.lon))
                self._buffers.append(buf)
                with PILImage.open(buf) as pil_img:
                    max_w, max_h = 15 * cm, 9 * cm
                    scale = min(max_w / pil_img.width, max_h / pil_img.height)
                    story.append(Image(buf, width=pil_img.width * scale, height=pil_img.height * scale))
                story.append(Spacer(1, 6))
                caption_text = (
                    "Analiz noktasının uydu görüntüsü."
                    if params.locale == "tr"
                    else "Satellite image of the analysis location."
                )
                story.append(self._figure_caption(3, caption_text, params))
            except Exception as e:  # noqa: BLE001
                logger.warning("Uydu görüntüsü eklenemedi: %s", e)

        story.append(Spacer(1, 20))

    def _add_standard_spectra_section(self, story: List[Any], results: CalculationResults, params: InputParams) -> None:
        story.append(Paragraph("4. Standart Deprem Yer Hareketi Spektrumları", self.styles["Heading1Blue"]))
        
        intro_text = "Deprem yer hareketi spektrumları, belirli bir deprem yer hareketi düzeyi esas alınarak %5 sönüm oranı için, harita spektral ivme katsayıları hesaplanıp ardından spektrumlar oluşturulacaktır."
        story.append(Paragraph(intro_text, self.styles["Body"]))
        story.append(Spacer(1, 12))

        # Ss
        story.append(Paragraph("4.1 Kısa periyot harita spektral ivme katsayısı", self.styles["Heading2Green"]))
        ss_value = f"<i>S</i><sub>s</sub> = {results.Ss:.4f}" if results.Ss is not None else "<i>S</i><sub>s</sub> = —"
        story.append(Paragraph(ss_value, self.styles["SymbolLineCenter"]))
        story.append(Spacer(1, 10))

        # S1
        story.append(Paragraph("4.2 1.0 saniye periyot için harita spektral ivme katsayısı", self.styles["Heading2Green"]))
        s1_value = f"<i>S</i><sub>1</sub> = {results.S1:.4f}" if results.S1 is not None else "<i>S</i><sub>1</sub> = —"
        story.append(Paragraph(s1_value, self.styles["SymbolLineCenter"]))
        story.append(Spacer(1, 20))
        
    def _add_soil_coefficients_section(self, story: List[Any], results: CalculationResults, params: InputParams) -> None:
        story.append(Paragraph("5. Yerel Zemin Etki Katsayıları", self.styles["Heading1Blue"]))
        
        table_cell_style = self.styles["TableCell"]
        body_center_style = self.styles["BodyCenter"]

        # Table 2.1
        story.append(self._table_caption(5, "Kısa periyot bölgesi için Yerel Zemin Etki Katsayıları (TBDY-2018 Tablo 2.1)", params))
        fs_header = [Paragraph(cell, table_cell_style) for cell in ["Yerel Zemin Sınıfı", "<i>S</i><sub>s</sub> ≤ 0.25", "<i>S</i><sub>s</sub> = 0.50", "<i>S</i><sub>s</sub> = 0.75", "<i>S</i><sub>s</sub> = 1.00", "<i>S</i><sub>s</sub> = 1.25", "<i>S</i><sub>s</sub> ≥ 1.50"]]
        fs_data = [
            fs_header,
            ["ZA", "0.8", "0.8", "0.8", "0.8", "0.8", "0.8"],
            ["ZB", "0.9", "0.9", "0.9", "0.9", "0.9", "0.9"],
            ["ZC", "1.3", "1.3", "1.2", "1.2", "1.2", "1.2"],
            ["ZD", "1.6", "1.4", "1.2", "1.1", "1.0", "1.0"],
            ["ZE", "2.4", "1.7", "1.3", "1.1", "0.9", "0.8"],
            ["ZF", Paragraph("Sahaya özel zemin davranış analizi yapılacaktır (Bkz.16.5).", body_center_style), "", "", "", "", ""]
        ]
        fs_table = Table(fs_data, colWidths=[2.5*cm] * 7)
        fs_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('TEXTCOLOR',(0,0),(-1,0),colors.black),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTNAME', (0,0), (-1,-1), self._font_name),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('SPAN', (1, 6), (-1, 6))
        ]))
        # Seçilen zemin sınıfı satırını vurgula
        soil = (params.soil_class or "").strip().upper()
        soil_row = {"ZA": 1, "ZB": 2, "ZC": 3, "ZD": 4, "ZE": 5, "ZF": 6}.get(soil)
        if soil_row is not None:
            fs_table.setStyle(TableStyle([
                ('BACKGROUND', (0, soil_row), (-1, soil_row), SELECTED_ROW_COLOR),
                ('TEXTCOLOR', (0, soil_row), (-1, soil_row), SELECTED_ROW_TEXT_COLOR),
            ]))
        story.append(fs_table)
        story.append(Spacer(1, 12))

        # Table 2.2
        # Table 2.2
        story.append(self._table_caption(5, "1.0 saniye periyot için Yerel Zemin Etki Katsayıları (TBDY-2018 Tablo 2.2)", params))
        f1_header = [Paragraph(cell, table_cell_style) for cell in [
            "Yerel Zemin Sınıfı",
            "<i>S</i><sub>1</sub> ≤ 0.10",
            "<i>S</i><sub>1</sub> = 0.20",
            "<i>S</i><sub>1</sub> = 0.30",
            "<i>S</i><sub>1</sub> = 0.40",
            "<i>S</i><sub>1</sub> = 0.50",
            "<i>S</i><sub>1</sub> ≥ 0.60",
        ]]
        f1_data = [
            f1_header,
            ["ZA", "0.8", "0.8", "0.8", "0.8", "0.8", "0.8"],
            ["ZB", "0.8", "0.8", "0.8", "0.8", "0.8", "0.8"],
            ["ZC", "1.5", "1.5", "1.5", "1.5", "1.5", "1.4"],
            ["ZD", "2.4", "2.2", "2.0", "1.9", "1.8", "1.7"],
            ["ZE", "4.2", "3.3", "2.8", "2.4", "2.2", "2.0"],
            ["ZF", Paragraph("Sahaya özel zemin davranış analizi yapılacaktır (Bkz.16.5).", body_center_style), "", "", "", "", ""]
        ]
        f1_table = Table(f1_data, colWidths=[2.5*cm] * 7)
        f1_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('TEXTCOLOR',(0,0),(-1,0),colors.black),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTNAME', (0,0), (-1,-1), self._font_name),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('SPAN', (1, 6), (-1, 6))
        ]))
        # Seçilen zemin sınıfı satırını vurgula
        soil = (params.soil_class or "").strip().upper()
        soil_row = {"ZA": 1, "ZB": 2, "ZC": 3, "ZD": 4, "ZE": 5, "ZF": 6}.get(soil)
        if soil_row is not None:
            f1_table.setStyle(TableStyle([
                ('BACKGROUND', (0, soil_row), (-1, soil_row), SELECTED_ROW_COLOR),
                ('TEXTCOLOR', (0, soil_row), (-1, soil_row), SELECTED_ROW_TEXT_COLOR),
            ]))
        story.append(f1_table)
        story.append(Spacer(1, 12))

        fs_value = f"<i>F</i><sub>s</sub> = {results.Fs:.2f}" if results.Fs is not None else "<i>F</i><sub>s</sub> = —"
        story.append(Paragraph(fs_value, self.styles["SymbolLineCenter"]))
        f1_value = f"<i>F</i><sub>1</sub> = {results.F1:.2f}" if results.F1 is not None else "<i>F</i><sub>1</sub> = —"
        story.append(Paragraph(f1_value, self.styles["SymbolLineCenter"]))
        story.append(Spacer(1, 20))

    def _add_design_spectra_section(self, story: List[Any], results: CalculationResults, params: InputParams) -> None:
        story.append(Paragraph("6. Tasarım Spektral İvme Katsayıları", self.styles["Heading1Blue"]))
        
        # SDS
        sds_formula = f"<i>S</i><sub>DS</sub> = <i>S</i><sub>s</sub> × <i>F</i><sub>s</sub> = {results.Ss:.4f} × {results.Fs:.2f} = {results.SDS:.4f}" if all(v is not None for v in [results.Ss, results.Fs, results.SDS]) else "<i>S</i><sub>DS</sub> = —"
        story.append(Paragraph(sds_formula, self.styles["SymbolLineCenter"]))
        story.append(Spacer(1, 10))

        # SD1
        sd1_formula = f"<i>S</i><sub>D1</sub> = <i>S</i><sub>1</sub> × <i>F</i><sub>1</sub> = {results.S1:.4f} × {results.F1:.2f} = {results.SD1:.4f}" if all(v is not None for v in [results.S1, results.F1, results.SD1]) else "<i>S</i><sub>D1</sub> = —"
        story.append(Paragraph(sd1_formula, self.styles["SymbolLineCenter"]))
        story.append(Spacer(1, 20))

    # def _add_horizontal_elastic_spectrum_section(self, story: List[Any], results: CalculationResults, params: InputParams) -> None:
    #     story.append(Paragraph("7. Yatay Elastik Tasarım Spektrumu", self.styles["Heading1Blue"]))
        
    #     intro_text = "Gözönüne alınan herhangi bir deprem yer hareketi düzeyi için <i>yatay elastik tasarım ivme spektrumu</i>'nun ordinatları olan <i>yatay elastik tasarım spektral ivmeleri</i>, doğal titreşim periyoduna bağlı olarak yerçekimi ivmesi [<i>g</i>] cinsinden tanımlanmıştır."
    #     story.append(Paragraph(intro_text, self.styles["Body"]))
    #     story.append(Spacer(1, 15))

    #     # --- Sae(T) Formülleri ---
    #     formula_style = self.styles["SymbolLineCenter"]
        
    #     # Formülleri tek tablo halinde düzenli hizala
    #     formula_data = [
    #         [Paragraph('<i>S</i><sub>ae</sub>(<i>T</i>) = (0.4 + 0.6 × <i>T</i>/<i>T</i><sub>A</sub>) × <i>S</i><sub>DS</sub>', formula_style), 
    #          Paragraph('(0 ≤ <i>T</i> ≤ <i>T</i><sub>A</sub>)', formula_style)],
    #         [Paragraph('<i>S</i><sub>ae</sub>(<i>T</i>) = <i>S</i><sub>DS</sub>', formula_style), 
    #          Paragraph('(<i>T</i><sub>A</sub> ≤ <i>T</i> ≤ <i>T</i><sub>B</sub>)', formula_style)],
    #         [Paragraph('<i>S</i><sub>ae</sub>(<i>T</i>) = <i>S</i><sub>D1</sub>/<i>T</i>', formula_style), 
    #          Paragraph('(<i>T</i><sub>B</sub> ≤ <i>T</i> ≤ <i>T</i><sub>L</sub>)', formula_style)],
    #         [Paragraph('<i>S</i><sub>ae</sub>(<i>T</i>) = <i>S</i><sub>D1</sub> × <i>T</i><sub>L</sub>/<i>T</i><sup>2</sup>', formula_style), 
    #          Paragraph('(<i>T</i><sub>L</sub> ≤ <i>T</i>)', formula_style)]
    #     ]
        
    #     formula_table = Table(formula_data, colWidths=[10*cm, 5*cm], hAlign='CENTER')
    #     formula_table.setStyle(TableStyle([
    #         ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    #         ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    #         ('LEFTPADDING', (0,0), (-1,-1), 8),
    #         ('RIGHTPADDING', (0,0), (-1,-1), 8),
    #         ('TOPPADDING', (0,0), (-1,-1), 6),
    #         ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    #         ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.white]),
    #     ]))
    #     story.append(formula_table)
    #     story.append(Spacer(1, 15))

    #     # --- TA, TB ve TL Hesaplamaları ---
    #     if results.SD1 is not None and results.SDS is not None and results.SDS > 0:
    #         TA = 0.2 * (results.SD1 / results.SDS)
    #         TB = results.SD1 / results.SDS
            
    #         # Hesaplamaları tek satırda göster
    #         story.append(Paragraph(f'<i>T</i><sub>A</sub> = 0.2 × {results.SD1:.4f}/{results.SDS:.4f} = {TA:.4f} s', formula_style))
    #         story.append(Spacer(1, 6))
    #         story.append(Paragraph(f'<i>T</i><sub>B</sub> = {results.SD1:.4f}/{results.SDS:.4f} = {TB:.4f} s', formula_style))
    #         story.append(Spacer(1, 6))
    #         story.append(Paragraph('<i>T</i><sub>L</sub> = 6 s', formula_style))
    #     else:
    #         # Hesaplanamadığında basit gösterim
    #         story.append(Paragraph('<i>T</i><sub>A</sub> = —', formula_style))
    #         story.append(Spacer(1, 6))
    #         story.append(Paragraph('<i>T</i><sub>B</sub> = —', formula_style))
    #         story.append(Spacer(1, 6))
    #         story.append(Paragraph('<i>T</i><sub>L</sub> = 6 s', formula_style))
    #     story.append(Spacer(1, 15))
        
    #     # Yatay elastik tasarım spektrumu grafiği ekle
    #     try:
    #         graph_path = "report_images/yatay_elastik_tasarim_spektrumu_grafik.png"
    #         if os.path.exists(graph_path):
    #             with PILImage.open(graph_path) as pil_img:
    #                 max_w, max_h = 14 * cm, 10 * cm
    #                 scale = min(max_w / pil_img.width, max_h / pil_img.height)
    #                 story.append(Image(graph_path, width=pil_img.width * scale, height=pil_img.height * scale))
    #                 story.append(Spacer(1, 6))
    #                 caption_text = (
    #                     "TBDY‑2018’e göre yatay elastik tasarım ivme spektrumunun gösterimi "
    #                     "(T: periyot [s], Sₐₑ(T): spektral ivme [g])."
    #                     if params.locale == "tr"
    #                     else "Schematic shape of the horizontal elastic design acceleration spectrum "
    #                     "(T: period [s], Sae(T): spectral acceleration [g])."
    #                 )
    #                 story.append(self._figure_caption(7, caption_text, params))
    #                 story.append(Spacer(1, 10))
    #     except Exception as e:  # noqa: BLE001
    #         logger.warning("Spektrum grafiği eklenemedi: %s", e)
        
    #     # Dinamik yatay elastik tasarım spektrumu grafiği oluştur ve ekle
    #     if results.SDS is not None and results.SD1 is not None:
    #         try:
    #             dynamic_graph_buf = self._create_horizontal_spectrum_plot(results)
    #             if dynamic_graph_buf:
    #                 self._buffers.append(dynamic_graph_buf)
    #                 with PILImage.open(dynamic_graph_buf) as pil_img:
    #                     max_w, max_h = 14 * cm, 10 * cm
    #                     scale = min(max_w / pil_img.width, max_h / pil_img.height)
    #                     story.append(Image(dynamic_graph_buf, width=pil_img.width * scale, height=pil_img.height * scale))
    #                     story.append(Spacer(1, 6))
    #                     caption_text = (
    #                         "Hesaplanan yatay elastik tasarım ivme spektrumu "
    #                         "(T: periyot [s], Sₐₑ(T): spektral ivme [g])."
    #                         if params.locale == "tr"
    #                         else "Computed horizontal elastic design acceleration spectrum "
    #                         "(T: period [s], Sae(T): spectral acceleration [g])."
    #                     )
    #                     story.append(self._figure_caption(7, caption_text, params))
    #                     story.append(Spacer(1, 10))
    #         except Exception as e:  # noqa: BLE001
    #             logger.warning("Dinamik spektrum grafiği oluşturulamadı: %s", e)
        
    #     # Yatay elastik tasarım yerdeğiştirme spektrumu açıklaması
    #     story.append(Spacer(1, 15))
    #     displacement_text = "Gözönüne alınan herhangi bir deprem yer hareketi düzeyi için <i>yatay elastik tasarım yerdeğiştirme spektrumu</i>'nun ordinatları olan yatay elastik tasarım spektral yerdeğiştirmeleri, doğal titreşim periyoduna bağlı olarak metre [m] cinsinden hesaplanır."
    #     story.append(Paragraph(displacement_text, self.styles["Body"]))
    #     story.append(Spacer(1, 12))
        
    #     # Yerdeğiştirme spektrumu formülü
    #     displacement_formula = '<i>S</i><sub>de</sub>(<i>T</i>) = <i>T</i><sup>2</sup>/(4π<sup>2</sup>) × <i>g</i> × <i>S</i><sub>ae</sub>(<i>T</i>)'
    #     story.append(Paragraph(displacement_formula, self.styles["SymbolLineCenter"]))
    #     story.append(Spacer(1, 15))
        
    #     # Yatay elastik yerdeğiştirme tasarım spektrumu statik grafiği ekle
    #     try:
    #         displacement_graph_path = "report_images/yatay_elastik__yerdegistirme_tasarim_spektrumu_grafik.png"
    #         if os.path.exists(displacement_graph_path):
    #             with PILImage.open(displacement_graph_path) as pil_img:
    #                 max_w, max_h = 14 * cm, 10 * cm
    #                 scale = min(max_w / pil_img.width, max_h / pil_img.height)
    #                 story.append(Image(displacement_graph_path, width=pil_img.width * scale, height=pil_img.height * scale))
    #                 story.append(Spacer(1, 10))
    #     except Exception as e:  # noqa: BLE001
    #         logger.warning("Yerdeğiştirme spektrumu grafiği eklenemedi: %s", e)
        
    #     # Dinamik yatay elastik yerdeğiştirme spektrumu grafiği oluştur ve ekle
    #     if results.SDS is not None and results.SD1 is not None:
    #         try:
    #             dynamic_displacement_buf = self._create_displacement_spectrum_plot(results)
    #             if dynamic_displacement_buf:
    #                 self._buffers.append(dynamic_displacement_buf)
    #                 with PILImage.open(dynamic_displacement_buf) as pil_img:
    #                     max_w, max_h = 14 * cm, 10 * cm
    #                     scale = min(max_w / pil_img.width, max_h / pil_img.height)
    #                     story.append(Image(dynamic_displacement_buf, width=pil_img.width * scale, height=pil_img.height * scale))
    #                     story.append(Spacer(1, 6))
    #                     caption_text = (
    #                         "Hesaplanan yatay elastik tasarım yerdeğiştirme spektrumu "
    #                         "(T: periyot [s], S<sub>de</sub>(T): spektral yerdeğiştirme [m])."
    #                         if params.locale == "tr"
    #                         else "Computed horizontal elastic design displacement spectrum "
    #                         "(T: period [s], Sde(T): spectral displacement [m])."
    #                     )
    #                     story.append(self._figure_caption(7, caption_text, params))
    #                     story.append(Spacer(1, 10))
    #         except Exception as e:  # noqa: BLE001
    #             logger.warning("Dinamik yerdeğiştirme spektrumu grafiği oluşturulamadı: %s", e)
            
    #     story.append(Spacer(1, 20))
    
    def _add_horizontal_elastic_spectrum_section(self, story: List[Any], results: CalculationResults, params: InputParams) -> None:
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
        from reportlab.lib.styles import ParagraphStyle

        story.append(Paragraph("7. Yatay Elastik Tasarım Spektrumu", self.styles["Heading1Blue"]))

        intro_text = (
            "Gözönüne alınan herhangi bir deprem yer hareketi düzeyi için "
            "<i>yatay elastik tasarım ivme spektrumu</i>'nun ordinatları olan "
            "<i>yatay elastik tasarım spektral ivmeleri</i>, doğal titreşim periyoduna bağlı olarak "
            "yerçekimi ivmesi [<i>g</i>] cinsinden tanımlanmıştır."
        )
        story.append(Paragraph(intro_text, self.styles["Body"]))
        story.append(Spacer(1, 15))

        # --- Sae(T) Formülleri (DÜZGÜN HİZALI) ---
        base_style = self.styles["SymbolLineCenter"]  # font/size aynen kalsın

        formula_left = ParagraphStyle(
            name="FormulaLeft",
            parent=base_style,
            alignment=TA_LEFT,
        )
        formula_right = ParagraphStyle(
            name="FormulaRight",
            parent=base_style,
            alignment=TA_RIGHT,
        )

        # doc.width'ü generate_report'ta self._doc_width olarak set etmiştik
        doc_w = getattr(self, "_doc_width", 15 * cm)
        left_w = doc_w * 0.82
        right_w = doc_w * 0.18

        formula_data = [
            [
                Paragraph(
                    '<i>S</i><sub>ae</sub>(<i>T</i>) = (0.4 + 0.6 × <i>T</i>/<i>T</i><sub>A</sub>) × <i>S</i><sub>DS</sub>',
                    formula_left,
                ),
                Paragraph('(0 ≤ <i>T</i> ≤ <i>T</i><sub>A</sub>)', formula_right),
            ],
            [
                Paragraph('<i>S</i><sub>ae</sub>(<i>T</i>) = <i>S</i><sub>DS</sub>', formula_left),
                Paragraph('(<i>T</i><sub>A</sub> ≤ <i>T</i> ≤ <i>T</i><sub>B</sub>)', formula_right),
            ],
            [
                Paragraph('<i>S</i><sub>ae</sub>(<i>T</i>) = <i>S</i><sub>D1</sub>/<i>T</i>', formula_left),
                Paragraph('(<i>T</i><sub>B</sub> ≤ <i>T</i> ≤ <i>T</i><sub>L</sub>)', formula_right),
            ],
            [
                Paragraph(
                    '<i>S</i><sub>ae</sub>(<i>T</i>) = <i>S</i><sub>D1</sub> × <i>T</i><sub>L</sub>/<i>T</i><sup>2</sup>',
                    formula_left,
                ),
                Paragraph('(<i>T</i><sub>L</sub> ≤ <i>T</i>)', formula_right),
            ],
        ]

        formula_table = Table(formula_data, colWidths=[left_w, right_w], hAlign="CENTER")
        formula_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white]),
        ]))
        story.append(formula_table)
        story.append(Spacer(1, 12))

        # --- TA, TB ve TL Hesaplamaları (DÜZGÜN BLOK) ---
        calc_center = ParagraphStyle(
            name="CalcCenter",
            parent=base_style,
            alignment=TA_CENTER,
        )

        if results.SD1 is not None and results.SDS is not None and results.SDS > 0:
            TA = 0.2 * (results.SD1 / results.SDS)
            TB = results.SD1 / results.SDS

            calc_rows = [
                [Paragraph(f'<i>T</i><sub>A</sub> = 0.2 × {results.SD1:.4f}/{results.SDS:.4f} = {TA:.4f} s', calc_center)],
                [Paragraph(f'<i>T</i><sub>B</sub> = {results.SD1:.4f}/{results.SDS:.4f} = {TB:.4f} s', calc_center)],
                [Paragraph('<i>T</i><sub>L</sub> = 6 s', calc_center)],
            ]
        else:
            calc_rows = [
                [Paragraph('<i>T</i><sub>A</sub> = —', calc_center)],
                [Paragraph('<i>T</i><sub>B</sub> = —', calc_center)],
                [Paragraph('<i>T</i><sub>L</sub> = 6 s', calc_center)],
            ]

        calc_table = Table(calc_rows, colWidths=[doc_w], hAlign="CENTER")
        calc_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(calc_table)
        story.append(Spacer(1, 15))

        # Yatay elastik tasarım spektrumu grafiği ekle
        try:
            graph_path = "report_images/yatay_elastik_tasarim_spektrumu_grafik.png"
            if os.path.exists(graph_path):
                with PILImage.open(graph_path) as pil_img:
                    max_w, max_h = 14 * cm, 10 * cm
                    scale = min(max_w / pil_img.width, max_h / pil_img.height)
                    story.append(Image(graph_path, width=pil_img.width * scale, height=pil_img.height * scale))
                    story.append(Spacer(1, 6))
                    caption_text = (
                        "TBDY-2018’e göre yatay elastik tasarım ivme spektrumunun gösterimi "
                        "(T: periyot [s], Sₐₑ(T): spektral ivme [g])."
                        if params.locale == "tr"
                        else "Schematic shape of the horizontal elastic design acceleration spectrum "
                        "(T: period [s], Sae(T): spectral acceleration [g])."
                    )
                    story.append(self._figure_caption(7, caption_text, params))
                    story.append(Spacer(1, 10))
        except Exception as e:  # noqa: BLE001
            logger.warning("Spektrum grafiği eklenemedi: %s", e)

        # Dinamik yatay elastik tasarım spektrumu grafiği oluştur ve ekle
        if results.SDS is not None and results.SD1 is not None:
            try:
                dynamic_graph_buf = self._create_horizontal_spectrum_plot(results)
                if dynamic_graph_buf:
                    self._buffers.append(dynamic_graph_buf)
                    with PILImage.open(dynamic_graph_buf) as pil_img:
                        max_w, max_h = 14 * cm, 10 * cm
                        scale = min(max_w / pil_img.width, max_h / pil_img.height)
                        story.append(Image(dynamic_graph_buf, width=pil_img.width * scale, height=pil_img.height * scale))
                        story.append(Spacer(1, 6))
                        caption_text = (
                            "Hesaplanan yatay elastik tasarım ivme spektrumu "
                            "(T: periyot [s], Sₐₑ(T): spektral ivme [g])."
                            if params.locale == "tr"
                            else "Computed horizontal elastic design acceleration spectrum "
                            "(T: period [s], Sae(T): spectral acceleration [g])."
                        )
                        story.append(self._figure_caption(7, caption_text, params))
                        story.append(Spacer(1, 10))
            except Exception as e:  # noqa: BLE001
                logger.warning("Dinamik spektrum grafiği oluşturulamadı: %s", e)

        # Yatay elastik tasarım yerdeğiştirme spektrumu açıklaması
        story.append(Spacer(1, 15))
        displacement_text = (
            "Gözönüne alınan herhangi bir deprem yer hareketi düzeyi için "
            "<i>yatay elastik tasarım yerdeğiştirme spektrumu</i>'nun ordinatları olan "
            "yatay elastik tasarım spektral yerdeğiştirmeleri, doğal titreşim periyoduna bağlı olarak "
            "metre [m] cinsinden hesaplanır."
        )
        story.append(Paragraph(displacement_text, self.styles["Body"]))
        story.append(Spacer(1, 12))

        # Yerdeğiştirme spektrumu formülü
        displacement_formula = (
            '<i>S</i><sub>de</sub>(<i>T</i>) = <i>T</i><sup>2</sup>/(4π<sup>2</sup>) × <i>g</i> × '
            '<i>S</i><sub>ae</sub>(<i>T</i>)'
        )
        story.append(Paragraph(displacement_formula, self.styles["SymbolLineCenter"]))
        story.append(Spacer(1, 15))

        # Yatay elastik yerdeğiştirme tasarım spektrumu statik grafiği ekle
        try:
            displacement_graph_path = "report_images/yatay_elastik__yerdegistirme_tasarim_spektrumu_grafik.png"
            if os.path.exists(displacement_graph_path):
                with PILImage.open(displacement_graph_path) as pil_img:
                    max_w, max_h = 14 * cm, 10 * cm
                    scale = min(max_w / pil_img.width, max_h / pil_img.height)
                    story.append(Image(displacement_graph_path, width=pil_img.width * scale, height=pil_img.height * scale))
                    story.append(Spacer(1, 10))
        except Exception as e:  # noqa: BLE001
            logger.warning("Yerdeğiştirme spektrumu grafiği eklenemedi: %s", e)

        # Dinamik yatay elastik yerdeğiştirme spektrumu grafiği oluştur ve ekle
        if results.SDS is not None and results.SD1 is not None:
            try:
                dynamic_displacement_buf = self._create_displacement_spectrum_plot(results)
                if dynamic_displacement_buf:
                    self._buffers.append(dynamic_displacement_buf)
                    with PILImage.open(dynamic_displacement_buf) as pil_img:
                        max_w, max_h = 14 * cm, 10 * cm
                        scale = min(max_w / pil_img.width, max_h / pil_img.height)
                        story.append(Image(dynamic_displacement_buf, width=pil_img.width * scale, height=pil_img.height * scale))
                        story.append(Spacer(1, 6))
                        caption_text = (
                            "Hesaplanan yatay elastik tasarım yerdeğiştirme spektrumu "
                            "(T: periyot [s], S<sub>de</sub>(T): spektral yerdeğiştirme [m])."
                            if params.locale == "tr"
                            else "Computed horizontal elastic design displacement spectrum "
                            "(T: period [s], Sde(T): spectral displacement [m])."
                        )
                        story.append(self._figure_caption(7, caption_text, params))
                        story.append(Spacer(1, 10))
            except Exception as e:  # noqa: BLE001
                logger.warning("Dinamik yerdeğiştirme spektrumu grafiği oluşturulamadı: %s", e)

        story.append(Spacer(1, 20))


    # def _add_vertical_elastic_spectrum_section(self, story: List[Any], results: CalculationResults, params: InputParams) -> None:
    #     story.append(Paragraph("8. Düşey Elastik Tasarım Spektrumu", self.styles["Heading1Blue"]))
        
    #     intro_text = "Gözönüne alınan herhangi bir deprem yer hareketi düzeyi için <i>düşey elastik tasarım ivme spektrumu</i>'nun ordinatları olan düşey elastik tasarım spektral ivmeleri, yatay deprem yer hareketi için tanımlanan kısa periyot tasarım spektral ivme katsayısına ve doğal titreşim periyoduna bağlı olarak yerçekimi ivmesi [g] cinsinden tanımlanır."
    #     story.append(Paragraph(intro_text, self.styles["Body"]))
    #     story.append(Spacer(1, 15))

    #     # --- SaeD(T) Formülleri ---
    #     formula_style = self.styles["SymbolLineCenter"]
        
    #     # Formülleri tek tablo halinde düzenli hizala
    #     formula_data = [
    #         [Paragraph('<i>S</i><sub>aeD</sub>(<i>T</i>) = (0.4 + 0.6 × <i>T</i>/<i>T</i><sub>AD</sub>) × <i>S</i><sub>DS</sub>', formula_style), 
    #          Paragraph('(0 ≤ <i>T</i> ≤ <i>T</i><sub>AD</sub>)', formula_style)],
    #         [Paragraph('<i>S</i><sub>aeD</sub>(<i>T</i>) = <i>S</i><sub>DS</sub>', formula_style), 
    #          Paragraph('(<i>T</i><sub>AD</sub> ≤ <i>T</i> ≤ <i>T</i><sub>BD</sub>)', formula_style)],
    #         [Paragraph('<i>S</i><sub>aeD</sub>(<i>T</i>) = <i>S</i><sub>D1</sub>/<i>T</i>', formula_style), 
    #          Paragraph('(<i>T</i><sub>BD</sub> ≤ <i>T</i> ≤ <i>T</i><sub>LD</sub>)', formula_style)],
    #         [Paragraph('<i>S</i><sub>aeD</sub>(<i>T</i>) = <i>S</i><sub>D1</sub> × <i>T</i><sub>LD</sub>/<i>T</i><sup>2</sup>', formula_style), 
    #          Paragraph('(<i>T</i><sub>LD</sub> ≤ <i>T</i>)', formula_style)]
    #     ]
        
    #     formula_table = Table(formula_data, colWidths=[10*cm, 5*cm], hAlign='CENTER')
    #     formula_table.setStyle(TableStyle([
    #         ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    #         ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    #         ('LEFTPADDING', (0,0), (-1,-1), 8),
    #         ('RIGHTPADDING', (0,0), (-1,-1), 8),
    #         ('TOPPADDING', (0,0), (-1,-1), 6),
    #         ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    #         ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.white]),
    #     ]))
    #     story.append(formula_table)
    #     story.append(Spacer(1, 15))

    #     # --- TAD, TBD ve TLD Hesaplamaları ---
    #     if results.SD1 is not None and results.SDS is not None and results.SDS > 0:
    #         TA = 0.2 * (results.SD1 / results.SDS)
    #         TB = results.SD1 / results.SDS
    #         TL = 6.0  # Default TL value
            
    #         TAD = TA / 3
    #         TBD = TB / 3
    #         TLD = TL / 2
            
    #         # Hesaplamaları göster
    #         story.append(Paragraph(f'<i>T</i><sub>AD</sub> = <i>T</i><sub>A</sub>/3 = {TA:.4f}/3 = {TAD:.4f} s', formula_style))
    #         story.append(Spacer(1, 6))
    #         story.append(Paragraph(f'<i>T</i><sub>BD</sub> = <i>T</i><sub>B</sub>/3 = {TB:.4f}/3 = {TBD:.4f} s', formula_style))
    #         story.append(Spacer(1, 6))
    #         story.append(Paragraph(f'<i>T</i><sub>LD</sub> = <i>T</i><sub>L</sub>/2 = {TL:.1f}/2 = {TLD:.1f} s', formula_style))
    #     else:
    #         # Hesaplanamadığında basit gösterim
    #         story.append(Paragraph('<i>T</i><sub>AD</sub> = —', formula_style))
    #         story.append(Spacer(1, 6))
    #         story.append(Paragraph('<i>T</i><sub>BD</sub> = —', formula_style))
    #         story.append(Spacer(1, 6))
    #         story.append(Paragraph('<i>T</i><sub>LD</sub> = 3 s', formula_style))
        
    #     # Düşey elastik tasarım spektrumu grafiği ekle
    #     try:
    #         graph_path = "report_images/dusey_elastik_tasarim_spektrumu.png"
    #         if os.path.exists(graph_path):
    #             with PILImage.open(graph_path) as pil_img:
    #                 max_w, max_h = 14 * cm, 10 * cm
    #                 scale = min(max_w / pil_img.width, max_h / pil_img.height)
    #                 story.append(Image(graph_path, width=pil_img.width * scale, height=pil_img.height * scale))
    #                 story.append(Spacer(1, 6))
    #                 caption_text = (
    #                     "TBDY‑2018’e göre düşey elastik tasarım ivme spektrumunun gösterimi "
    #                     "(T: periyot [s], Sₐᵥ(T): spektral ivme [g])."
    #                     if params.locale == "tr"
    #                     else "Schematic shape of the vertical elastic design acceleration spectrum "
    #                     "(T: period [s], Sav(T): spectral acceleration [g])."
    #                 )
    #                 story.append(self._figure_caption(8, caption_text, params))
    #                 story.append(Spacer(1, 10))
    #     except Exception as e:  # noqa: BLE001
    #         logger.warning("Düşey spektrum grafiği eklenemedi: %s", e)

    #     # Dinamik düşey elastik tasarım spektrumu grafiği oluştur ve ekle
    #     if results.SDS is not None and results.SD1 is not None:
    #         try:
    #             dynamic_vertical_buf = self._create_vertical_spectrum_plot(results)
    #             if dynamic_vertical_buf:
    #                 self._buffers.append(dynamic_vertical_buf)
    #                 with PILImage.open(dynamic_vertical_buf) as pil_img:
    #                     max_w, max_h = 14 * cm, 10 * cm
    #                     scale = min(max_w / pil_img.width, max_h / pil_img.height)
    #                     story.append(Image(dynamic_vertical_buf, width=pil_img.width * scale, height=pil_img.height * scale))
    #                     story.append(Spacer(1, 6))
    #                     caption_text = (
    #                         "Hesaplanan düşey elastik tasarım ivme spektrumu "
    #                         "(T: periyot [s], Sₐᵥ(T): spektral ivme [g])."
    #                         if params.locale == "tr"
    #                         else "Computed vertical elastic design acceleration spectrum "
    #                         "(T: period [s], Sav(T): spectral acceleration [g])."
    #                     )
    #                     story.append(self._figure_caption(8, caption_text, params))
    #                     story.append(Spacer(1, 10))
    #         except Exception as e:  # noqa: BLE001
    #             logger.warning("Dinamik düşey spektrum grafiği oluşturulamadı: %s", e)
        
    #     story.append(Spacer(1, 20))
    
    
    def _add_vertical_elastic_spectrum_section(self, story: List[Any], results: CalculationResults, params: InputParams) -> None:
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
        from reportlab.lib.styles import ParagraphStyle

        story.append(Paragraph("8. Düşey Elastik Tasarım Spektrumu", self.styles["Heading1Blue"]))

        intro_text = (
            "Gözönüne alınan herhangi bir deprem yer hareketi düzeyi için "
            "<i>düşey elastik tasarım ivme spektrumu</i>'nun ordinatları olan düşey elastik tasarım spektral ivmeleri, "
            "yatay deprem yer hareketi için tanımlanan kısa periyot tasarım spektral ivme katsayısına ve doğal titreşim "
            "periyoduna bağlı olarak yerçekimi ivmesi [g] cinsinden tanımlanır."
        )
        story.append(Paragraph(intro_text, self.styles["Body"]))
        story.append(Spacer(1, 15))

        # --- SaeD(T) Formülleri (OKUNAKLI: sol=formül sol yaslı, sağ=aralık sağ yaslı) ---
        base_style = self.styles["SymbolLineCenter"]  # font/size aynen kalsın

        formula_left = ParagraphStyle(
            name="VFormulaLeft",
            parent=base_style,
            alignment=TA_LEFT,
        )
        formula_right = ParagraphStyle(
            name="VFormulaRight",
            parent=base_style,
            alignment=TA_RIGHT,
        )

        doc_w = getattr(self, "_doc_width", 15 * cm)
        left_w = doc_w * 0.82
        right_w = doc_w * 0.18

        formula_data = [
            [
                Paragraph(
                    '<i>S</i><sub>aeD</sub>(<i>T</i>) = (0.4 + 0.6 × <i>T</i>/<i>T</i><sub>AD</sub>) × <i>S</i><sub>DS</sub>',
                    formula_left,
                ),
                Paragraph('(0 ≤ <i>T</i> ≤ <i>T</i><sub>AD</sub>)', formula_right),
            ],
            [
                Paragraph('<i>S</i><sub>aeD</sub>(<i>T</i>) = <i>S</i><sub>DS</sub>', formula_left),
                Paragraph('(<i>T</i><sub>AD</sub> ≤ <i>T</i> ≤ <i>T</i><sub>BD</sub>)', formula_right),
            ],
            [
                Paragraph('<i>S</i><sub>aeD</sub>(<i>T</i>) = <i>S</i><sub>D1</sub>/<i>T</i>', formula_left),
                Paragraph('(<i>T</i><sub>BD</sub> ≤ <i>T</i> ≤ <i>T</i><sub>LD</sub>)', formula_right),
            ],
            [
                Paragraph(
                    '<i>S</i><sub>aeD</sub>(<i>T</i>) = <i>S</i><sub>D1</sub> × <i>T</i><sub>LD</sub>/<i>T</i><sup>2</sup>',
                    formula_left,
                ),
                Paragraph('(<i>T</i><sub>LD</sub> ≤ <i>T</i>)', formula_right),
            ],
        ]

        formula_table = Table(formula_data, colWidths=[left_w, right_w], hAlign="CENTER")
        formula_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white]),
        ]))
        story.append(formula_table)
        story.append(Spacer(1, 12))

        # --- TAD, TBD ve TLD Hesaplamaları (tek blok, düzenli) ---
        calc_center = ParagraphStyle(
            name="VCalcCenter",
            parent=base_style,
            alignment=TA_CENTER,
        )

        if results.SD1 is not None and results.SDS is not None and results.SDS > 0:
            TA = 0.2 * (results.SD1 / results.SDS)
            TB = results.SD1 / results.SDS
            TL = 6.0  # Default TL value

            TAD = TA / 3
            TBD = TB / 3
            TLD = TL / 2

            calc_rows = [
                [Paragraph(f'<i>T</i><sub>AD</sub> = <i>T</i><sub>A</sub>/3 = {TA:.4f}/3 = {TAD:.4f} s', calc_center)],
                [Paragraph(f'<i>T</i><sub>BD</sub> = <i>T</i><sub>B</sub>/3 = {TB:.4f}/3 = {TBD:.4f} s', calc_center)],
                [Paragraph(f'<i>T</i><sub>LD</sub> = <i>T</i><sub>L</sub>/2 = {TL:.1f}/2 = {TLD:.1f} s', calc_center)],
            ]
        else:
            calc_rows = [
                [Paragraph('<i>T</i><sub>AD</sub> = —', calc_center)],
                [Paragraph('<i>T</i><sub>BD</sub> = —', calc_center)],
                [Paragraph('<i>T</i><sub>LD</sub> = 3 s', calc_center)],
            ]

        calc_table = Table(calc_rows, colWidths=[doc_w], hAlign="CENTER")
        calc_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(calc_table)
        story.append(Spacer(1, 15))

        # Düşey elastik tasarım spektrumu grafiği ekle
        try:
            graph_path = "report_images/dusey_elastik_tasarim_spektrumu.png"
            if os.path.exists(graph_path):
                with PILImage.open(graph_path) as pil_img:
                    max_w, max_h = 14 * cm, 10 * cm
                    scale = min(max_w / pil_img.width, max_h / pil_img.height)
                    story.append(Image(graph_path, width=pil_img.width * scale, height=pil_img.height * scale))
                    story.append(Spacer(1, 6))
                    caption_text = (
                        "TBDY-2018’e göre düşey elastik tasarım ivme spektrumunun gösterimi "
                        "(T: periyot [s], Sₐᵥ(T): spektral ivme [g])."
                        if params.locale == "tr"
                        else "Schematic shape of the vertical elastic design acceleration spectrum "
                        "(T: period [s], Sav(T): spectral acceleration [g])."
                    )
                    story.append(self._figure_caption(8, caption_text, params))
                    story.append(Spacer(1, 10))
        except Exception as e:  # noqa: BLE001
            logger.warning("Düşey spektrum grafiği eklenemedi: %s", e)

        # Dinamik düşey elastik tasarım spektrumu grafiği oluştur ve ekle
        if results.SDS is not None and results.SD1 is not None:
            try:
                dynamic_vertical_buf = self._create_vertical_spectrum_plot(results)
                if dynamic_vertical_buf:
                    self._buffers.append(dynamic_vertical_buf)
                    with PILImage.open(dynamic_vertical_buf) as pil_img:
                        max_w, max_h = 14 * cm, 10 * cm
                        scale = min(max_w / pil_img.width, max_h / pil_img.height)
                        story.append(Image(dynamic_vertical_buf, width=pil_img.width * scale, height=pil_img.height * scale))
                        story.append(Spacer(1, 6))
                        caption_text = (
                            "Hesaplanan düşey elastik tasarım ivme spektrumu "
                            "(T: periyot [s], Sₐᵥ(T): spektral ivme [g])."
                            if params.locale == "tr"
                            else "Computed vertical elastic design acceleration spectrum "
                            "(T: period [s], Sav(T): spectral acceleration [g])."
                        )
                        story.append(self._figure_caption(8, caption_text, params))
                        story.append(Spacer(1, 10))
            except Exception as e:  # noqa: BLE001
                logger.warning("Dinamik düşey spektrum grafiği oluşturulamadı: %s", e)

        story.append(Spacer(1, 20))


    def _add_spectrum_plots(self, story: List[Any], fig: plt.Figure, params: InputParams, section_no: int) -> None:
        heading = f"{section_no}. Spektrum Grafikleri" if params.locale == "tr" else f"{section_no}. Spectrum Plots"
        story.append(Paragraph(heading, self.styles["Heading1Blue"]))
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches="tight", pad_inches=0.02)
        buf.seek(0)
        self._buffers.append(buf)
        with PILImage.open(buf) as pil_img:
            max_w, max_h = 15 * cm, 10 * cm
            scale = min(max_w / pil_img.width, max_h / pil_img.height)
            story.append(Image(buf, width=pil_img.width * scale, height=pil_img.height * scale))
        story.append(Spacer(1, 20))
        plt.close(fig)

    def _add_spectrum_data_table(
        self,
        story: List[Any],
        data: Mapping[str, Any],
        results: CalculationResults,
        params: InputParams,
        section_no: int,
    ) -> None:
        """Spektrumun kritik periyotlarındaki sayısal değerleri özetler."""
        heading = (
            f"{section_no}. Spektrum Sayısal Çıktıları"
            if params.locale == "tr"
            else f"{section_no}. Numerical Spectrum Output"
        )
        story.append(Paragraph(heading, self.styles["Heading1Blue"]))
        table_cell_style = self.styles["TableCell"]

        intro = (
            "Bu bölümde yatay elastik tasarım ivme spektrumunun kritik periyotlar için hesaplanan sayısal değerleri verilmiştir. "
            "Tam periyot aralığının tamamı tabloya taşınmamış, mühendislik tasarımında sık kullanılan noktalar öne çıkarılmıştır."
            if params.locale == "tr"
            else "This section summarises the numerical values of the horizontal elastic design acceleration spectrum at a set "
                 "of critical periods used frequently in structural design."
        )
        story.append(Paragraph(intro, self.styles["Body"]))
        story.append(Spacer(1, 10))

        SDS = results.SDS or 0.0
        SD1 = results.SD1 or 0.0
        TL = results.TL or 6.0

        if SDS <= 0 or SD1 <= 0:
            msg = (
                "Spektrum parametreleri tanımlı olmadığından sayısal çıktı tablosu oluşturulamamıştır."
                if params.locale == "tr"
                else "Spectrum parameters are not defined; numerical spectrum table could not be generated."
            )
            story.append(Paragraph(msg, self.styles["Body"]))
            story.append(Spacer(1, 12))
            return

        caption_text = (
            "Kritik periyot noktalarında Sae(T) ve Sde(T) değerleri."
            if params.locale == "tr"
            else "Sae(T) and Sde(T) values at key periods."
        )
        story.append(self._table_caption(section_no, caption_text, params))

        TA = 0.2 * SD1 / SDS if SDS > 0 else 0.0
        TB = SD1 / SDS if SDS > 0 else 0.0

        def _sae(T_val: float) -> float:
            """Yatay elastik tasarım ivmesi Sae(T) [g]."""
            if T_val <= TA:
                return (0.4 + 0.6 * (T_val / TA)) * SDS if TA > 0 else SDS
            if T_val <= TB:
                return SDS
            if T_val <= TL:
                return SD1 / T_val if T_val > 0 else SDS
            return SD1 * TL / (T_val ** 2) if T_val > 0 else 0.0

        g_val = 9.81  # m/s²
        four_pi_sq = 4.0 * math.pi * math.pi

        critical_points: List[Tuple[str, float]] = [
            ("0", 0.0),
            ("T_A", TA),
            ("T_B", TB),
            ("1.0 s", 1.0),
            ("T_L", TL),
        ]

        label_map = {
            "T_A": "T<sub>A</sub>",
            "T_B": "T<sub>B</sub>",
            "T_L": "T<sub>L</sub>",
        }

        table_header = [
            Paragraph("Periyot Tanımı" if params.locale == "tr" else "Period label", table_cell_style),
            Paragraph("T [s]", table_cell_style),
            Paragraph("Sₐₑ(T) [g]" if params.locale == "tr" else "Sae(T) [g]", table_cell_style),
            Paragraph("Sₑₑ(T) [m]" if params.locale == "tr" else "Sde(T) [m]", table_cell_style),
        ]

        rows: List[List[Any]] = [table_header]
        for label, T_val in critical_points:
            Sa = _sae(T_val)
            Sd = (T_val ** 2 / four_pi_sq) * g_val * Sa
            rows.append(
                [
                    Paragraph(label_map.get(label, label), table_cell_style),
                    f"{T_val:.4f}",
                    f"{Sa:.4f}",
                    f"{Sd:.4f}",
                ]
            )

        table_style = self._table_style_with_padding(4.5)
        table = Table(rows, colWidths=[4 * cm, 3 * cm, 4 * cm, 4 * cm], style=table_style)
        story.append(table)
        story.append(Spacer(1, 16))
    
    def _add_conclusion(self, story: List[Any], results: CalculationResults, params: InputParams, section_no: int) -> None:
        """Sonuç ve değerlendirme bölümünü oluşturur."""
        heading = (
            f"{section_no}. Sonuç ve Değerlendirme"
            if params.locale == "tr"
            else f"{section_no}. Conclusions and Remarks"
        )
        story.append(Paragraph(heading, self.styles["Heading1Blue"]))

        # Temel parametreler ve karakteristik periyotlar
        Ss = results.Ss or 0.0
        S1 = results.S1 or 0.0
        Fs = results.Fs or 0.0
        F1 = results.F1 or 0.0
        SDS = results.SDS or 0.0
        SD1 = results.SD1 or 0.0
        TL = results.TL or 6.0

        TA = 0.2 * SD1 / SDS if SDS > 0 else 0.0
        TB = SD1 / SDS if SDS > 0 else 0.0

        # Düşey karakteristik periyotlar
        TAD = TA / 3.0 if TA > 0 else 0.0
        TBD = TB / 3.0 if TB > 0 else 0.0
        TLD = TL / 2.0 if TL > 0 else 0.0

        story.append(self._table_caption(
            section_no,
            "Temel spektrum parametreleri ve karakteristik periyotlar." if params.locale == "tr" else
            "Key spectrum parameters and characteristic periods.",
            params,
        ))

        table_cell_style = self.styles["TableCell"]

        def _cell(text: str) -> Paragraph:
            return Paragraph(text, table_cell_style)

        header_row = [
            _cell("Parametre" if params.locale == "tr" else "Parameter"),
            _cell("Değer" if params.locale == "tr" else "Value"),
        ]

        rows: List[List[Any]] = [header_row]

        def _fmt(val: float, digits: int = 4) -> str:
            return f"{val:.{digits}f}" if val not in (None, 0.0) else "—"

        # Konum ve giriş parametreleri
        loc_value = (
            f"{params.lat:.6f}, {params.lon:.6f}"
            if params.lat is not None and params.lon is not None
            else "—"
        )
        rows.extend(
            [
                [
                    _cell("Konum (Enlem, Boylam)" if params.locale == "tr" else "Location (Lat, Lon)"),
                    _cell(loc_value),
                ],
                [
                    _cell("Deprem Düzeyi" if params.locale == "tr" else "Earthquake Level"),
                    _cell(params.earthquake_level or "—"),
                ],
                [
                    _cell("Zemin Sınıfı" if params.locale == "tr" else "Soil Class"),
                    _cell(params.soil_class or "—"),
                ],
                [_cell("<i>S</i><sub>s</sub> [g]"), _cell(_fmt(Ss))],
                [_cell("<i>S</i><sub>1</sub> [g]"), _cell(_fmt(S1))],
                [_cell("<i>F</i><sub>s</sub>"), _cell(_fmt(Fs, 2))],
                [_cell("<i>F</i><sub>1</sub>"), _cell(_fmt(F1, 2))],
                [_cell("<i>S</i><sub>DS</sub> [g]"), _cell(_fmt(SDS))],
                [_cell("<i>S</i><sub>D1</sub> [g]"), _cell(_fmt(SD1))],
                [_cell("<i>T</i><sub>L</sub> [s]"), _cell(_fmt(TL, 2))],
                [_cell("<i>T</i><sub>A</sub> [s]"), _cell(_fmt(TA, 4))],
                [_cell("<i>T</i><sub>B</sub> [s]"), _cell(_fmt(TB, 4))],
                [_cell("<i>T</i><sub>AD</sub> [s]"), _cell(_fmt(TAD, 4))],
                [_cell("<i>T</i><sub>BD</sub> [s]"), _cell(_fmt(TBD, 4))],
                [_cell("<i>T</i><sub>LD</sub> [s]"), _cell(_fmt(TLD, 4))],
            ]
        )

        conclusion_table_style = self._table_style_with_padding(4.5)
        table = Table(rows, colWidths=[7 * cm, 8 * cm], style=conclusion_table_style)
        story.append(table)
        story.append(Spacer(1, 12))

        # Teknik notlar
        if params.locale == "tr":
            notes = (
                "Notlar: <i>S</i><sub>s</sub> ve <i>S</i><sub>1</sub> değerleri TDTH harita parametreleri olup "
                "<i>F</i><sub>s</sub> ve <i>F</i><sub>1</sub> katsayıları TBDY-2018 Tablo 2.1 ve Tablo 2.2 "
                "esas alınarak belirlenmiştir."
            )
        else:
            notes = (
                "Technical notes: (i) Ss and S1 are TDTH map parameters; "
                "(ii) Fs and F1 are selected according to TBDY‑2018 Tables 2.1 and 2.2; "
                "(iii) SDS and SD1 are the key parameters that define the design spectrum; "
                "(iv) This report is a computational output and additional engineering "
                "assessment may be required depending on the site and project conditions."
            )

        story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
        story.append(Spacer(1, 8))
        story.append(Paragraph(notes, self.styles["BodyWide"]))
        story.append(Spacer(1, 20))
    
    def _add_footer(self, story: List[Any], params: InputParams) -> None:
        # Footer intentionally left empty (no separator or text).
        pass

    def _create_horizontal_spectrum_plot(self, results: CalculationResults) -> Optional[io.BytesIO]:
        """Yatay elastik tasarım spektrumu grafiğini oluşturur ve Times New Roman fontunu kullanır."""
        try:
            import matplotlib
            matplotlib.use('Agg')  # GUI olmayan backend
            
            # Times New Roman fontunu matplotlib için ayarla
            plt.rcParams['font.family'] = 'Times New Roman'
            plt.rcParams['font.size'] = 10 + FONT_SIZE_INCREMENT
            plt.rcParams['axes.titlesize'] = 12 + FONT_SIZE_INCREMENT
            plt.rcParams['axes.labelsize'] = 11 + FONT_SIZE_INCREMENT
            plt.rcParams['xtick.labelsize'] = 9 + FONT_SIZE_INCREMENT
            plt.rcParams['ytick.labelsize'] = 9 + FONT_SIZE_INCREMENT
            plt.rcParams['legend.fontsize'] = 10 + FONT_SIZE_INCREMENT
            
            # Spektrum hesaplaması
            SDS = results.SDS
            SD1 = results.SD1
            TL = 6.0  # Default TL value
            
            if SDS <= 0:
                return None
                
            # Periyot dizisi oluştur
            TA = 0.2 * SD1 / SDS if SDS > 0 else 0.0
            TB = SD1 / SDS if SDS > 0 else 0.0
            
            # Optimized period array generation
            T_points = []
            T_points.extend(np.linspace(0, TA, 50))
            T_points.extend(np.linspace(TA, TB, 30))
            T_points.extend(np.linspace(TB, TL, 50))
            T_points.extend(np.linspace(TL, min(8.0, TL * 2), 30))
            
            T = np.unique(np.array(T_points))
            T = T[T >= 0]
            
            # Spektral ivme hesaplaması
            Sae = np.zeros_like(T)
            
            for i, t in enumerate(T):
                if t <= TA:
                    Sae[i] = (0.4 + 0.6 * t / TA) * SDS if TA > 0 else SDS
                elif t <= TB:
                    Sae[i] = SDS
                elif t <= TL:
                    Sae[i] = SD1 / t if t > 0 else SDS
                else:
                    Sae[i] = SD1 * TL / (t ** 2) if t > 0 else 0
            
            # Grafik oluştur
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # Ana spektrum çizgisi
            ax.plot(T, Sae, 'k-', linewidth=2.5, label='Yatay Elastik Tasarım Spektrumu')
            
            # Kritik noktaları işaretle
            if TA > 0:
                Sae_TA = (0.4 + 0.6) * SDS
                ax.plot(TA, Sae_TA, 'ro', markersize=8, label=f'TA = {TA:.4f} s')
                ax.axvline(x=TA, color='r', linestyle='--', alpha=0.5)
                
            if TB > 0:
                ax.plot(TB, SDS, 'go', markersize=8, label=f'TB = {TB:.4f} s')
                ax.axvline(x=TB, color='g', linestyle='--', alpha=0.5)
                
            ax.plot(TL, SD1/TL, 'mo', markersize=8, label=f'TL = {TL:.1f} s')
            ax.axvline(x=TL, color='m', linestyle='--', alpha=0.5)
            
            # Grafik özelleştirme
            ax.set_xlabel('Periyot, T (saniye)', fontweight='medium')
            ax.set_ylabel('Spektral İvme, Sₐₑ(T) (g)', fontweight='medium')
            ax.set_title('Yatay Elastik Tasarım Spektrumu', fontweight='bold', pad=15)
            
            # Grid ve legend
            ax.grid(True, alpha=0.3)
            ax.legend(loc='upper right', framealpha=0.9)
            
            # Eksen sınırları
            ax.set_xlim(0, max(8.0, TL * 1.5))
            ax.set_ylim(0, max(Sae) * 1.1)
            
            # Layout optimize
            plt.tight_layout()
            
            # PNG olarak buffer'a kaydet
            buf = io.BytesIO()
            fig.savefig(buf, format='PNG', dpi=300, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            buf.seek(0)
            plt.close(fig)
            
            return buf
            
        except Exception as e:
            logger.warning("Spektrum grafiği oluşturulamadı: %s", e)
            return None

    def _create_displacement_spectrum_plot(self, results: CalculationResults) -> Optional[io.BytesIO]:
        """Yatay elastik yerdeğiştirme spektrumu grafiğini oluşturur ve Times New Roman fontunu kullanır."""
        try:
            import matplotlib
            matplotlib.use('Agg')  # GUI olmayan backend
            
            # Times New Roman fontunu matplotlib için ayarla
            plt.rcParams['font.family'] = 'Times New Roman'
            plt.rcParams['font.size'] = 10 + FONT_SIZE_INCREMENT
            plt.rcParams['axes.titlesize'] = 12 + FONT_SIZE_INCREMENT
            plt.rcParams['axes.labelsize'] = 11 + FONT_SIZE_INCREMENT
            plt.rcParams['xtick.labelsize'] = 9 + FONT_SIZE_INCREMENT
            plt.rcParams['ytick.labelsize'] = 9 + FONT_SIZE_INCREMENT
            plt.rcParams['legend.fontsize'] = 10 + FONT_SIZE_INCREMENT
            
            # Spektrum hesaplaması
            SDS = results.SDS
            SD1 = results.SD1
            TL = 6.0  # Default TL value
            g = 9.81  # Yerçekimi ivmesi (m/s²)
            
            if SDS <= 0:
                return None
                
            # Periyot dizisi oluştur
            TA = 0.2 * SD1 / SDS if SDS > 0 else 0.0
            TB = SD1 / SDS if SDS > 0 else 0.0
            
            # Optimized period array generation
            T_points = []
            T_points.extend(np.linspace(0.01, TA, 50))  # 0'dan kaçın (bölme hatası için)
            T_points.extend(np.linspace(TA, TB, 30))
            T_points.extend(np.linspace(TB, TL, 50))
            T_points.extend(np.linspace(TL, min(8.0, TL * 2), 30))
            
            T = np.unique(np.array(T_points))
            T = T[T > 0]  # Sıfır periyodu hariç tut
            
            # Önce spektral ivme hesapla (Sae)
            Sae = np.zeros_like(T)
            
            for i, t in enumerate(T):
                if t <= TA:
                    Sae[i] = (0.4 + 0.6 * t / TA) * SDS if TA > 0 else SDS
                elif t <= TB:
                    Sae[i] = SDS
                elif t <= TL:
                    Sae[i] = SD1 / t if t > 0 else SDS
                else:
                    Sae[i] = SD1 * TL / (t ** 2) if t > 0 else 0
            
            # Yerdeğiştirme spektrumunu hesapla: Sde(T) = T²/(4π²) × g × Sae(T)
            Sde = (T**2 / (4 * np.pi**2)) * g * Sae  # Sonuç metre cinsinden
            
            # Grafik oluştur
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # Ana spektrum çizgisi
            ax.plot(T, Sde, 'k-', linewidth=2.5, label='Yatay Elastik Yerdeğiştirme Spektrumu')
            
            # Kritik noktaları işaretle
            if TA > 0:
                Sae_TA = (0.4 + 0.6) * SDS
                Sde_TA = (TA**2 / (4 * np.pi**2)) * g * Sae_TA
                ax.plot(TA, Sde_TA, 'ro', markersize=8, label=f'TA = {TA:.4f} s')
                ax.axvline(x=TA, color='r', linestyle='--', alpha=0.5)
                
            if TB > 0:
                Sde_TB = (TB**2 / (4 * np.pi**2)) * g * SDS
                ax.plot(TB, Sde_TB, 'go', markersize=8, label=f'TB = {TB:.4f} s')
                ax.axvline(x=TB, color='g', linestyle='--', alpha=0.5)
                
            Sde_TL = (TL**2 / (4 * np.pi**2)) * g * (SD1/TL)
            ax.plot(TL, Sde_TL, 'mo', markersize=8, label=f'TL = {TL:.1f} s')
            ax.axvline(x=TL, color='m', linestyle='--', alpha=0.5)
            
            # Grafik özelleştirme
            ax.set_xlabel('Periyot, T (saniye)', fontweight='medium')
            ax.set_ylabel('Spektral Yerdeğiştirme, Sde(T) (m)', fontweight='medium')
            ax.set_title('Yatay Elastik Yerdeğiştirme Spektrumu', fontweight='bold', pad=15)
            
            # Grid ve legend
            ax.grid(True, alpha=0.3)
            ax.legend(loc='lower right', framealpha=0.9)
            
            # Eksen sınırları
            ax.set_xlim(0, max(8.0, TL * 1.5))
            ax.set_ylim(0, max(Sde) * 1.1)
            
            # Layout optimize
            plt.tight_layout()
            
            # PNG olarak buffer'a kaydet
            buf = io.BytesIO()
            fig.savefig(buf, format='PNG', dpi=300, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            buf.seek(0)
            plt.close(fig)
            
            return buf
            
        except Exception as e:
            logger.warning("Yerdeğiştirme spektrumu grafiği oluşturulamadı: %s", e)
            return None

    def _create_vertical_spectrum_plot(self, results: CalculationResults) -> Optional[io.BytesIO]:
        """Düşey elastik tasarım spektrumu grafiğini oluşturur (0-3 saniye arası).

        TBDY-2018 uyumlu düşey spektrum formülleri (3 saniyeye kadar):

            1. Bölge: S_aeD(T) = (0.32 + 0.48 T/TAD) SDS  (0 ≤ T ≤ TAD)
            2. Bölge: S_aeD(T) = 0.8 SDS                   (TAD ≤ T ≤ TBD)
            3. Bölge: S_aeD(T) = 0.8 SDS TBD / T          (TBD ≤ T ≤ 3.0s)

        Not: 3 saniyeden sonrası gösterilmez (NaN sorununu önlemek için).
        Geçişlerde süreklilik sağlanır.
        """
        try:
            import matplotlib
            matplotlib.use('Agg')  # GUI olmayan backend
            import matplotlib.pyplot as plt
            import numpy as np
            import io

            # Görsel ayarları
            plt.rcParams['font.family'] = 'Times New Roman'
            plt.rcParams['font.size'] = 10 + FONT_SIZE_INCREMENT
            plt.rcParams['axes.titlesize'] = 12 + FONT_SIZE_INCREMENT
            plt.rcParams['axes.labelsize'] = 11 + FONT_SIZE_INCREMENT
            plt.rcParams['xtick.labelsize'] = 9 + FONT_SIZE_INCREMENT
            plt.rcParams['ytick.labelsize'] = 9 + FONT_SIZE_INCREMENT
            plt.rcParams['legend.fontsize'] = 10 + FONT_SIZE_INCREMENT

            SDS = results.SDS
            SD1 = results.SD1
            TL = 6.0  # TBDY varsayılanı
            if SDS is None or SD1 is None or SDS <= 0:
                return None

            # Yatay karakteristik periyotlar
            TA = 0.2 * SD1 / SDS
            TB = SD1 / SDS
            # Düşey karakteristik periyotlar (TBDY-2018)
            TAD = TA / 3.0
            TBD = TB / 3.0
            TLD = TL / 2.0

            # Periyot vektörü (3 saniyeye kadar, süreklilik ve yoğunluk)
            T_pts = []
            T_pts.extend(np.linspace(0.0, max(TAD, 1e-4), 50))
            T_pts.extend(np.linspace(max(TAD, 1e-4), max(TBD, 2e-4), 30))
            T_pts.extend(np.linspace(max(TBD, 2e-4), max(TLD, 3e-4), 50))
            # 3 saniyeden sonrası dahil edilmiyor (NaN sorununu önlemek için)
            T = np.unique(np.array(T_pts))
            T = T[T <= 3.0]  # 3 saniyeyi aşan değerleri filtrele

            SaeD = np.zeros_like(T)
            for i, t in enumerate(T):
                if t <= max(TAD, 1e-9):
                    # 1. Bölge: 0 ≤ T ≤ TAD
                    # T=0'da 0.32*SDS, T=TAD'de 0.8*SDS olacak şekilde lineer
                    if TAD > 0:
                        SaeD[i] = (0.32 + 0.48 * (t / TAD)) * SDS
                    else:
                        SaeD[i] = SDS  # patoloji durumunda sabit kabul
                elif t <= max(TBD, 1e-9):
                    # 2. Bölge: TAD ≤ T ≤ TBD (sabit plato)
                    SaeD[i] = 0.8 * SDS
                else:
                    # 3. Bölge: TBD ≤ T ≤ 3.0s (0.8*SDS*TBD/T formülü)
                    SaeD[i] = 0.8 * SDS * TBD / t if t > 0 else 0.8 * SDS

            # Grafik
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.plot(T, SaeD, 'k-', linewidth=2.5, label='Düşey Elastik Tasarım Spektrumu')

            # Kritik noktalar
            if TAD > 0:
                ax.plot(TAD, 0.8 * SDS, 'ro', markersize=7, label=f'TAD = {TAD:.4f} s')
                ax.axvline(x=TAD, linestyle='--', alpha=0.5)
            if TBD > 0:
                ax.plot(TBD, 0.8 * SDS, 'go', markersize=7, label=f'TBD = {TBD:.4f} s')
                ax.axvline(x=TBD, linestyle='--', alpha=0.5)
            if TLD > 0:
                ax.plot(TLD, 0.8 * SDS * TBD / TLD, 'mo', markersize=7, label=f'TLD = {TLD:.2f} s')
                ax.axvline(x=TLD, linestyle='--', alpha=0.5)

            ax.set_xlabel('Periyot, T (s)')
            ax.set_ylabel('Spektral İvme, SₐeD(T) (g)')
            ax.set_title('Düşey Elastik Tasarım Spektrumu', pad=12)
            ax.grid(True, alpha=0.3)
            ax.legend(loc='upper right', framealpha=0.9)
            ax.set_xlim(0, 3.0)  # Düşey spektrum 3 saniyeye kadar gösterilir
            ax.set_ylim(0, max(SaeD) * 1.15 if SaeD.size else 1)
            plt.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format='PNG', dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
            buf.seek(0)
            plt.close(fig)
            return buf

        except Exception as e:  # noqa: BLE001
            logger.warning('Düşey spektrum grafiği oluşturulamadı: %s', e)
            return None

    # ---------- Cleanup ----------------------------------------------------
    def _cleanup_buffers(self) -> None:
        for buf in self._buffers:
            try:
                buf.close()
            except Exception:  # noqa: BLE001
                pass
        self._buffers.clear()


# ----------------------- Font registration helper ------------------------

def _register_times_new_roman(font_path: Optional[str]) -> str:
    """
    Registers Times New Roman font family (Normal, Bold, Italic, Bold-Italic).
    Tries common paths on Linux/Windows/macOS. Falls back to Helvetica.
    """
    # Font variant names and their common filenames
    variants = {
        "TimesNewRoman": ["times.ttf", "Times New Roman.ttf", "TimesNewRoman.ttf"],
        "TimesNewRoman-Bold": ["timesbd.ttf", "Times New Roman Bold.ttf", "TimesNewRoman-Bold.ttf", "timesb.ttf"],
        "TimesNewRoman-Italic": ["timesi.ttf", "Times New Roman Italic.ttf", "TimesNewRoman-Italic.ttf"],
        "TimesNewRoman-BoldItalic": ["timesbi.ttf", "Times New Roman Bold Italic.ttf", "TimesNewRoman-BoldItalic.ttf"],
    }

    # Common font directories
    font_dirs = [
        "/usr/share/fonts/truetype/msttcorefonts/",
        "C:/Windows/Fonts/",
        "/Library/Fonts/",
        "/System/Library/Fonts/",
    ]
    if font_path and os.path.isdir(font_path):
        font_dirs.insert(0, font_path)

    registered_count = 0
    for name, filenames in variants.items():
        font_found = False
        for directory in font_dirs:
            for filename in filenames:
                path = os.path.join(directory, filename)
                if os.path.exists(path):
                    try:
                        pdfmetrics.registerFont(TTFont(name, path))
                        logger.info("Registered font '%s' from %s", name, path)
                        registered_count += 1
                        font_found = True
                        break  # Move to the next variant
                    except Exception as e:
                        logger.warning("Failed to register font %s: %s", path, e)
            if font_found:
                break # Move to the next variant

    if registered_count >= 4:
        try:
            pdfmetrics.registerFontFamily(
                "TimesNewRoman",
                normal="TimesNewRoman",
                bold="TimesNewRoman-Bold",
                italic="TimesNewRoman-Italic",
                boldItalic="TimesNewRoman-BoldItalic",
            )
            logger.info("Successfully registered Times New Roman font family.")
            return "TimesNewRoman"
        except Exception as e:
            logger.error("Failed to register font family: %s", e)

    logger.warning(
        "Could not register all Times New Roman variants (found %d/4). "
        "Falling back to Helvetica. Bold/Italic may not render correctly.",
        registered_count,
    )
    return "Helvetica"


# ----------------------- Satellite image helper ---------------------------
def _find_font_file() -> Optional[str]:
    """Tries to find a path to a Times New Roman font file."""
    # Prioritize bold font for better visibility on maps
    filenames = [
        "timesbd.ttf", "Times New Roman Bold.ttf", "timesb.ttf",
        "times.ttf", "Times New Roman.ttf"
    ]
    font_dirs = [
        "C:/Windows/Fonts/",
        "/usr/share/fonts/truetype/msttcorefonts/",
        "/Library/Fonts/",
        "/System/Library/Fonts/",
    ]
    for directory in font_dirs:
        for filename in filenames:
            path = os.path.join(directory, filename)
            if os.path.exists(path):
                return path
    return None

def _deg2num(lat_deg: float, lon_deg: float, zoom: int) -> Tuple[int, int]:
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = math.floor((lon_deg + 180.0) / 360.0 * n)
    ytile = math.floor((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return xtile, ytile


def _deg2pixel(lat_deg: float, lon_deg: float, zoom: int, tile_size: int = 256) -> Tuple[float, float]:
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    x = (lon_deg + 180.0) / 360.0 * n * tile_size
    y = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n * tile_size
    return x, y


def _download_tile(x: int, y: int, z: int, tile_size: int = 256) -> PILImage.Image:
    # Google vt uydu tiles (repo GUI'de de kullanılıyor)
    url = f"https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
    req = request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; PDFReportGenerator/1.0)"})
    with request.urlopen(req, timeout=10) as resp:
        data = resp.read()
    img = PILImage.open(io.BytesIO(data)).convert("RGB")
    # Bazı hizmetler 512px döndürebilir; gerekirse yeniden boyutlandır
    if img.size != (tile_size, tile_size):
        img = img.resize((tile_size, tile_size), PILImage.LANCZOS)
    return img


def _compose_satellite_image(
    lat: float,
    lon: float,
    zoom: int = 18,
    tiles_w: int = 6,
    tiles_h: int = 4,
    tile_size: int = 256,
    out_size: Tuple[int, int] = (1500, 960),
) -> Tuple[io.BytesIO, Tuple[int, int]]:
    """Verilen koordinasyon için küçük bir uydu görüntüsü oluşturur.

    Google vt uydu tile'larını indirir, birleştirir ve merkeze göre kırpar.
    Hata durumunda Exception fırlatır.
    """
    if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))):
        raise ValueError("Geçersiz koordinatlar")

    # Merkez tile ve piksel koordinatı
    center_xtile, center_ytile = _deg2num(lat, lon, zoom)
    center_xpx, center_ypx = _deg2pixel(lat, lon, zoom, tile_size)

    # Sol-üst tile indexleri
    half_w = tiles_w // 2
    half_h = tiles_h // 2
    left_xtile = center_xtile - half_w
    top_ytile = center_ytile - half_h

    # Stitching tuvali
    canvas_w = tiles_w * tile_size
    canvas_h = tiles_h * tile_size
    canvas = PILImage.new("RGB", (canvas_w, canvas_h), (255, 255, 255))

    n = 2 ** zoom

    # Tile'ları indir ve yapıştır
    for dy in range(tiles_h):
        for dx in range(tiles_w):
            tx = (left_xtile + dx) % n
            ty = top_ytile + dy
            if ty < 0:
                ty = 0
            if ty >= n:
                ty = n - 1
            try:
                tile_img = _download_tile(tx, ty, zoom, tile_size)
            except Exception as e:  # noqa: BLE001
                # Tek tile hatasında beyaz blok ile devam
                logger.warning("Tile indirilemedi (%s,%s,%s): %s", tx, ty, zoom, e)
                tile_img = PILImage.new("RGB", (tile_size, tile_size), (240, 240, 240))
            canvas.paste(tile_img, (dx * tile_size, dy * tile_size))

    # Merkez pikselin stitched canvas üzerindeki konumu
    left_xpx_global = left_xtile * tile_size
    top_ypx_global = top_ytile * tile_size
    center_x_on_canvas = center_xpx - left_xpx_global
    center_y_on_canvas = center_ypx - top_ypx_global

    out_w, out_h = out_size
    crop_left = int(round(center_x_on_canvas - out_w / 2))
    crop_top = int(round(center_y_on_canvas - out_h / 2))
    crop_right = crop_left + out_w
    crop_bottom = crop_top + out_h

    # Sınırları koru
    if crop_left < 0:
        crop_right -= crop_left
        crop_left = 0
    if crop_top < 0:
        crop_bottom -= crop_top
        crop_top = 0
    if crop_right > canvas_w:
        shift = crop_right - canvas_w
        crop_left -= shift
        crop_right = canvas_w
        if crop_left < 0:
            crop_left = 0
    if crop_bottom > canvas_h:
        shift = crop_bottom - canvas_h
        crop_top -= shift
        crop_bottom = canvas_h
        if crop_top < 0:
            crop_top = 0

    cropped = canvas.crop((crop_left, crop_top, crop_right, crop_bottom))

    # Merkez işareti ekle (kırmızı nokta gerçek koordinatın kırpılmış görüntü içindeki konumuna yerleştirilir)
    try:
        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(cropped)
        cropped_w, cropped_h = cropped.size
        # Koordinatın kırpılmış görüntü içindeki piksel konumu
        cx_f = center_x_on_canvas - crop_left
        cy_f = center_y_on_canvas - crop_top
        # Güvenli tamsayı ve sınır içinde tut
        cx = max(0, min(int(round(cx_f)), cropped_w - 1))
        cy = max(0, min(int(round(cy_f)), cropped_h - 1))
        
        # Kırmızı noktayı çiz
        r_outer = 20
        r_inner = 8
        draw.ellipse((cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer), outline=(220, 20, 20), width=2)
        draw.ellipse((cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner), fill=(220, 20, 20))
        
        # Ok ve metin ekle
        font_path = _find_font_file()
        try:
            font_size = 36 + FONT_SIZE_INCREMENT
            font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
        except IOError:
            font = ImageFont.load_default()

        text = "Analiz Konumu"
        text_pos = (cx + 40, cy - 80)
        
        # Görünürlük için metne basit bir dış hat çiz
        outline_color = "white"
        text_color = "black"
        draw.text((text_pos[0]-2, text_pos[1]-2), text, font=font, fill=outline_color)
        draw.text((text_pos[0]+2, text_pos[1]-2), text, font=font, fill=outline_color)
        draw.text((text_pos[0]-2, text_pos[1]+2), text, font=font, fill=outline_color)
        draw.text((text_pos[0]+2, text_pos[1]+2), text, font=font, fill=outline_color)
        draw.text(text_pos, text, font=font, fill=text_color)
        
        # Ok çiz
        arrow_start = (cx + 35, cy - 45)
        arrow_end = (cx + 18, cy - 18) # Dış dairenin kenarına işaret et
        draw.line([arrow_start, arrow_end], fill=text_color, width=3)

        # Ok başı çiz
        angle = math.atan2(arrow_end[1] - arrow_start[1], arrow_end[0] - arrow_start[0])
        arrowhead_len = 15
        arrowhead_angle = math.pi / 6 # 30 derece
        
        x1 = arrow_end[0] - arrowhead_len * math.cos(angle - arrowhead_angle)
        y1 = arrow_end[1] - arrowhead_len * math.sin(angle - arrowhead_angle)
        x2 = arrow_end[0] - arrowhead_len * math.cos(angle + arrowhead_angle)
        y2 = arrow_end[1] - arrowhead_len * math.sin(angle + arrowhead_angle)
        
        draw.polygon([arrow_end, (x1, y1), (x2, y2)], fill=text_color)
        
    except Exception:
        pass

    # Çıktıyı PNG olarak buffer'a yaz
    out_buf = io.BytesIO()
    cropped.save(out_buf, format="PNG", optimize=True)
    out_buf.seek(0)
    return out_buf, cropped.size
