#!/usr/bin/env python3
"""
Script para reparar os planos no banco de dados
Executar: python repair_planos.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Plano

def repair_planos():
    """Repara os planos no banco de dados"""
    with app.app_context():
        try:
            planos = Plano.query.all()
            print(f"🔧 Encontrados {len(planos)} planos para reparar")
            
            for plano in planos:
                print(f"\n📋 Plano: {plano.nome}")
                print(f"   Features original: {plano.features[:50]}...")
                
                # Se features estiver vazia, define padrões
                if not plano.features or len(plano.features.strip()) < 5:
                    if '100' in plano.nome:
                        plano.features = "Wi-Fi Grátis\nInstalação Grátis\nSuporte 24h\nFibra Óptica"
                    elif '200' in plano.nome:
                        plano.features = "Wi-Fi Grátis\nInstalação Grátis\nSuporte 24h\nFibra Óptica\nModem Incluso"
                    elif '400' in plano.nome:
                        plano.features = "Wi-Fi Grátis\nInstalação Grátis\nSuporte 24h\nFibra Óptica\nModem Incluso\nAntivírus"
                    else:
                        plano.features = "Wi-Fi Grátis\nInstalação Grátis\nSuporte 24h"
                    print(f"   ✅ Features corrigidas")
                
                # Corrige preço se necessário
                if '/' in str(plano.preco):
                    plano.preco = str(plano.preco).split('/')[0].strip()
                    print(f"   ✅ Preço corrigido: {plano.preco}")
                
                # Corrige velocidade se vazia
                if not plano.velocidade or plano.velocidade.strip() == '':
                    if '100' in plano.nome:
                        plano.velocidade = '100 Mbps'
                    elif '200' in plano.nome:
                        plano.velocidade = '200 Mbps'
                    elif '400' in plano.nome:
                        plano.velocidade = '400 Mbps'
                    print(f"   ✅ Velocidade corrigida: {plano.velocidade}")
            
            db.session.commit()
            print(f"\n🎉 Todos os planos foram reparados!")
            
        except Exception as e:
            print(f"❌ Erro: {e}")
            db.session.rollback()

if __name__ == '__main__':
    print("🚀 INICIANDO REPARO DE PLANOS")
    repair_planos()