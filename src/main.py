# main.py (arquivo principal para o Render)
import sys
import os

# Adicionar o diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import json
import time
import threading
import traceback
from datetime import datetime
import io
import os
from playwright.sync_api import sync_playwright

# Criar a aplicação Flask
application = Flask(__name__)
app = application  # Alias para compatibilidade

# Configuração global para armazenar os resultados da busca
search_results = []
search_params = {}
search_status = {
    "is_running": False,
    "progress": 0,
    "message": "",
    "error": None,
    "total_found": 0
}

def fast_extract(page, selectors):
    """Extração ultra-rápida com múltiplos seletores CSS."""
    for selector in selectors:
        try:
            element = page.locator(selector).first
            if element.count() > 0:
                text = element.inner_text(timeout=2000).strip()
                if text:
                    return text
        except:
            continue
    return "N/A"

def scrape_google_maps(search_query, max_results):
    """Função otimizada para velocidade máxima - apenas dados essenciais."""
    global search_status
    
    results = []
    
    with sync_playwright() as p:
        search_status["progress"] = 15
        search_status["message"] = "Iniciando navegador..."
        
        # Configuração mínima para máxima velocidade
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-images',
                '--disable-javascript',
                '--disable-plugins',
                '--disable-extensions',
                '--disable-gpu',
                '--no-first-run'
            ]
        )
        
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            viewport={'width': 1280, 'height': 720}
        )
        page = context.new_page()
        
        # Bloquear recursos desnecessários para velocidade
        page.route("**/*.{png,jpg,jpeg,gif,webp,css,woff,woff2}", lambda route: route.abort())
        
        try:
            search_status["progress"] = 20
            search_status["message"] = f"Buscando: {search_query}"
            
            # Ir direto para a URL de busca do Google Maps
            encoded_query = search_query.replace(' ', '+')
            maps_url = f"https://www.google.com/maps/search/{encoded_query}"
            page.goto(maps_url, timeout=30000, wait_until='domcontentloaded')
            
            search_status["progress"] = 30
            search_status["message"] = "Aguardando resultados..."
            
            # Aguardar resultados com timeout reduzido
            try:
                page.wait_for_selector('a[href*="/maps/place/"]', timeout=15000)
            except:
                search_status["error"] = "Nenhum resultado encontrado"
                browser.close()
                return []
            
            search_status["progress"] = 40
            search_status["message"] = "Carregando mais resultados..."
            
            # Scroll rápido e eficiente
            for scroll_round in range(10):  # Máximo 10 tentativas de scroll
                page.mouse.wheel(0, 3000)
                page.wait_for_timeout(800)  # Timeout reduzido
                
                current_count = page.locator('a[href*="/maps/place/"]').count()
                if current_count >= max_results:
                    break
                    
                search_status["message"] = f"Encontrados {current_count} resultados..."
            
            # Coletar todos os links
            search_status["progress"] = 50
            search_status["message"] = "Coletando links dos estabelecimentos..."
            
            all_links = page.locator('a[href*="/maps/place/"]').all()
            
            # Limitar ao número máximo solicitado
            if len(all_links) > max_results:
                all_links = all_links[:max_results]
            
            search_status["total_found"] = len(all_links)
            search_status["message"] = f"Processando {len(all_links)} estabelecimentos..."
            
            # Processar cada resultado rapidamente
            for i, link in enumerate(all_links):
                progress = 50 + int((i / len(all_links)) * 45)
                search_status["progress"] = progress
                search_status["message"] = f"Extraindo dados ({i+1}/{len(all_links)})"
                
                try:
                    # Clicar no link
                    link.click()
                    page.wait_for_timeout(1000)  # Timeout mínimo
                    
                    # Aguardar apenas o título carregar
                    try:
                        page.wait_for_selector('h1', timeout=8000)
                    except:
                        continue
                    
                    # Extração super rápida apenas dos dados essenciais
                    name = fast_extract(page, [
                        'h1.DUwDvf',
                        'h1[data-attrid="title"]',
                        'h1'
                    ])
                    
                    place_type = fast_extract(page, [
                        'button[jsaction*="category"]',
                        '.DkEaL',
                        '[data-value*="type"]'
                    ])
                    
                    address = fast_extract(page, [
                        'button[data-item-id="address"] .fontBodyMedium',
                        '[data-item-id="address"] .fontBodyMedium',
                        'button[data-value="Address"] .fontBodyMedium'
                    ])
                    
                    phone = fast_extract(page, [
                        'button[data-item-id*="phone"] .fontBodyMedium',
                        'a[href^="tel:"]',
                        'button[aria-label*="Phone"] .fontBodyMedium'
                    ])
                    
                    website = fast_extract(page, [
                        'a[data-item-id="authority"] .fontBodyMedium',
                        'a[href^="http"]:not([href*="google"]):not([href*="maps"])',
                        'button[data-item-id="authority"] div'
                    ])
                    
                    # Só adiciona se conseguiu pelo menos o nome
                    if name and name != "N/A":
                        result = {
                            "name": name,
                            "type": place_type,
                            "address": address,
                            "phone": phone,
                            "website": website
                        }
                        results.append(result)
                    
                except Exception as e:
                    continue
                
            search_status["progress"] = 95
            search_status["message"] = f"Concluído! {len(results)} estabelecimentos coletados."
            
        except Exception as e:
            search_status["error"] = str(e)
            search_status["message"] = f"Erro: {str(e)}"
            
        finally:
            browser.close()
    
    return results

