"""
Veritabanı Yöneticisi
SQLite ile proje verileri, hesaplamalar ve ayarları saklar
"""

import sqlite3
import json
import pickle
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import logging

class DatabaseManager:
    """SQLite veritabanı yöneticisi"""
    
    def __init__(self, db_path="tbdy_spektrum.db"):
        """
        Args:
            db_path (str): Veritabanı dosya yolu
        """
        self.db_path = db_path
        self.conn = None
        
        # Veritabanını başlat
        self._init_database()
    
    def _init_database(self):
        """Veritabanını başlatır ve tabloları oluşturur"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # Dict-like access
            
            # Tabloları oluştur
            self._create_tables()
            
            logging.info(f"Veritabanı başlatıldı: {self.db_path}")
            
        except Exception as e:
            logging.error(f"Veritabanı başlatma hatası: {e}")
            raise
    
    def _create_tables(self):
        """Veritabanı tablolarını oluşturur"""
        cursor = self.conn.cursor()
        
        # Projeler tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                location_lat REAL,
                location_lon REAL,
                earthquake_level TEXT,
                soil_class TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                project_hash TEXT UNIQUE
            )
        """)
        
        # Hesaplamalar tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calculations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                calculation_type TEXT NOT NULL,
                input_params TEXT NOT NULL,  -- JSON
                results TEXT NOT NULL,       -- JSON
                spectrum_data BLOB,          -- Pickled DataFrame
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                execution_time_ms REAL,
                FOREIGN KEY (project_id) REFERENCES projects (id)
            )
        """)
        
        # Kullanıcı ayarları tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT NOT NULL,
                setting_type TEXT DEFAULT 'string',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # AFAD veri dosyaları tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS afad_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_hash TEXT UNIQUE NOT NULL,
                file_size INTEGER,
                record_count INTEGER,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP
            )
        """)
        
        # Favoriler tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                calculation_id INTEGER,
                favorite_type TEXT DEFAULT 'calculation',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id),
                FOREIGN KEY (calculation_id) REFERENCES calculations (id)
            )
        """)
        
        self.conn.commit()
    
    def save_project(self, project_data):
        """
        Projeyi veritabanına kaydeder
        
        Args:
            project_data (dict): Proje bilgileri
            
        Returns:
            int: Proje ID'si
        """
        cursor = self.conn.cursor()
        
        # Proje hash'i oluştur (benzersiz proje kontrolü için)
        project_str = f"{project_data.get('location_lat', 0)}-{project_data.get('location_lon', 0)}-{project_data.get('earthquake_level', '')}-{project_data.get('soil_class', '')}"
        project_hash = hashlib.md5(project_str.encode()).hexdigest()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO projects 
                (name, description, location_lat, location_lon, earthquake_level, soil_class, project_hash, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_data.get('name', 'Yeni Proje'),
                project_data.get('description', ''),
                project_data.get('location_lat'),
                project_data.get('location_lon'), 
                project_data.get('earthquake_level'),
                project_data.get('soil_class'),
                project_hash,
                datetime.now().isoformat()
            ))
            
            project_id = cursor.lastrowid
            self.conn.commit()
            
            return project_id
            
        except Exception as e:
            logging.error(f"Proje kaydetme hatası: {e}")
            self.conn.rollback()
            return None
    
    def save_calculation(self, project_id, calculation_data):
        """
        Hesaplamayı veritabanına kaydeder
        
        Args:
            project_id (int): Proje ID'si
            calculation_data (dict): Hesaplama verileri
            
        Returns:
            int: Hesaplama ID'si
        """
        cursor = self.conn.cursor()
        
        try:
            # Spectrum data'yı pickle ile serialize et
            spectrum_data_blob = None
            if 'spectrum_dataframe' in calculation_data:
                spectrum_data_blob = pickle.dumps(calculation_data['spectrum_dataframe'])
            
            cursor.execute("""
                INSERT INTO calculations 
                (project_id, calculation_type, input_params, results, spectrum_data, execution_time_ms)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                project_id,
                calculation_data.get('type', 'spectrum'),
                json.dumps(calculation_data.get('input_params', {})),
                json.dumps(calculation_data.get('results', {})),
                spectrum_data_blob,
                calculation_data.get('execution_time_ms', 0)
            ))
            
            calculation_id = cursor.lastrowid
            self.conn.commit()
            
            return calculation_id
            
        except Exception as e:
            logging.error(f"Hesaplama kaydetme hatası: {e}")
            self.conn.rollback()
            return None
    
    def load_project(self, project_id):
        """
        Projeyi veritabanından yükler
        
        Args:
            project_id (int): Proje ID'si
            
        Returns:
            dict: Proje bilgileri
        """
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        return None
    
    def load_calculation(self, calculation_id):
        """
        Hesaplamayı veritabanından yükler
        
        Args:
            calculation_id (int): Hesaplama ID'si
            
        Returns:
            dict: Hesaplama bilgileri
        """
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT * FROM calculations WHERE id = ?", (calculation_id,))
        row = cursor.fetchone()
        
        if row:
            result = dict(row)
            
            # JSON verileri parse et
            result['input_params'] = json.loads(result['input_params'])
            result['results'] = json.loads(result['results'])
            
            # Spectrum data'yı deserialize et
            if result['spectrum_data']:
                result['spectrum_dataframe'] = pickle.loads(result['spectrum_data'])
            
            return result
        return None
    
    def get_projects_list(self, limit=50):
        """
        Proje listesini getirir
        
        Args:
            limit (int): Maksimum proje sayısı
            
        Returns:
            list: Proje listesi
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT id, name, description, location_lat, location_lon, 
                   earthquake_level, soil_class, created_at, updated_at
            FROM projects 
            ORDER BY updated_at DESC 
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_calculations_for_project(self, project_id):
        """
        Bir projeye ait hesaplamaları getirir
        
        Args:
            project_id (int): Proje ID'si
            
        Returns:
            list: Hesaplama listesi
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT id, calculation_type, created_at, execution_time_ms
            FROM calculations 
            WHERE project_id = ?
            ORDER BY created_at DESC
        """, (project_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def search_projects(self, search_term="", filters=None):
        """
        Projeleri arar
        
        Args:
            search_term (str): Arama terimi
            filters (dict): Ek filtreler
            
        Returns:
            list: Bulunan projeler
        """
        cursor = self.conn.cursor()
        
        query = "SELECT * FROM projects WHERE 1=1"
        params = []
        
        if search_term:
            query += " AND (name LIKE ? OR description LIKE ?)"
            params.extend([f"%{search_term}%", f"%{search_term}%"])
        
        if filters:
            if 'earthquake_level' in filters:
                query += " AND earthquake_level = ?"
                params.append(filters['earthquake_level'])
            
            if 'soil_class' in filters:
                query += " AND soil_class = ?"
                params.append(filters['soil_class'])
        
        query += " ORDER BY updated_at DESC LIMIT 100"
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def save_user_setting(self, key, value, setting_type='string'):
        """
        Kullanıcı ayarını kaydeder
        
        Args:
            key (str): Ayar anahtarı
            value: Ayar değeri
            setting_type (str): Ayar türü
        """
        cursor = self.conn.cursor()
        
        # Değeri string'e çevir
        if setting_type == 'json':
            value_str = json.dumps(value)
        else:
            value_str = str(value)
        
        cursor.execute("""
            INSERT OR REPLACE INTO user_settings 
            (setting_key, setting_value, setting_type, updated_at)
            VALUES (?, ?, ?, ?)
        """, (key, value_str, setting_type, datetime.now().isoformat()))
        
        self.conn.commit()
    
    def get_user_setting(self, key, default=None):
        """
        Kullanıcı ayarını getirir
        
        Args:
            key (str): Ayar anahtarı
            default: Varsayılan değer
            
        Returns:
            Ayar değeri
        """
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT setting_value, setting_type FROM user_settings WHERE setting_key = ?", (key,))
        row = cursor.fetchone()
        
        if row:
            value_str, setting_type = row
            
            try:
                if setting_type == 'json':
                    return json.loads(value_str)
                elif setting_type == 'int':
                    return int(value_str)
                elif setting_type == 'float':
                    return float(value_str)
                elif setting_type == 'bool':
                    return value_str.lower() == 'true'
                else:
                    return value_str
            except:
                return default
        
        return default
    
    def register_afad_file(self, file_path, record_count):
        """
        AFAD dosyasını kayıt altına alır
        
        Args:
            file_path (str): Dosya yolu
            record_count (int): Kayıt sayısı
            
        Returns:
            int: Dosya ID'si
        """
        cursor = self.conn.cursor()
        
        # Dosya bilgileri
        path_obj = Path(file_path)
        file_name = path_obj.name
        file_size = path_obj.stat().st_size
        
        # Dosya hash'i
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO afad_files 
                (file_path, file_name, file_hash, file_size, record_count, last_used_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(file_path), file_name, file_hash, file_size, 
                record_count, datetime.now().isoformat()
            ))
            
            file_id = cursor.lastrowid
            self.conn.commit()
            return file_id
            
        except Exception as e:
            logging.error(f"AFAD dosyası kaydetme hatası: {e}")
            return None
    
    def add_to_favorites(self, project_id=None, calculation_id=None, notes=""):
        """
        Favorilere ekler
        
        Args:
            project_id (int): Proje ID'si
            calculation_id (int): Hesaplama ID'si
            notes (str): Notlar
        """
        cursor = self.conn.cursor()
        
        favorite_type = 'calculation' if calculation_id else 'project'
        
        cursor.execute("""
            INSERT INTO favorites (project_id, calculation_id, favorite_type, notes)
            VALUES (?, ?, ?, ?)
        """, (project_id, calculation_id, favorite_type, notes))
        
        self.conn.commit()
    
    def get_favorites(self, favorite_type=None):
        """
        Favorileri getirir
        
        Args:
            favorite_type (str): Favori türü ('project' veya 'calculation')
            
        Returns:
            list: Favori listesi
        """
        cursor = self.conn.cursor()
        
        query = """
            SELECT f.*, p.name as project_name, c.calculation_type
            FROM favorites f
            LEFT JOIN projects p ON f.project_id = p.id
            LEFT JOIN calculations c ON f.calculation_id = c.id
            WHERE 1=1
        """
        
        params = []
        if favorite_type:
            query += " AND f.favorite_type = ?"
            params.append(favorite_type)
        
        query += " ORDER BY f.created_at DESC"
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_database_stats(self):
        """
        Veritabanı istatistiklerini getirir
        
        Returns:
            dict: İstatistikler
        """
        cursor = self.conn.cursor()
        
        stats = {}
        
        # Proje sayısı
        cursor.execute("SELECT COUNT(*) FROM projects")
        stats['project_count'] = cursor.fetchone()[0]
        
        # Hesaplama sayısı
        cursor.execute("SELECT COUNT(*) FROM calculations")
        stats['calculation_count'] = cursor.fetchone()[0]
        
        # AFAD dosya sayısı
        cursor.execute("SELECT COUNT(*) FROM afad_files")
        stats['afad_file_count'] = cursor.fetchone()[0]
        
        # Favori sayısı
        cursor.execute("SELECT COUNT(*) FROM favorites")
        stats['favorite_count'] = cursor.fetchone()[0]
        
        # En son proje
        cursor.execute("SELECT name, updated_at FROM projects ORDER BY updated_at DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            stats['latest_project'] = {'name': row[0], 'date': row[1]}
        
        return stats
    
    def cleanup_old_data(self, days_old=30):
        """
        Eski verileri temizler
        
        Args:
            days_old (int): Kaç gün öncesinden eski kabul edileceği
        """
        cursor = self.conn.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        cutoff_str = cutoff_date.isoformat()
        
        # Eski hesaplamaları sil (favorilerdeki hariç)
        cursor.execute("""
            DELETE FROM calculations 
            WHERE created_at < ? 
            AND id NOT IN (SELECT calculation_id FROM favorites WHERE calculation_id IS NOT NULL)
        """, (cutoff_str,))
        
        deleted_count = cursor.rowcount
        self.conn.commit()
        
        return deleted_count
    
    def export_to_json(self, output_path):
        """
        Tüm veritabanını JSON'a export eder
        
        Args:
            output_path (str): Çıktı dosya yolu
        """
        export_data = {
            'export_date': datetime.now().isoformat(),
            'version': '1.0',
            'projects': self.get_projects_list(limit=1000),
            'user_settings': {},
            'database_stats': self.get_database_stats()
        }
        
        # Kullanıcı ayarlarını ekle
        cursor = self.conn.cursor()
        cursor.execute("SELECT setting_key, setting_value FROM user_settings")
        for row in cursor.fetchall():
            export_data['user_settings'][row[0]] = row[1]
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    def close(self):
        """Veritabanı bağlantısını kapatır"""
        if self.conn:
            self.conn.close()
    
    def __del__(self):
        """Destructor - bağlantıyı kapat"""
        self.close() 