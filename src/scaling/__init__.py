"""
3B Ölçekleme Modülleri
====================

PGMD uyumlu 3B ölçekleme işlemleri için modüller.
"""

# Ana modüller
from .scaling_3d_main import Scaling3DProcessor, Scaling3DConfig, create_default_config

# Alt modüller
from .period_grid import build_period_grid, validate_period_grid, interpolate_to_grid
from .weight_function import (
    create_weight_function, create_uniform_weights, create_short_period_weights,
    create_long_period_weights, create_band_weights, validate_weight_function
)
from .scale_factor import (
    calculate_scale_factor, calculate_scale_factor_3d, calculate_mse_log_space,
    calculate_geometric_mean_spectrum, calculate_srss_spectrum, 
    calculate_scale_factor_3d_tbdy, normalize_weights_tbdy
)
from .scale_3d import (
    scale_record_3d, scale_multiple_records_3d, calculate_suite_statistics,
    rank_records_by_mse, select_top_records, ScaleResult3D
)
from .ranking_selection import (
    rank_records_by_mse, select_top_records, filter_records_by_criteria,
    calculate_selection_statistics, create_default_criteria, RecordMetadata
)
from .regulatory_checks import (
    perform_comprehensive_regulatory_checks, calculate_suite_averages,
    create_default_checks, check_asce_7_16_compliance, check_tbdy_compliance
)
from .reporting import (
    create_scaling_report, export_comprehensive_report, create_summary_report,
    export_to_csv, export_to_json, export_spectra_to_csv
)
from .tbdy_scaling import (
    scale_3d_simple_tbdy, validate_records_tbdy, export_tbdy_results_csv,
    TBDYScaleResult, design_spectrum_tbdy
)

__all__ = [
    # Ana sınıflar
    'Scaling3DProcessor',
    'Scaling3DConfig',
    'TBDYScaleResult',
    'create_default_config',
    
    # Periyot ızgarası
    'build_period_grid',
    'validate_period_grid',
    'interpolate_to_grid',
    
    # Ağırlık fonksiyonu
    'create_weight_function',
    'create_uniform_weights',
    'create_short_period_weights',
    'create_long_period_weights',
    'create_band_weights',
    'validate_weight_function',
    
    # Ölçek katsayısı
    'calculate_scale_factor',
    'calculate_scale_factor_3d',
    'calculate_scale_factor_3d_tbdy',
    'calculate_mse_log_space',
    'calculate_geometric_mean_spectrum',
    'calculate_srss_spectrum',
    'normalize_weights_tbdy',
    
    # 3B ölçekleme
    'scale_record_3d',
    'scale_multiple_records_3d',
    'calculate_suite_statistics',
    'rank_records_by_mse',
    'select_top_records',
    'ScaleResult3D',
    
    # Sıralama ve seçim
    'filter_records_by_criteria',
    'calculate_selection_statistics',
    'create_default_criteria',
    'RecordMetadata',
    
    # Yönetmelik kontrolleri
    'perform_comprehensive_regulatory_checks',
    'calculate_suite_averages',
    'create_default_checks',
    'check_asce_7_16_compliance',
    'check_tbdy_compliance',
    
    # Raporlama
    'create_scaling_report',
    'export_comprehensive_report',
    'create_summary_report',
    'export_to_csv',
    'export_to_json',
    'export_spectra_to_csv',
    
    # TBDY-2018
    'scale_3d_simple_tbdy',
    'validate_records_tbdy',
    'export_tbdy_results_csv',
    'design_spectrum_tbdy'
]
