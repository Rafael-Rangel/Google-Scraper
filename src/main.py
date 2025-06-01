import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # Necessário para deploy

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import json
import time
import threading
import traceback
from datetime import datetime
import io
import os
from playwright.sync_api import sync_playwright

app = Flask(__name__)

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

def check_memory_usage():
    """Verifica o uso de memória atual."""
    import psutil
    process = psutil.Process()
    memory_info = process.memory_info()
    return memory_info.rss / 1024 / 1024  # MB

# Função para extrair dados de um elemento usando XPath - SIMPLIFICADA
def extract_data(xpath, page):
    """Extrai texto de um elemento usando XPath."""
    try:
        element = page.locator(xpath).first
        if element.count() > 0:
            return element.inner_text().strip()
        return "N/A"
    except:
        return "N/A"

# Função principal de scraping - ULTRA OTIMIZADA PARA PERFORMANCE
def scrape_google_maps(search_query, max_results):
    """Função principal para scraping do Google Maps - MÁXIMA PERFORMANCE."""
    global search_status
    
    results = []
    
    with sync_playwright() as p:
        search_status["progress"] = 10
        search_status["message"] = "Iniciando navegador..."
        
        # Configurações EXTREMAMENTE otimizadas para performance
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--disable-web-security',
                '--disable-features=TranslateUI',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-images',  # Não carrega imagens = mais rápido
                '--disable-javascript-harmony-shipping',
                '--disable-background-timer-throttling',
                '--disable-renderer-backgrounding',
                '--disable-backgrounding-occluded-windows',
                '--disable-background-networking',
                '--no-first-run',
                '--no-default-browser-check',
                '--memory-pressure-off',
                '--max_old_space_size=4096'
            ]
        )
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        page = context.new_page()
        
        # Desabilitar carregamento de recursos desnecessários para MÁXIMA VELOCIDADE
        page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())
        
        try:
            search_status["progress"] = 15
            search_status["message"] = "Acessando Google Maps..."
            
            # Acessar Google Maps
            page.goto("https://www.google.com/maps", timeout=60000)
            page.wait_for_timeout(1000)  # Reduzido
            
            # Buscar pelo termo - RÁPIDO
            search_status["progress"] = 20
            search_status["message"] = f"Buscando: {search_query}..."
            
            search_box = page.locator('#searchboxinput')
            search_box.fill(search_query)
            page.wait_for_timeout(500)  # Reduzido
            search_box.press("Enter")
            
            # Esperar pelos resultados - SELETORES OTIMIZADOS
            search_status["progress"] = 25
            search_status["message"] = "Carregando resultados..."
            
            results_xpath = '//a[contains(@href, "/maps/place/")]'
            
            try:
                page.wait_for_selector(results_xpath, timeout=15000)
            except:
                search_status["error"] = f"Sem resultados para '{search_query}'"
                browser.close()
                return []
            
            # SCROLL ULTRA AGRESSIVO E RÁPIDO
            search_status["progress"] = 30
            search_status["message"] = "Scroll rápido para mais resultados..."
            
            scroll_count = 0
            max_scrolls = 60  # Aumentado significativamente
            
            while scroll_count < max_scrolls:
                current_count = page.locator(results_xpath).count()
                
                if current_count >= max_results:
                    break
                
                # SCROLL MÚLTIPLO ULTRA RÁPIDO
                page.evaluate("""
                    // Scroll em múltiplos containers simultaneamente
                    const containers = [
                        document.querySelector('[role="main"]'),
                        document.querySelector('.m6QErb'),
                        document.querySelector('#pane')
                    ];
                    
                    containers.forEach(container => {
                        if (container) {
                            container.scrollTop += 3000;
                        }
                    });
                    
                    // Scroll da página também
                    window.scrollBy(0, 3000);
                """)
                
                # Espera MÍNIMA
                page.wait_for_timeout(800)
                
                new_count = page.locator(results_xpath).count()
                
                if new_count > current_count:
                    search_status["message"] = f"{new_count} resultados encontrados..."
                
                scroll_count += 1
            
            # Pegar resultados RAPIDAMENTE
            all_listings = page.locator(results_xpath).all()
            listings = all_listings[:max_results] if len(all_listings) > max_results else all_listings
            
            search_status["total_found"] = len(listings)
            search_status["progress"] = 40
            search_status["message"] = f"Processando {len(listings)} estabelecimentos..."
            
            if len(listings) == 0:
                search_status["error"] = "Nenhum resultado encontrado"
                browser.close()
                return []
            
            # PROCESSAMENTO ULTRA RÁPIDO - APENAS DADOS ESSENCIAIS
            for i, listing in enumerate(listings):
                progress = 40 + int((i / len(listings)) * 55)
                search_status["progress"] = progress
                search_status["message"] = f"Extraindo {i+1}/{len(listings)}"
                
                try:
                    # Clique RÁPIDO sem scroll
                    listing.click(timeout=3000)
                    
                    # Espera MÍNIMA pelos detalhes
                    page.wait_for_timeout(1200)
                    
                    # EXTRAÇÃO SUPER RÁPIDA - SÓ OS DADOS NECESSÁRIOS
                    name = extract_data('//h1 | //div[contains(@class, "fontHeadlineLarge")]//span', page)
                    
                    if name == "N/A":  # Se não conseguir nome, pula
                        continue
                    
                    # Dados essenciais com seletores únicos e rápidos
                    place_type = extract_data('//button[contains(@jsaction, "category")]', page)
                    address = extract_data('//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]', page)
                    phone = extract_data('//button[contains(@data-item-id, "phone")]//div[contains(@class, "fontBodyMedium")]', page)
                    website = extract_data('//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]', page)
                    
                    # Adicionar resultado SIMPLES
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
                
                # SEM PAUSA - MÁXIMA VELOCIDADE
            
            search_status["progress"] = 95
            search_status["message"] = f"Concluído! {len(results)} estabelecimentos coletados"
            
        except Exception as e:
            search_status["error"] = f"Erro: {str(e)}"
            search_status["message"] = f"Erro: {str(e)}"
        finally:
            browser.close()
    
    return results

