# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    hiddenimports=[
        # PySide6 core (bắt buộc)
        'PySide6.QtSvg',
        'PySide6.QtXml',
    ],
    excludes=[
        # ===== Qt RẤT NẶNG – KHÔNG DÙNG =====
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineQuick',
        'PySide6.QtWebEngine',

        'PySide6.QtCharts',
        'PySide6.QtChartsWidgets',

        'PySide6.Qt3DCore',
        'PySide6.Qt3DRender',
        'PySide6.Qt3DInput',
        'PySide6.Qt3DLogic',
        'PySide6.Qt3DExtras',

        # ===== QML / Quick (không dùng) =====
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',

        # ===== Multimedia =====
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',

        'PySide6.QtSql',
        'PySide6.QtTest',

        # ===== Bluetooth / NFC =====
        'PySide6.QtBluetooth',
        'PySide6.QtNfc',

        # ===== Python libs không dùng =====
        'tkinter',
        'pytest',
        'unittest',
        'pydoc',
        'doctest',
        'email',
        'http',
        'xmlrpc',
    ],
    noarchive=True,
)


pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)


exe = EXE(
    pyz,
    a.scripts,
	a.binaries,
	a.zipfiles,
	[],
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    uac_admin=True,
    icon='logo.ico'
)