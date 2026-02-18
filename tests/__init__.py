"""
TBDY-2018 Spektrum Analizi Test Paketi
"""

# Test sırasında gerekli modüllerin yüklenmesi
import sys
import os
from pathlib import Path

# src klasörünü Python path'ine ekle
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path)) 