# Função para executar o scraper em uma thread separada
def run_scraper(establishment_type, location, max_results):
    global search_results, search_status
    
    try:
        search_status["is_running"] = True
        search_status["progress"] = 5
        search_status["message"] = "Iniciando..."
        search_status["error"] = None
        
        # Query de busca
        search_query = f"{establishment_type} em {location}"
        
        # Executar scraper
        results = scrape_google_maps(search_query, max_results)
        
        # Armazenar resultados
        search_results = results
        search_status["total_found"] = len(results)
        
        if len(results) > 0:
            search_status["progress"] = 100
            search_status["message"] = f"Concluído! {len(results)} estabelecimentos."
        else:
            search_status["message"] = "Nenhum resultado encontrado."
            search_status["error"] = "Nenhum resultado."
        
        search_status["is_running"] = False
        
    except Exception as e:
        search_status["error"] = str(e)
        search_status["message"] = "Erro na coleta."
        search_status["progress"] = 0
        search_status["is_running"] = False

# Rotas da API
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    global search_params, search_status
    
    establishment_type = request.form.get('establishment_type')
    location = request.form.get('location')
    max_results = int(request.form.get('max_results', 20))
    
    if not establishment_type or not location:
        return jsonify({"error": "Parâmetros obrigatórios."}), 400
    
    search_params = {
        "establishment_type": establishment_type,
        "location": location,
        "max_results": max_results
    }
    
    if search_status["is_running"]:
        return jsonify({"error": "Busca em andamento."}), 400
    
    scraper_thread = threading.Thread(
        target=run_scraper,
        args=(establishment_type, location, max_results)
    )
    scraper_thread.daemon = True
    scraper_thread.start()
    
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
        
        content = f"Resultados: {search_params['establishment_type']} em {search_params['location']}\n"
        content += f"Total: {len(search_results)}\n"
        content += "=" * 50 + "\n\n"
        
        for result in search_results:
            content += f"Nome: {result.get('name', 'N/A')}\n"
            content += f"Tipo: {result.get('type', 'N/A')}\n"
            content += f"Endereço: {result.get('address', 'N/A')}\n"
            content += f"Telefone: {result.get('phone', 'N/A')}\n"
            content += f"Website: {result.get('website', 'N/A')}\n"
            content += "-" * 30 + "\n\n"
        
        buffer = io.BytesIO()
        buffer.write(content.encode('utf-8'))
        buffer.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"resultados_{timestamp}.txt"
        
        return send_file(buffer, as_attachment=True, download_name=filename, mimetype='text/plain')
    
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
        filename = f"resultados_{timestamp}.json"
        
        return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/json')
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/export/csv')
def export_csv():
    try:
        if not search_results:
            return jsonify({"error": "Nenhum resultado disponível."}), 404
        
        headers = ['Nome', 'Tipo', 'Endereço', 'Telefone', 'Website']
        
        rows = []
        for result in search_results:
            # Fix: Use separate variables to avoid f-string quote conflicts
            name_val = str(result.get("name", "N/A")).replace('"', '""')
            type_val = str(result.get("type", "N/A")).replace('"', '""')
            address_val = str(result.get("address", "N/A")).replace('"', '""')
            phone_val = str(result.get("phone", "N/A")).replace('"', '""')
            website_val = str(result.get("website", "N/A")).replace('"', '""')
            
            row = [
                f'"{name_val}"',
                f'"{type_val}"',
                f'"{address_val}"',
                f'"{phone_val}"',
                f'"{website_val}"'
            ]
            rows.append(row)
        
        content = ','.join(headers) + '\n'
        for row in rows:
            content += ','.join(row) + '\n'
        
        buffer = io.BytesIO()
        buffer.write(content.encode('utf-8'))
        buffer.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"resultados_{timestamp}.csv"
        
        return send_file(buffer, as_attachment=True, download_name=filename, mimetype='text/csv')
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Google Maps Scraper - VERSÃO ULTRA RÁPIDA")
    print("http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
