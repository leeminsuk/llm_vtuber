#!/bin/bash
# 데스크톱 앱(Electron)에 캐릭터 퀵스위치 칩 바를 주입한다.
#
# 데스크톱 앱은 프론트엔드를 app.asar에 번들하므로 서버의 index.html 주입이
# 닿지 않는다. 이 스크립트는 asar를 풀어 renderer/index.html에
# web_tool/quickswitch.js를 인라인으로 심고 다시 패킹한 뒤 ad-hoc 재서명한다.
# 멱등: 이미 패치된 앱이면 그대로 종료. 앱을 업데이트하면 다시 실행하면 된다.
#
# 사용법: bash scripts/patch_desktop_app.sh [앱 경로]
set -euo pipefail

APP="${1:-/Applications/open-llm-vtuber-electron.app}"
ASAR="$APP/Contents/Resources/app.asar"
JS="$(dirname "$0")/../web_tool/quickswitch.js"
WORK="$(mktemp -d /tmp/ollv_asar.XXXXXX)"
MARKER="<!-- llm_vtuber quickswitch -->"

[ -f "$ASAR" ] || { echo "app.asar 없음: $ASAR"; exit 1; }
[ -f "$JS" ] || { echo "quickswitch.js 없음: $JS"; exit 1; }

echo "asar 추출 중..."
npx -y @electron/asar extract "$ASAR" "$WORK"

INDEX="$WORK/out/renderer/index.html"
[ -f "$INDEX" ] || { echo "renderer index.html 없음"; exit 1; }

if grep -q "llm_vtuber quickswitch" "$INDEX"; then
    echo "이미 패치됨 — 종료"
    rm -rf "$WORK"
    exit 0
fi

echo "quickswitch 인라인 주입..."
MARKER="$MARKER" JS="$JS" INDEX="$INDEX" python3 - <<'PYEOF'
import os

index = os.environ["INDEX"]
with open(os.environ["JS"], encoding="utf-8") as f:
    js = f.read()
with open(index, encoding="utf-8") as f:
    html = f.read()

inline = f'{os.environ["MARKER"]}\n    <script>\n{js}\n    </script>\n    '
marker = '<script type="module"'
assert marker in html, "module script tag not found"
html = html.replace(marker, inline + marker, 1)
with open(index, "w", encoding="utf-8") as f:
    f.write(html)
print("injected", len(js), "bytes")
PYEOF

echo "asar 재패킹..."
npx -y @electron/asar pack "$WORK" "$ASAR"
rm -rf "$WORK"

echo "ad-hoc 재서명 (번들 수정으로 기존 서명 무효화됨)..."
codesign --force --deep -s - "$APP" 2>/dev/null || true

echo "완료. 앱을 재시작하면 상단에 캐릭터 칩 바가 나타난다."
