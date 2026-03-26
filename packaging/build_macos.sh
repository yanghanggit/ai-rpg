#!/usr/bin/env bash
# packaging/build_macos.sh
#
# 构建 macOS AI-RPG-Client.app
#
# 使用方法（在项目根目录）：
#   make client-build
# 或直接：
#   bash packaging/build_macos.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PACKAGING_DIR="$PROJECT_ROOT/packaging"
DIST_DIR="$PROJECT_ROOT/dist/client"
BUILD_DIR="$PROJECT_ROOT/build/client"
APP_NAME="AI-RPG-Client"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
APP_MACOS="$APP_BUNDLE/Contents/MacOS"
APP_RESOURCES="$APP_BUNDLE/Contents/Resources"

echo "🔧 AI RPG Client macOS 构建脚本"
echo "================================================"

# ── Step 1: 初始化 packaging/ 的 uv 环境 ──────────────────────────────────
echo ""
echo "📦 Step 1: 设置 packaging/ 的独立 uv 环境..."
cd "$PACKAGING_DIR"
uv sync
echo "✅ 依赖安装完成"

# ── Step 2: 运行 PyInstaller ───────────────────────────────────────────────
echo ""
echo "🏗️  Step 2: 运行 PyInstaller..."
uv run pyinstaller game_client.spec \
    --distpath "$DIST_DIR/pyinstaller_out" \
    --workpath "$BUILD_DIR" \
    --noconfirm
echo "✅ PyInstaller 构建完成"

# ── Step 3: 组装 .app bundle ─────────────────────────────────────────────
echo ""
echo "🗂️  Step 3: 组装 .app bundle..."
rm -rf "$APP_BUNDLE"
mkdir -p "$APP_MACOS"
mkdir -p "$APP_RESOURCES"

# 复制 PyInstaller 生成的二进制到 .app 内部
cp "$DIST_DIR/pyinstaller_out/game_client" "$APP_MACOS/game_client"

# 复制 launcher 脚本作为 .app 的主入口
cp "$PACKAGING_DIR/launcher.sh" "$APP_MACOS/$APP_NAME"
chmod +x "$APP_MACOS/$APP_NAME"

# 写 Info.plist
cat > "$APP_BUNDLE/Contents/Info.plist" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>AI RPG Client</string>
    <key>CFBundleExecutable</key>
    <string>$APP_NAME</string>
    <key>CFBundleIdentifier</key>
    <string>com.ai-rpg.client</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleVersion</key>
    <string>0.1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>0.1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST_EOF

echo "✅ .app bundle 组装完成"

# ── Step 4: 输出报告 ────────────────────────────────────────────────────
echo ""
echo "================================================"
echo "🎉 构建成功！"
echo ""
echo "📦 输出路径: $APP_BUNDLE"
APP_SIZE=$(du -sh "$APP_BUNDLE" | cut -f1)
echo "📏 App 体积: $APP_SIZE"
echo ""
echo "📤 分发方法:"
echo "   右键 → 压缩 → 发送 AI-RPG-Client.zip 给同事"
echo "   同事双击 .app → 弹出终端窗口 → 游戏 TUI 启动"
echo ""
echo "⚠️  注意：首次运行可能被 Gatekeeper 拦截，同事需要："
echo "   右键 → 打开 → 点击「打开」绕过安全提示"
