"""
テスト共通フィクスチャ
=====================
backend/ ディレクトリを sys.path に追加することで、
bridge.py が `from scenes import ...` のような相対インポートで
動作できるようにする。
"""

import sys
from pathlib import Path

# backend/ を sys.path に追加（bridge.py の bare import に対応）
sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))