def run_scraper(establishment_type, location, max_results):
    global search_results, search_status
    
    try:
        search_status["is_running"] = True
        search_status["progress"] = 10
        search_status["message"] = "Iniciando coleta rápida..."
        search_status["error"] = None
        
        # Query de busca otimizada
        search_query = f"{establishment_type} {location}"
        
        # Executar scraper rápido
        results = scrape_google_maps(search_query, max_results)
        
        search_results = results
        search_status["total_found"] = len(results)
        search_status["progress"] = 100
        search_status["message"] = f"Concluído! {len(results)} estabelecimentos coletados em modo rápido."
        search_status["is_running"] = False
        
    except Exception as e:
        search_status["error"] = str(e)
        search_status["message"] = "Erro durante a coleta."
        search_status["progress"] = 0
        search_status["is_running"] = False

# Rotas da aplicação
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    global search_params, search_status
    
    # Obter parâmetros do formulário
    establishment_type = request.form.get('establishment_type')
    location = request.form.get('location')
    max_results = int(request.form.get('max_results', 20))
    
    # Validar parâmetros
    if not establishment_type or not location:
        return jsonify({
            "error": "Tipo de estabelecimento e localização são obrigatórios."
        }), 400
    
    # Armazenar parâmetros de busca
    search_params = {
        "establishment_type": establishment_type,
        "location": location,
        "max_results": max_results
    }
    
    # Verificar se já existe uma busca em andamento
    if search_status["is_running"]:
        return jsonify({
            "error": "Já existe uma busca em andamento. Aguarde a conclusão."
        }), 400
    
    # Iniciar thread para executar o scraper
    scraper_thread = threading.Thread(
        target=run_scraper,
        args=(establishment_type, location, max_results)
    )
    scraper_thread.daemon = True
    scraper_thread.start()
    
    # Redirecionar para a página de resultados
    return redirect('/results')

@app.route('/results')
def results():
    return render_template('results.html')

@app.route('/api/results')
def api_results():
    return jsonify({
        "search_params": search_params,
        "total_found": search_status["total_found"],
        "results": search_results
    })

@app.route('/api/status')
def api_status():
    return jsonify(search_status)

@app.route('/export/txt')
def export_txt():
    try:
        if not search_results:
            return jsonify({"error": "Nenhum resultado disponível."}), 404
        
        content = f"Busca: {search_params.get('establishment_type', '')} em {search_params.get('location', '')}\n"
        content += f"Total: {len(search_results)} estabelecimentos\n"
        content += "=" * 50 + "\n\n"
        
        for i, result in enumerate(search_results, 1):
            content += f"{i}. {result.get('name', 'N/A')}\n"
            content += f"   Tipo: {result.get('type', 'N/A')}\n"
            content += f"   Endereço: {result.get('address', 'N/A')}\n"
            content += f"   Telefone: {result.get('phone', 'N/A')}\n"
            content += f"   Website: {result.get('website', 'N/A')}\n"
            content += "-" * 30 + "\n\n"
        
        buffer = io.BytesIO()
        buffer.write(content.encode('utf-8'))
        buffer.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"estabelecimentos_{timestamp}.txt"
        
        return send_file(buffer, as_attachment=True, download_name=filename, mimetype='text/plain')
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/export/csv')
def export_csv():
    try:
        if not search_results:
            return jsonify({"error": "Nenhum resultado disponível."}), 404
        
        headers = ['Nome', 'Tipo', 'Endereço', 'Telefone', 'Website']
        
        content = ','.join(headers) + '\n'
        for result in search_results:
            row = [
                f'"{result.get("name", "N/A").replace('"', '""')}"',
                f'"{result.get("type", "N/A").replace('"', '""')}"',
                f'"{result.get("address", "N/A").replace('"', '""')}"',
                f'"{result.get("phone", "N/A").replace('"', '""')}"',
                f'"{result.get("website", "N/A").replace('"', '""')}"'
            ]
            content += ','.join(row) + '\n'
        
        buffer = io.BytesIO()
        buffer.write(content.encode('utf-8'))
        buffer.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"estabelecimentos_{timestamp}.csv"
        
        return send_file(buffer, as_attachment=True, download_name=filename, mimetype='text/csv')
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/export/json')
def export_json():
    try:
        if not search_results:
            return jsonify({"error": "Nenhum resultado disponível."}), 404
        
        data = {
            "search_params": search_params,
            "total_found": len(search_results),
            "results": search_results
        }
        
        buffer = io.BytesIO()
        buffer.write(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))
        buffer.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"estabelecimentos_{timestamp}.json"
        
        return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/json')
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint de health check para o Render
@app.route('/health')
def health():
    return jsonify({"status": "ok", "message": "Google Maps Scraper está funcionando!"})

# Para desenvolvimento local
if __name__ == '__main__':
    print("Iniciando Google Maps Scraper Web...")
    print("Acesse http://localhost:5000 no seu navegador")
    app.run(host='0.0.0.0', port=5000, debug=True)

# Para produção (Render)
# O Render irá usar o objeto 'app' automaticamente
