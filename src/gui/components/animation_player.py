"""
Time history animasyon oynatıcısı bileşeni
"""

import tkinter as tk
from tkinter import ttk
import numpy as np
import time
from typing import Callable, Dict, Any
import threading

class AnimationPlayer:
    """Time history animasyon oynatıcısı sınıfı"""
    
    def __init__(self, parent_frame):
        """
        Args:
            parent_frame: Ana çerçeve
        """
        self.parent_frame = parent_frame
        
        # Animasyon durumu
        self.is_playing = False
        self.is_paused = False
        self.current_frame = 0
        self.total_frames = 0
        self.playback_speed = 1.0  # 1x normal hız
        self.loop_enabled = False
        
        # Veri
        self.time_data = None
        self.animation_data = None
        self.fps = 30  # Frame per second
        
        # Callback fonksiyonları
        self.frame_callback = None  # Her frame'de çağrılır
        self.play_callback = None   # Play başladığında
        self.pause_callback = None  # Pause'da
        self.stop_callback = None   # Stop'ta
        
        # Threading
        self.animation_thread = None
        self.stop_animation_flag = False
        
        # GUI bileşenleri
        self.control_frame = None
        self.progress_frame = None
        self.info_frame = None
        
        # Kontrol widget'ları
        self.play_button = None
        self.pause_button = None
        self.stop_button = None
        self.progress_var = None
        self.progress_scale = None
        self.speed_var = None
        self.loop_var = None
        self.time_label_var = None
        self.frame_label_var = None
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Widget'ları oluşturur"""
        # Ana kontrol çerçevesi
        self.control_frame = ttk.LabelFrame(self.parent_frame, text="🎬 Animasyon Kontrolleri", padding=10)
        self.control_frame.pack(fill="x", padx=5, pady=5)
        
        # Oynatma kontrolleri
        controls_row1 = ttk.Frame(self.control_frame)
        controls_row1.pack(fill="x", pady=(0, 10))
        
        # Play/Pause/Stop butonları
        self.play_button = ttk.Button(
            controls_row1, 
            text="▶️ Play",
            command=self._play_animation,
            width=10
        )
        self.play_button.pack(side="left", padx=2)
        
        self.pause_button = ttk.Button(
            controls_row1,
            text="⏸️ Pause",
            command=self._pause_animation,
            width=10,
            state="disabled"
        )
        self.pause_button.pack(side="left", padx=2)
        
        self.stop_button = ttk.Button(
            controls_row1,
            text="⏹️ Stop",
            command=self._stop_animation,
            width=10,
            state="disabled"
        )
        self.stop_button.pack(side="left", padx=2)
        
        # Hız kontrolü
        speed_frame = ttk.Frame(controls_row1)
        speed_frame.pack(side="right", padx=10)
        
        ttk.Label(speed_frame, text="Hız:").pack(side="left")
        self.speed_var = tk.DoubleVar(value=1.0)
        speed_scale = ttk.Scale(
            speed_frame, 
            from_=0.1, to=5.0, 
            orient="horizontal",
            length=100,
            variable=self.speed_var,
            command=self._on_speed_change
        )
        speed_scale.pack(side="left", padx=5)
        self.speed_label = ttk.Label(speed_frame, text="1.0x")
        self.speed_label.pack(side="left", padx=5)
        
        # Loop checkbox
        self.loop_var = tk.BooleanVar()
        loop_check = ttk.Checkbutton(
            controls_row1,
            text="🔄 Loop",
            variable=self.loop_var,
            command=self._on_loop_change
        )
        loop_check.pack(side="right", padx=10)
        
        # Progress bar ve zaman kontrolü
        self.progress_frame = ttk.Frame(self.control_frame)
        self.progress_frame.pack(fill="x", pady=(0, 10))
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_scale = ttk.Scale(
            self.progress_frame,
            from_=0, to=100,
            orient="horizontal",
            variable=self.progress_var,
            command=self._on_progress_change
        )
        self.progress_scale.pack(fill="x", padx=(0, 10))
        
        # Zaman ve frame bilgileri
        self.info_frame = ttk.Frame(self.control_frame)
        self.info_frame.pack(fill="x")
        
        # Zaman bilgisi
        time_info_frame = ttk.Frame(self.info_frame)
        time_info_frame.pack(side="left")
        
        ttk.Label(time_info_frame, text="Zaman:").pack(side="left")
        self.time_label_var = tk.StringVar(value="0.000 / 0.000 s")
        ttk.Label(time_info_frame, textvariable=self.time_label_var, 
                 font=('Courier New', 9)).pack(side="left", padx=5)
        
        # Frame bilgisi
        frame_info_frame = ttk.Frame(self.info_frame)
        frame_info_frame.pack(side="right")
        
        ttk.Label(frame_info_frame, text="Frame:").pack(side="left")
        self.frame_label_var = tk.StringVar(value="0 / 0")
        ttk.Label(frame_info_frame, textvariable=self.frame_label_var,
                 font=('Courier New', 9)).pack(side="left", padx=5)
        
        # Frame navigation butonları
        nav_frame = ttk.Frame(self.info_frame)
        nav_frame.pack()
        
        ttk.Button(nav_frame, text="⏮️", command=self._first_frame, width=3).pack(side="left", padx=1)
        ttk.Button(nav_frame, text="⏪", command=self._prev_frame, width=3).pack(side="left", padx=1)
        ttk.Button(nav_frame, text="⏩", command=self._next_frame, width=3).pack(side="left", padx=1)
        ttk.Button(nav_frame, text="⏭️", command=self._last_frame, width=3).pack(side="left", padx=1)
    
    def set_data(self, time_data: np.ndarray, animation_data: Dict[str, np.ndarray]):
        """
        Animasyon verilerini ayarlar
        
        Args:
            time_data: Zaman serisi
            animation_data: Animasyon verileri dictionary'si
        """
        self.time_data = time_data
        self.animation_data = animation_data
        
        if len(time_data) > 0:
            self.total_frames = len(time_data)
            self.current_frame = 0
            
            # Progress bar'ı güncelle
            self.progress_scale.configure(to=self.total_frames - 1)
            
            # Bilgi labellarını güncelle
            self._update_info_labels()
            
            # Play butonunu etkinleştir
            self.play_button.configure(state="normal")
            
            print(f"🎬 Animasyon verisi ayarlandı: {self.total_frames} frame")
        else:
            self._disable_controls()
    
    def set_frame_callback(self, callback: Callable[[int, float, Dict[str, Any]], None]):
        """
        Frame callback fonksiyonunu ayarlar
        
        Args:
            callback: Her frame'de çağrılacak fonksiyon (frame_index, time_value, data_values)
        """
        self.frame_callback = callback
    
    def set_play_callback(self, callback: Callable[[], None]):
        """Play callback fonksiyonunu ayarlar"""
        self.play_callback = callback
    
    def set_pause_callback(self, callback: Callable[[], None]):
        """Pause callback fonksiyonunu ayarlar"""
        self.pause_callback = callback
    
    def set_stop_callback(self, callback: Callable[[], None]):
        """Stop callback fonksiyonunu ayarlar"""
        self.stop_callback = callback
    
    def _play_animation(self):
        """Animasyonu başlatır"""
        if not self.time_data is None and len(self.time_data) > 0:
            if not self.is_playing:
                self.is_playing = True
                self.is_paused = False
                self.stop_animation_flag = False
                
                # Buton durumlarını güncelle
                self.play_button.configure(state="disabled")
                self.pause_button.configure(state="normal")
                self.stop_button.configure(state="normal")
                
                # Play callback
                if self.play_callback:
                    self.play_callback()
                
                # Animasyon thread'ini başlat
                self.animation_thread = threading.Thread(target=self._animation_loop, daemon=True)
                self.animation_thread.start()
                
                print("▶️ Animasyon başlatıldı")
    
    def _pause_animation(self):
        """Animasyonu duraklatır"""
        if self.is_playing and not self.is_paused:
            self.is_paused = True
            
            # Buton durumlarını güncelle
            self.play_button.configure(state="normal", text="▶️ Resume")
            self.pause_button.configure(state="disabled")
            
            # Pause callback
            if self.pause_callback:
                self.pause_callback()
            
            print("⏸️ Animasyon duraklatıldı")
        elif self.is_paused:
            # Resume
            self.is_paused = False
            self.play_button.configure(state="disabled", text="▶️ Play")
            self.pause_button.configure(state="normal")
            print("▶️ Animasyon devam ettiriliyor")
    
    def _stop_animation(self):
        """Animasyonu durdurur"""
        if self.is_playing:
            self.stop_animation_flag = True
            self.is_playing = False
            self.is_paused = False
            self.current_frame = 0
            
            # Buton durumlarını güncelle
            self.play_button.configure(state="normal", text="▶️ Play")
            self.pause_button.configure(state="disabled")
            self.stop_button.configure(state="disabled")
            
            # Progress'i sıfırla
            self.progress_var.set(0)
            self._update_info_labels()
            
            # Stop callback
            if self.stop_callback:
                self.stop_callback()
            
            # İlk frame'i göster
            self._show_frame(0)
            
            print("⏹️ Animasyon durduruldu")
    
    def _animation_loop(self):
        """Animasyon döngüsü (thread'de çalışır)"""
        try:
            frame_duration = 1.0 / self.fps  # Saniye cinsinden frame süresi
            
            while self.is_playing and not self.stop_animation_flag:
                if not self.is_paused:
                    # Frame'i göster
                    self.parent_frame.after(0, lambda f=self.current_frame: self._show_frame(f))
                    
                    # Sonraki frame'e geç
                    self.current_frame += 1
                    
                    # Son frame'e ulaştıysak
                    if self.current_frame >= self.total_frames:
                        if self.loop_enabled:
                            self.current_frame = 0  # Başa dön
                        else:
                            # Animasyonu durdur
                            self.parent_frame.after(0, self._stop_animation)
                            break
                
                # Hız ayarına göre bekle
                adjusted_duration = frame_duration / self.playback_speed
                time.sleep(adjusted_duration)
                
        except Exception as e:
            print(f"❌ Animasyon döngüsü hatası: {e}")
            self.parent_frame.after(0, self._stop_animation)
    
    def _show_frame(self, frame_index: int):
        """Belirtilen frame'i gösterir"""
        try:
            if self.time_data is None or frame_index >= len(self.time_data):
                return
            
            # Mevcut frame'i güncelle
            self.current_frame = frame_index
            
            # Progress bar'ı güncelle
            self.progress_var.set(frame_index)
            
            # Bilgi labellarını güncelle
            self._update_info_labels()
            
            # Frame callback'i çağır
            if self.frame_callback:
                time_value = self.time_data[frame_index]
                data_values = {}
                
                # Animasyon verilerinden mevcut frame'in değerlerini al
                if self.animation_data:
                    for key, data_array in self.animation_data.items():
                        if frame_index < len(data_array):
                            data_values[key] = data_array[frame_index]
                
                self.frame_callback(frame_index, time_value, data_values)
                
        except Exception as e:
            print(f"❌ Frame gösterim hatası: {e}")
    
    def _update_info_labels(self):
        """Bilgi labellarını günceller"""
        try:
            if self.time_data is not None and len(self.time_data) > 0:
                current_time = self.time_data[self.current_frame] if self.current_frame < len(self.time_data) else 0
                total_time = self.time_data[-1] if len(self.time_data) > 0 else 0
                
                self.time_label_var.set(f"{current_time:.3f} / {total_time:.3f} s")
                self.frame_label_var.set(f"{self.current_frame + 1} / {self.total_frames}")
            else:
                self.time_label_var.set("0.000 / 0.000 s")
                self.frame_label_var.set("0 / 0")
        except Exception as e:
            print(f"❌ Bilgi güncelleme hatası: {e}")
    
    def _on_speed_change(self, value):
        """Hız değiştiğinde çağrılır"""
        try:
            self.playback_speed = float(value)
            self.speed_label.configure(text=f"{self.playback_speed:.1f}x")
            print(f"🏃 Animasyon hızı: {self.playback_speed:.1f}x")
        except Exception as e:
            print(f"❌ Hız değiştirme hatası: {e}")
    
    def _on_loop_change(self):
        """Loop ayarı değiştiğinde çağrılır"""
        self.loop_enabled = self.loop_var.get()
        status = "açık" if self.loop_enabled else "kapalı"
        print(f"🔄 Loop modu: {status}")
    
    def _on_progress_change(self, value):
        """Progress bar değiştiğinde çağrılır (manuel scrubbing)"""
        try:
            if not self.is_playing:  # Sadece oynatma durdurulmuşken manuel kontrol
                frame_index = int(float(value))
                if 0 <= frame_index < self.total_frames:
                    self._show_frame(frame_index)
        except Exception as e:
            print(f"❌ Progress değiştirme hatası: {e}")
    
    def _first_frame(self):
        """İlk frame'e gider"""
        if not self.is_playing:
            self._show_frame(0)
    
    def _prev_frame(self):
        """Önceki frame'e gider"""
        if not self.is_playing and self.current_frame > 0:
            self._show_frame(self.current_frame - 1)
    
    def _next_frame(self):
        """Sonraki frame'e gider"""
        if not self.is_playing and self.current_frame < self.total_frames - 1:
            self._show_frame(self.current_frame + 1)
    
    def _last_frame(self):
        """Son frame'e gider"""
        if not self.is_playing:
            self._show_frame(self.total_frames - 1)
    
    def _disable_controls(self):
        """Kontrolleri devre dışı bırakır"""
        self.play_button.configure(state="disabled")
        self.pause_button.configure(state="disabled")
        self.stop_button.configure(state="disabled")
        self.progress_scale.configure(state="disabled")
    
    def get_current_frame(self) -> int:
        """Mevcut frame index'ini döndürür"""
        return self.current_frame
    
    def get_current_time(self) -> float:
        """Mevcut zamanı döndürür"""
        if self.time_data is not None and self.current_frame < len(self.time_data):
            return self.time_data[self.current_frame]
        return 0.0
    
    def is_animation_playing(self) -> bool:
        """Animasyonun oynatılıp oynatılmadığını döndürür"""
        return self.is_playing
    
    def set_fps(self, fps: int):
        """FPS ayarlar"""
        self.fps = max(1, min(60, fps))  # 1-60 FPS arası
        print(f"🎬 FPS ayarlandı: {self.fps}")
    
    def jump_to_time(self, target_time: float):
        """Belirtilen zamana atlar"""
        if self.time_data is not None:
            # En yakın frame'i bul
            time_diffs = np.abs(self.time_data - target_time)
            closest_frame = np.argmin(time_diffs)
            
            if not self.is_playing:
                self._show_frame(closest_frame)
            else:
                self.current_frame = closest_frame
    
    def jump_to_frame(self, target_frame: int):
        """Belirtilen frame'e atlar"""
        if 0 <= target_frame < self.total_frames:
            if not self.is_playing:
                self._show_frame(target_frame)
            else:
                self.current_frame = target_frame