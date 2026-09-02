#!/usr/bin/env python
"""
Script de Migración e Ingesta Completa de Datos Softtrade en Mercotruck.
Ejecuta el procesamiento de:
- HISTORICO_MERCOTRUCK.xlsx
- SOFTTRADE_IMPO.xlsx / SOFTTRADE_EXPO.xlsx (Histórico 2025)
- Carpeta docs/softrade/*.xlsx (Archivos bimestrales 2026)
"""
import sys
import os
import time

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.etl.pipeline import run_etl_pipeline

def main():
    print("=" * 60)
    print(" 🚀 INICIANDO MIGRACIÓN E INGESTA DE DATOS DE MERCOTRUCK ")
    print("=" * 60)
    start_time = time.time()

    try:
        run_etl_pipeline(clear_existing=True)
        elapsed = time.time() - start_time
        print("\n" + "=" * 60)
        print(f" 🎉 MIGRACIÓN COMPLETADA CON ÉXITO EN {elapsed:.2f} SEGUNDOS")
        print("=" * 60)
    except Exception as e:
        print("\n" + "=" * 60)
        print(f" ❌ ERROR DURANTE LA MIGRACIÓN: {e}")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()
