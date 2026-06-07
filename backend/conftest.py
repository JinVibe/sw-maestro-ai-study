import sys
from pathlib import Path

# repo 루트(ai 패키지)와 backend(app 패키지)를 import 경로에 추가
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
