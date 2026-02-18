
"""
Kayıt Çifti Eşleme (Pair Manager)
- loaded_earthquake_files ve processed_earthquake_data üzerinden X-Y bileşenlerini eşler.
- Heuristik: dosya adı/etiketlerinden {NS/EW, 000/090, X/Y, 1/2} çıkarımı + dt/uzunluk uyumu.
- Çıktı: [(ax, ay, dt, meta), ...] yapısı (ivme dizileri 'acceleration' alanından alınır).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple, Optional
import numpy as np
import re
from typing import Any
import os

# dt kovası için tolerans (µs)
DT_TOL_US = 2

# Yardımcı: orientation tespiti
_ORIENT_PATTERNS = [
    # Klasik yönler
    (r'(^|[^A-Za-z])NS([^A-Za-z]|$)', 'NS'),
    (r'(^|[^A-Za-z])SN([^A-Za-z]|$)', 'NS'),
    (r'(^|[^A-Za-z])EW([^A-Za-z]|$)', 'EW'),
    (r'(^|[^A-Za-z])WE([^A-Za-z]|$)', 'EW'),
    # Açı tabanlı
    (r'(^|[^0-9])000([^0-9]|$)', '000'),
    (r'(^|[^0-9])090([^0-9]|$)', '090'),
    (r'(^|[^0-9])180([^0-9]|$)', '180'),
    (r'(^|[^0-9])270([^0-9]|$)', '270'),
    # HMC varyantları
    (r'(^|[^A-Za-z0-9])HMC000([^A-Za-z0-9]|$)', '000'),
    (r'(^|[^A-Za-z0-9])HMC090([^A-Za-z0-9]|$)', '090'),
    (r'(^|[^A-Za-z0-9])HMC180([^A-Za-z0-9]|$)', '180'),
    (r'(^|[^A-Za-z0-9])HMC270([^A-Za-z0-9]|$)', '270'),
    # Kanal tabanlı
    (r'(^|[^A-Za-z0-9])HN1([^A-Za-z0-9]|$)', 'HN1'),
    (r'(^|[^A-Za-z0-9])HN2([^A-Za-z0-9]|$)', 'HN2'),
    (r'(^|[^A-Za-z0-9])H1([^A-Za-z0-9]|$)', 'H1'),
    (r'(^|[^A-Za-z0-9])H2([^A-Za-z0-9]|$)', 'H2'),
    # Doğrudan X/Y
    (r'(^|[^A-Za-z])X([^A-Za-z]|$)', 'X'),
    (r'(^|[^A-Za-z])Y([^A-Za-z]|$)', 'Y'),
]

def _detect_orientation(name: str) -> Optional[str]:
    name_up = name.upper()
    for pat, tag in _ORIENT_PATTERNS:
        if re.search(pat, name_up):
            return tag
    return None

def infer_axis(name: str) -> Optional[str]:
    """Dosya/ad etiketlerinden X/Y eksen tahmini.

    000/180/NS/X/H1/HN1 -> X
    090/270/EW/Y/H2/HN2 -> Y
    Aksi halde None
    """
    tag = _detect_orientation(name) or ''
    if tag in ('000','180','NS','X','H1','HN1'):
        return 'X'
    if tag in ('090','270','EW','Y','H2','HN2'):
        return 'Y'
    return None

def _base_key(name: str) -> str:
    """Eşleştirme anahtarı: yatay etiketleri (NS/EW, 000/090/180/270, H1/H2/HN1/HN2, HMCxxx) temizle."""
    s = str(name).upper()
    # Sonda gelen yön/kanal etiketlerini buda
    s = re.sub(r'(?:[._\-])HMC(?:000|090|180|270)(?=$)', '', s)
    s = re.sub(r'(?:^|[._\-])(000|090|180|270)(?=$)', '', s)
    s = re.sub(r'(?:^|[._\-])(NS|SN|EW|WE|X|Y|H1|H2|HN1|HN2)(?=$)', '', s)
    # PEER E* kanal kodları (ELC/EIC/ELN/EIN vb.) ve sonundaki 000/090/180/270 varyantlarını kaldır
    s = re.sub(r'(?:[._\-])?(?:E[LI][CN])(?:000|090|180|270)?(?=$)', '', s)
    # Sondaki saf 3-haneli açı (öncesinde harf olsa bile) kaldır
    s = re.sub(r'(000|090|180|270)(?=$)', '', s)
    s = re.sub(r'[._\-]+$', '', s)
    s = re.sub(r'[^A-Z0-9]+', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    return s

@dataclass
class Pair:
    name_x: str
    name_y: str
    time: np.ndarray
    ax: np.ndarray
    ay: np.ndarray
    dt: float
    meta: Dict

class PairManager:
    def __init__(self, get_loaded_records_callable):
        """
        get_loaded_records_callable: MainWindow içindeki loaded_earthquake_files listesini döndüren callable.
        Her eleman yapısı:
          {'name': display_name, 'processed_data': {'time':..., 'acceleration':..., 'units':{'acceleration': 'g' veya 'm/s²'}, ...}, ...}
        """
        self._get_loaded = get_loaded_records_callable
        # Manuel override: core_key -> {'X': name, 'Y': name}
        self._overrides: Dict[str, Dict[str, str]] = {}
        # Grup seçenekleri: core_key -> { 'crop_min': bool, 'swap_xy': bool }
        self._options: Dict[str, Dict[str, Any]] = {}

    # Eski group_id kullanılmıyor; core tabanlı ilerleniyor

    def set_option(self, core_key: str, option: str, value: Any) -> None:
        self._options.setdefault(core_key, {})[option] = value

    def get_option(self, core_key: str, option: str, default: Any = None) -> Any:
        return self._options.get(core_key, {}).get(option, default)

    @staticmethod
    def parse_group_id(group_id: str) -> Optional[Tuple[str, Optional[int]]]:
        """Desteklenen biçimler: 'core' veya 'core__dtb<bucket>'"""
        try:
            s = str(group_id)
            if '__dtb' in s:
                core, tail = s.split('__dtb', 1)
                bucket = int(tail) if tail else None
                return (core, bucket)
            return (s, None)
        except Exception:
            return None

    def get_group_records(self, group_id: str) -> List[Dict]:
        """Verilen group_id için kayıt listesini döndürür."""
        parsed = self.parse_group_id(group_id)
        if not parsed:
            return []
        core, bucket = parsed
        records = list(self._get_loaded() or [])
        groups = self._group_by_core_dt_bucket(records)
        if bucket is None:
            # core için tüm dt kovalarını birleştir
            out: List[Dict] = []
            for (c, b), grp in groups.items():
                if c == core:
                    out.extend(grp)
            return out
        return groups.get((core, int(bucket)), [])

    def _group_by_core_dt_bucket(self, records: Sequence[Dict]) -> Dict[tuple, List[Dict]]:
        """(core_key, dt_bucket) anahtarına göre kayıtları gruplar (N dikkate alınmaz)."""
        buckets: Dict[tuple, List[Dict]] = {}
        for rec in records:
            raw_name = str(rec.get('name') or rec.get('original_filename') or 'REC')
            stem = os.path.splitext(os.path.basename(raw_name))[0]
            core = _base_key(stem)
            pd = rec.get('processed_data', {}) or {}
            # dt hesapla
            dt = 0.0
            try:
                dt = float(pd.get('params', {}).get('time_step', 0.0) or 0.0)
            except Exception:
                dt = 0.0
            if not dt:
                try:
                    t = np.asarray(pd.get('time'), dtype=float)
                    if t.size >= 2:
                        dt = float(np.median(np.diff(t)))
                except Exception:
                    dt = 0.0
            # NPTS meta varsa onu da oku (eşleştirme uyarıları için faydalı)
            try:
                npts = int(pd.get('npts')) if 'npts' in pd else int(len(pd.get('acceleration') or []))
            except Exception:
                npts = int(len(pd.get('acceleration') or []))
            dt_us = int(round(max(0.0, float(dt)) * 1e6))
            tol = int(max(1, DT_TOL_US))
            dt_bucket = (dt_us // (2 * tol)) if tol > 0 else dt_us
            key = (core, dt_bucket)
            # Kayda referans meta notu ekle (istasyon/azimut varsa)
            try:
                meta_add = {}
                if 'station' in pd:
                    meta_add['station'] = pd.get('station')
                if 'azimuth_deg' in pd:
                    meta_add['azimuth_deg'] = pd.get('azimuth_deg')
                if meta_add:
                    rec.setdefault('pair_meta', {}).update(meta_add)
                rec.setdefault('pair_meta', {})['npts'] = npts
            except Exception:
                pass
            buckets.setdefault(key, []).append(rec)
        return buckets

    def list_groups(self, by_dt_bucket: bool = False) -> List[str]:
        """Mevcut yüklemelerden grup kimliklerini döndürür.

        Args:
            by_dt_bucket: True ise her farklı dt kovası ayrı grup olarak döner
                          ("core__dtb<bucket>"). False ise yalnızca benzersiz core anahtarları.
        Returns:
            List[str]: Grup kimlikleri (core veya core__dtbX)
        """
        try:
            records = list(self._get_loaded() or [])
            groups = self._group_by_core_dt_bucket(records)
            if by_dt_bucket:
                out: List[str] = []
                for (core, bucket) in groups.keys():
                    try:
                        out.append(f"{core}__dtb{int(bucket)}")
                    except Exception:
                        out.append(f"{core}")
                # Benzersiz ve sıralı
                return sorted(list(dict.fromkeys(out)))
            else:
                cores = {core for (core, _b) in groups.keys()}
                return sorted(list(cores))
        except Exception:
            return []

    def _group_by_base(self, records: Sequence[Dict]) -> Dict[str, List[Dict]]:
        groups: Dict[str, List[Dict]] = {}
        for rec in records:
            nm = rec.get('name') or rec.get('original_filename') or 'REC'
            key = _base_key(str(nm))
            groups.setdefault(key, []).append(rec)
        return groups

    def _try_pair_group(self, group: List[Dict]) -> List[Pair]:
        pairs: List[Pair] = []
        if len(group) < 2:
            return pairs
        # Önce olası X/Y ayrımı
        candidates = list(group)
        used = set()
        # İlk pass: etiket eşleşmesine göre
        for i in range(len(candidates)):
            if i in used: 
                continue
            n1 = str(candidates[i]['name'])
            o1 = _detect_orientation(n1) or ''
            t1 = candidates[i]['processed_data'].get('time')
            a1 = candidates[i]['processed_data'].get('acceleration')
            if t1 is None or a1 is None: 
                continue
            dt1 = float(np.median(np.diff(np.asarray(t1).astype(float)))) if len(t1) > 1 else None
            best_j = None
            best_score = -1.0
            for j in range(i+1, len(candidates)):
                if j in used: 
                    continue
                n2 = str(candidates[j]['name'])
                o2 = _detect_orientation(n2) or ''
                t2 = candidates[j]['processed_data'].get('time')
                a2 = candidates[j]['processed_data'].get('acceleration')
                if t2 is None or a2 is None: 
                    continue
                dt2 = float(np.median(np.diff(np.asarray(t2).astype(float)))) if len(t2) > 1 else None
                # Heuristik skor: farklı orientation + benzer dt + benzer uzunluk
                score = 0.0
                if o1 and o2 and o1 != o2:
                    score += 2.0
                if dt1 is not None and dt2 is not None:
                    rel = abs(dt1 - dt2) / max(1e-9, max(dt1, dt2))
                    score += max(0.0, 1.0 - rel*10)  # rel 0.0 → +1, rel 0.1 → +0
                # uzunluk uyuşması
                L1, L2 = len(t1), len(t2)
                relL = abs(L1 - L2) / max(1, max(L1, L2))
                score += max(0.0, 1.0 - relL*10)
                if score > best_score:
                    best_score = score
                    best_j = j
            if best_j is not None and best_score >= 1.0:  # eşik
                used.add(i); used.add(best_j)
                r1, r2 = candidates[i], candidates[best_j]
                # X/Y sırasını tahmin et (000/180/NS/H1/HN1 → X; 090/270/EW/H2/HN2 → Y)
                n1u = str(r1['name']).upper()
                n2u = str(r2['name']).upper()
                ax1 = infer_axis(n1u)
                ax2 = infer_axis(n2u)
                if ax1 == 'X' and ax2 == 'Y':
                    rrX, rrY = r1, r2
                elif ax1 == 'Y' and ax2 == 'X':
                    rrX, rrY = r2, r1
                else:
                    prefer_x_first = any(tag in n1u for tag in ['000','180','X','NS','H1','HN1']) or any(tag in n2u for tag in ['090','270','Y','EW','H2','HN2'])
                    rrX, rrY = (r1, r2) if prefer_x_first else (r2, r1)
                t = np.asarray(rrX['processed_data']['time']).astype(float)
                ax = np.asarray(rrX['processed_data']['acceleration']).astype(float)
                ay = np.asarray(rrY['processed_data']['acceleration']).astype(float)
                dt = float(np.median(np.diff(t))) if len(t) > 1 else rrX['processed_data'].get('params',{}).get('time_step', 0.01)
                event_id = _base_key(str(rrX.get('original_filename') or rrX.get('name')))  # basitleştirilmiş
                meta = {
                    'event_id': event_id,
                    'name_x': str(rrX['name']),
                    'name_y': str(rrY['name']),
                    'units': {
                        'acceleration_x': rrX['processed_data'].get('units',{}).get('acceleration','g'),
                        'acceleration_y': rrY['processed_data'].get('units',{}).get('acceleration','g'),
                    }
                }
                pairs.append(Pair(rrX['name'], rrY['name'], t, ax, ay, dt, meta))
        return pairs

    # ---------------- Manuel eşleştirme desteği ----------------
    def suggest_pairs(self) -> Tuple[Dict[str, Dict[str, str]], Dict[str, Dict]]:
        """Core anahtarlarına göre önerilen X/Y seçimlerini ve ad->kayıt haritasını döndürür.

        Returns: (suggestions, name_to_record)
        suggestions: { core_key: {'X': name?, 'Y': name?} }
        name_to_record: { name: record_dict }
        """
        records = list(self._get_loaded() or [])
        groups = self._group_by_core_dt_bucket(records)
        name_map: Dict[str, Dict] = {str(r.get('name')): r for r in records if r.get('name')}
        suggestions: Dict[str, Dict[str, str]] = {}
        # core -> tüm kovaların birleşimi
        core_to_group: Dict[str, List[Dict]] = {}
        for (core, _bucket), group in groups.items():
            core_to_group.setdefault(core, []).extend(group)
        for core, group in core_to_group.items():
            x_name: Optional[str] = None
            y_name: Optional[str] = None
            xs = [g for g in group if (_detect_orientation(str(g.get('name') or '')) or '') in ('NS','000','X')]
            ys = [g for g in group if (_detect_orientation(str(g.get('name') or '')) or '') in ('EW','090','Y')]
            if xs:
                x_name = str(xs[0].get('name'))
            if ys:
                y_name = str(ys[0].get('name'))
            if (x_name is None or y_name is None) and len(group) >= 2:
                n1 = str(group[0].get('name'))
                n2 = str(group[1].get('name'))
                x_name = x_name or n1
                y_name = y_name or n2
            if x_name or y_name:
                suggestions[core] = {}
                if x_name:
                    suggestions[core]['X'] = x_name
                if y_name:
                    suggestions[core]['Y'] = y_name
        return suggestions, name_map

    def set_override(self, core_key: str, axis: str, record_name: Optional[str]) -> None:
        axis_up = (axis or '').upper()
        if axis_up not in ('X','Y'):
            return
        if record_name is None:
            if core_key in self._overrides and axis_up in self._overrides[core_key]:
                self._overrides[core_key].pop(axis_up, None)
                if not self._overrides[core_key]:
                    self._overrides.pop(core_key, None)
            return
        self._overrides.setdefault(core_key, {})[axis_up] = str(record_name)

    def get_pairs(self) -> List[Tuple[np.ndarray, np.ndarray, float, Dict]]:
        """(ax, ay, dt, meta) listesi döndürür; ax/ay dizileri NumPy array'dir."""
        records = list(self._get_loaded() or [])
        name_map: Dict[str, Dict] = {str(r.get('name')): r for r in records if r.get('name')}
        all_pairs: List[Tuple[np.ndarray, np.ndarray, float, Dict]] = []
        suggestions, _ = self.suggest_pairs()
        merged: Dict[str, Dict[str, str]] = dict(suggestions)
        for core, sel in self._overrides.items():
            merged.setdefault(core, {})
            merged[core].update(sel)
        for core, sel in merged.items():
            if 'X' in sel and 'Y' in sel and sel['X'] in name_map and sel['Y'] in name_map:
                rx = name_map[sel['X']]
                ry = name_map[sel['Y']]
                t = np.asarray(rx['processed_data']['time']).astype(float)
                ax = np.asarray(rx['processed_data']['acceleration']).astype(float)
                ay = np.asarray(ry['processed_data']['acceleration']).astype(float)
                dt = float(np.median(np.diff(t))) if len(t) > 1 else rx['processed_data'].get('params',{}).get('time_step', 0.01)
                if bool(self.get_option(core, 'swap_xy', False)):
                    ax, ay = ay, ax
                if bool(self.get_option(core, 'crop_min', True)):
                    L = int(min(len(ax), len(ay), len(t))) if len(t) else int(min(len(ax), len(ay)))
                    if L > 0:
                        ax = ax[:L]
                        ay = ay[:L]
                        if len(t):
                            t = t[:L]
                # Grup adını kullanıcı dostu hale getir
                display_group_name = core
                if core.startswith('MANUAL_'):
                    display_group_name = core.replace('MANUAL_', '').replace('_', ' ')
                elif core.startswith('NEW_GROUP_'):
                    display_group_name = core.replace('NEW_GROUP_', '').replace('_', ' ')
                
                meta = {
                    'event_id': core,
                    'group_name': display_group_name,
                    'name_x': str(rx['name']),
                    'name_y': str(ry['name']),
                    'group_id': core,
                }
                meta['pair_name'] = f"{meta['name_x']} | {meta['name_y']}"
                all_pairs.append((ax, ay, dt, meta))
        return all_pairs
