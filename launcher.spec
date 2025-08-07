# -*- mode: python ; coding: utf-8 -*-
import os
import sys

a = Analysis(
    ['main.py'],     # Script principal (punto de entrada)
    pathex=['.'],                # Rutas adicionales para buscar módulos
    binaries=[],              # Archivos binarios externos a incluir
    datas=[
        ('assets/i18n/*.json', 'assets/i18n'),
        ('assets/icons/*.ico', 'assets/icons'),
        ('assets/styles/*.qss', 'assets/styles'),
    ],                 # Archivos de datos (json, qss, imágenes, etc.)
    
    hiddenimports=['PyQt6.sip',
        'modules.excel.excel_widget', 
        'modules.flow2d.flow2d_widget',
        'modules.HidrogramasCv.HidrogramasCv_widget',
        ],         # Imports que PyInstaller no detecta automáticamente
    hookspath=[],             # Hooks personalizados
    hooksconfig={},           # Configuración de esos hooks
    runtime_hooks=[],         # Scripts que se ejecutan antes del main
    excludes=['tkinter'],              # Módulos que quieres excluir
    noarchive=False,          # True si no quieres usar archivo .pyz
    optimize=0,               # 0 = sin optimizar, 1 o 2 = optimizaciones
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,     # Binaries van al paso siguiente (COLLECT)
    name='MyFriendTGI',           # Nombre del ejecutable .exe
    debug=False,               # True para debug (muestra más info si falla)
    bootloader_ignore_signals=False,
    strip=False,               # True para eliminar símbolos (reduce tamaño)
    upx=True,                  # Usa UPX para comprimir el ejecutable
    console=True,              # True: se abre consola. False: solo ventana
    disable_windowed_traceback=False,
    argv_emulation=False,      # Para macOS (emular argumentos de arrastre)
    target_arch=None,          # Compilación cruzada
    codesign_identity=None,    # Para firmar (macOS)
    entitlements_file=None,    # También macOS
    icon='assets/icons/TGI.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TGI',
)
