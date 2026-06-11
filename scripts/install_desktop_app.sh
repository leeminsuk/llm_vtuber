#!/bin/bash
# Open-LLM-VTuber 데스크톱 클라이언트 설치 (macOS arm64)
# Pet mode(투명 배경·항상 위 데스크톱 펫)는 웹이 아닌 데스크톱 앱 전용 기능이다.
# 설치 후: 서버(uv run run_server.py) 실행 → 데스크톱 앱 실행 → 좌측 상단 모드 메뉴 → Pet
set -euo pipefail

VERSION="${1:-1.2.1}"
URL="https://github.com/Open-LLM-VTuber/Open-LLM-VTuber-Web/releases/download/v${VERSION}/open-llm-vtuber-${VERSION}.dmg"
DMG="/tmp/ollv-desktop-${VERSION}.dmg"

echo "다운로드: $URL"
curl -L -o "$DMG" "$URL"

echo "마운트 및 설치..."
MOUNT_DIR=$(hdiutil attach "$DMG" -nobrowse | awk -F'\t' '/\/Volumes\//{print $NF}')
cp -R "$MOUNT_DIR"/*.app /Applications/
hdiutil detach "$MOUNT_DIR" -quiet

# 공증되지 않은 OSS 릴리스라 Gatekeeper 격리 해제 필요
xattr -dr com.apple.quarantine /Applications/open-llm-vtuber*.app 2>/dev/null || true

echo "설치 완료: /Applications/open-llm-vtuber-electron.app"
echo "서버를 켠 뒤 앱을 실행하고 모드 메뉴에서 Pet을 선택하세요."
