def run_scraper(establishment_type, location, max_results):
    global search_results, search_status
    
    try:
        search_status["is_running"] = True
        search_status["progress"] = 10
        search_status["message"] = "Iniciando coleta de dados..."
        search_status["error"] = None
        search_status["debug_logs"] = []  # Limpar logs anteriores
        
        # Construir a query de busca
        search_query = f"{establishment_type} em {location}"
        
        # Executar o scraper
        results = scrape_google_maps(search_query, max_results)
        
        # Armazenar resultados
        search_results = results
        search_status["total_found"] = len(results)
        
        search_status["progress"] = 100
        search_status["message"] = "Coleta concluída com sucesso!"
        search_status["is_running"] = False
        
    except Exception as e:
        search_status["error"] = str(e)
        search_status["message"] = "Erro durante a coleta de dados."
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
    "total_found": 0,
    "debug_logs": []  # Adicionando logs para o frontend
}

def check_memory_usage():
    """Verifica o uso de memória atual."""
    import psutil
    process = psutil.Process()
    memory_info = process.memory_info()
    return memory_info.rss / 1024 / 1024  # MB

# Função para extrair dados de um elemento usando XPath
def extract_data(xpath, page):
    """Extrai texto de um elemento usando XPath."""
    try:
        if page.locator(xpath).count() > 0:
            data = page.locator(xpath).first.inner_text()
            return data
        else:
            return "N/A"
    except Exception as e:
        return "N/A"

# Função principal de scraping
def add_debug_log(message):
    """Adiciona log tanto no console quanto no status para o frontend."""
    print(message)
    search_status["debug_logs"].append(f"{datetime.now().strftime('%H:%M:%S')} - {message}")
    # Manter apenas os últimos 50 logs para não sobrecarregar
    if len(search_status["debug_logs"]) > 50:
        search_status["debug_logs"] = search_status["debug_logs"][-50:]

def scrape_google_maps(search_query, max_results):
    """Função principal para scraping do Google Maps."""
    global search_status
    
    # Listas para armazenar dados
    results = []
    
    with sync_playwright() as p:
        search_status["progress"] = 15
        search_status["message"] = "Iniciando navegador..."
        add_debug_log(f"🚀 INICIANDO SCRAPER - Query: {search_query}, Max Results: {max_results}")
        
        # Iniciar navegador em modo headless (invisível)
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            search_status["progress"] = 20
            search_status["message"] = "Acessando Google Maps..."
            add_debug_log("🌐 Acessando Google Maps...")
            
            # Acessar Google Maps
            page.goto("https://www.google.com/maps", timeout=60000)
            page.wait_for_timeout(10000)
            add_debug_log("✅ Google Maps carregado")
            
            # Buscar pelo termo
            search_status["progress"] = 25
            search_status["message"] = f"Buscando por: {search_query}..."
            add_debug_log(f"🔍 Realizando busca por: {search_query}")
            
            page.locator('//input[@id="searchboxinput"]').fill(search_query)
            page.wait_for_timeout(1000)
            page.keyboard.press("Enter")
            add_debug_log("⌨️ Enter pressionado, aguardando resultados...")
            
            # Esperar pelos resultados
            results_xpath = '//a[contains(@href, "https://www.google.com/maps/place")]'
            try:
                page.wait_for_selector(results_xpath, timeout=30000)
                initial_count = page.locator(results_xpath).count()
                add_debug_log(f"🎯 Primeiros resultados encontrados: {initial_count}")
                search_status["message"] = "Resultados encontrados, carregando mais..."
            except Exception as e:
                add_debug_log(f"❌ Erro ao encontrar resultados: {str(e)}")
                search_status["error"] = f"Não foi possível encontrar resultados para '{search_query}'"
                browser.close()
                return []
            
            # Rolar para carregar mais resultados
            search_status["progress"] = 30
            search_status["message"] = "Carregando resultados..."
            add_debug_log("📜 INICIANDO PROCESSO DE SCROLL PARA CARREGAR MAIS RESULTADOS")
            
            previously_counted = 0
            scroll_attempts = 0
            max_scroll_attempts = 50
            stagnant_count = 0  # Contador para tentativas sem mudança
            
            while scroll_attempts < max_scroll_attempts:
                add_debug_log(f"🔄 Tentativa de scroll #{scroll_attempts + 1}")
                
                # Fazer scroll mais agressivo
                page.mouse.wheel(0, 15000)
                page.wait_for_timeout(3000)  # Aumentei o tempo de espera
                
                current_count = page.locator(results_xpath).count()
                add_debug_log(f"📊 Contagem atual: {current_count} (anterior: {previously_counted})")
                
                # Verificar se atingiu o máximo desejado
                if current_count >= max_results:
                    add_debug_log(f"🎯 Meta atingida! {current_count} >= {max_results}")
                    break
                
                # Verificar se não houve mudança
                if current_count == previously_counted:
                    stagnant_count += 1
                    add_debug_log(f"⚠️ Sem mudança na contagem (tentativa estagnada #{stagnant_count})")
                    
                    if stagnant_count >= 5:  # Se ficar 5 tentativas sem mudança
                        add_debug_log("🛑 Muitas tentativas sem progresso, verificando se há botão 'Ver mais'...")
                        
                        # Tentar encontrar e clicar no botão "Ver mais resultados"
                        more_button_selectors = [
                            '//button[contains(text(), "Ver mais")]',
                            '//button[contains(text(), "More results")]',
                            '//button[contains(text(), "Mais resultados")]',
                            '//div[contains(@class, "HlvSq")]//button',
                            '//button[contains(@jsaction, "loadMore")]'
                        ]
                        
                        button_clicked = False
                        for selector in more_button_selectors:
                            try:
                                if page.locator(selector).count() > 0:
                                    add_debug_log(f"🔘 Encontrei botão 'Ver mais': {selector}")
                                    page.locator(selector).first.click()
                                    page.wait_for_timeout(3000)
                                    button_clicked = True
                                    stagnant_count = 0  # Reset do contador
                                    break
                            except Exception as e:
                                add_debug_log(f"❌ Erro ao clicar no botão: {e}")
                                continue
                        
                        if not button_clicked:
                            add_debug_log("🚫 Nenhum botão 'Ver mais' encontrado")
                            if stagnant_count >= 8:  # Mais algumas tentativas após não encontrar botão
                                add_debug_log("🏁 Finalizando - sem mais resultados disponíveis")
                                break
                    
                    # Tentar scroll em diferentes posições
                    if stagnant_count % 2 == 0:
                        add_debug_log("🔄 Tentando scroll alternativo...")
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(2000)
                    
                else:
                    add_debug_log(f"✅ Progresso! De {previously_counted} para {current_count} (+{current_count - previously_counted})")
                    previously_counted = current_count
                    stagnant_count = 0  # Reset do contador quando há progresso
                    search_status["message"] = f"Encontrados {current_count} resultados até agora..."
                
                scroll_attempts += 1
                
                # Log de progresso a cada 10 tentativas
                if scroll_attempts % 10 == 0:
                    add_debug_log(f"📈 Progresso do scroll: {scroll_attempts}/{max_scroll_attempts} tentativas, {current_count} resultados")
            
            add_debug_log(f"🏁 SCROLL FINALIZADO - Total de tentativas: {scroll_attempts}")
            
            # Obter todos os resultados finais
            final_count = page.locator(results_xpath).count()
            add_debug_log(f"📊 CONTAGEM FINAL DE ELEMENTOS ENCONTRADOS: {final_count}")
            
            listings = page.locator(results_xpath).all()
            if len(listings) > max_results:
                listings = listings[:max_results]
                add_debug_log(f"✂️ Limitando resultados de {len(page.locator(results_xpath).all())} para {max_results}")
            
            search_status["total_found"] = len(listings)
            search_status["message"] = f"Encontrados {len(listings)} estabelecimentos. Coletando detalhes..."
            add_debug_log(f"🎯 PROCESSANDO {len(listings)} ESTABELECIMENTOS")
            
            # Processar cada resultado
            for i, listing_link in enumerate(listings):
                progress = 40 + int((i / len(listings)) * 50)
                search_status["progress"] = progress
                search_status["message"] = f"Coletando dados ({i+1}/{len(listings)})..."
                add_debug_log(f"🏪 Processando estabelecimento {i+1}/{len(listings)}")
                
                try:
                    # Clicar no resultado
                    listing = listing_link.locator("xpath=..")
                    add_debug_log(f"🖱️ Clicando no estabelecimento {i+1}")
                    listing.click()
                    
                    # Esperar pelo carregamento dos detalhes
                    name_xpath = '//div[contains(@class, "fontHeadlineLarge")]/span[contains(@class, "fontHeadlineLarge")] | //h1[contains(@class, "DUwDvf")]'
                    try:
                        page.wait_for_selector(name_xpath, timeout=15000)
                        add_debug_log(f"✅ Detalhes carregados para estabelecimento {i+1}")
                    except Exception:
                        add_debug_log(f"⏰ Timeout aguardando detalhes do estabelecimento {i+1}")
                        continue
                    
                    page.wait_for_timeout(1500)
                    
                    # Extrair dados
                    name = extract_data(name_xpath, page)
                    add_debug_log(f"📝 Nome extraído: {name}")
                    
                    place_type = extract_data('//button[contains(@jsaction, "category")]', page)
                    address = extract_data('//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]', page)
                    phone = extract_data('//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]', page)
                    website = extract_data('//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]', page)
                    opening_hours = extract_data('//button[contains(@data-item-id, "oh")] | //div[contains(@aria-label, "Horário")]', page)
                    intro = extract_data('//div[contains(@class, "WeS02d")]//div[contains(@class, "PYvSYb")]', page)
                    
                    # Extrair avaliações
                    reviews_xpath = '//div[contains(@class, "F7nice")]'
                    rev_count = "N/A"
                    rev_avg = "N/A"
                    
                    if page.locator(reviews_xpath).count() > 0:
                        review_text = page.locator(reviews_xpath).first.inner_text()
                        parts = review_text.split()
                        try:
                            rev_avg = float(parts[0].replace(",", "."))
                        except (ValueError, IndexError):
                            rev_avg = "N/A"
                        try:
                            count_part = parts[1].strip("()").replace(",", "")
                            rev_count = int(count_part)
                        except (ValueError, IndexError):
                            count_span_xpath = reviews_xpath + '//span[@aria-label]'
                            if page.locator(count_span_xpath).count() > 0:
                                try:
                                    count_part = page.locator(count_span_xpath).first.get_attribute("aria-label").split()[0].replace(",", "")
                                    rev_count = int(count_part)
                                except (ValueError, IndexError, AttributeError):
                                    rev_count = "N/A"
                            else:
                                rev_count = "N/A"
                    
                    # Extrair informações de serviços
                    info_xpath_base = '//div[contains(@class, "LTs0Rc")] | //div[contains(@class, "iP2t7d")]'
                    store_shopping = False
                    in_store_pickup = False
                    delivery = False
                    
                    info_elements = page.locator(info_xpath_base).all()
                    for info_element in info_elements:
                        info_text = info_element.inner_text().lower()
                        if "compra" in info_text or "shop" in info_text:
                            store_shopping = True
                        if "retira" in info_text or "pickup" in info_text:
                            in_store_pickup = True
                        if "entrega" in info_text or "delivery" in info_text:
                            delivery = True
                    
                    # Adicionar resultado à lista
                    result = {
                        "name": name,
                        "type": place_type,
                        "address": address,
                        "phone": phone,
                        "website": website,
                        "opening_hours": opening_hours,
                        "average_rating": rev_avg,
                        "review_count": rev_count,
                        "introduction": intro,
                        "store_shopping": store_shopping,
                        "in_store_pickup": in_store_pickup,
                        "delivery": delivery
                    }
                    
                    results.append(result)
                    add_debug_log(f"✅ Dados coletados com sucesso para: {name}")
                    
                except Exception as e:
                    add_debug_log(f"❌ Erro ao processar estabelecimento {i+1}: {str(e)}")
                    continue
                
                # Pequena pausa entre requisições
                page.wait_for_timeout(500)
            
            search_status["progress"] = 95
            search_status["message"] = "Finalizando coleta de dados..."
            add_debug_log(f"🎉 COLETA FINALIZADA - {len(results)} estabelecimentos processados com sucesso")
            
        except Exception as e:
            add_debug_log(f"💥 ERRO GERAL NO SCRAPER: {str(e)}")
            add_debug_log(f"📋 Traceback: {traceback.format_exc()}")
            search_status["error"] = str(e)
            search_status["message"] = f"Erro durante a coleta: {str(e)}"
        finally:
            browser.close()
            add_debug_log("🔒 Navegador fechado")
    
    return results

# Função para executar o scraper em uma thread separada
def run_scraper(establishment_type, location, max_results):
    global search_results, search_status
    
    try:
        search_status["is_running"] = True
        search_status["progress"] = 10
        search_status["message"] = "Iniciando coleta de dados..."
        search_status["error"] = None
        
        # Construir a query de busca
        search_query = f"{establishment_type} em {location}"
        
        # Executar o scraper
        results = scrape_google_maps(search_query, max_results)
        
        # Armazenar resultados
        search_results = results
        search_status["total_found"] = len(results)
        
        search_status["progress"] = 100
        search_status["message"] = "Coleta concluída com sucesso!"
        search_status["is_running"] = False
        
    except Exception as e:
        search_status["error"] = str(e)
        search_status["message"] = "Erro durante a coleta de dados."
        search_status["progress"] = 0
        search_status["is_running"] = False
        traceback.print_exc()

# Rotas da API
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    global search_params, search_status
    
    # Obter parâmetros do formulário
    establishment_type = request.form.get('establishment_type')
    location = request.form.get('location')
    max_results = int(request.form.get('max_results', 50))
    
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
        # Verificar se há resultados
        if not search_results:
            return jsonify({"error": "Nenhum resultado disponível para exportação."}), 404
        
        # Criar conteúdo do arquivo TXT
        content = f"Resultados da busca por: {search_params['establishment_type']} em {search_params['location']}\n"
        content += f"Total de estabelecimentos encontrados: {len(search_results)}\n"
        content += "=" * 40 + "\n\n"
        
        for result in search_results:
            content += f"Nome: {result.get('name', 'N/A')}\n"
            content += f"Tipo: {result.get('type', 'N/A')}\n"
            content += f"Endereço: {result.get('address', 'N/A')}\n"
            content += f"Telefone: {result.get('phone', 'N/A')}\n"
            content += f"Website: {result.get('website', 'N/A')}\n"
            content += f"Horário: {result.get('opening_hours', 'N/A')}\n"
            content += f"Avaliação Média: {result.get('average_rating', 'N/A')}\n"
            content += f"Contagem de Avaliações: {result.get('review_count', 'N/A')}\n"
            content += f"Introdução: {result.get('introduction', 'N/A')}\n"
            content += f"Compras na Loja: {'Sim' if result.get('store_shopping') else 'Não'}\n"
            content += f"Retirada na Loja: {'Sim' if result.get('in_store_pickup') else 'Não'}\n"
            content += f"Entrega: {'Sim' if result.get('delivery') else 'Não'}\n"
            content += "---" * 10 + "\n\n"
        
        # Criar um objeto de arquivo em memória
        buffer = io.BytesIO()
        buffer.write(content.encode('utf-8'))
        buffer.seek(0)
        
        # Gerar nome do arquivo com timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"resultados_{timestamp}.txt"
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='text/plain'
        )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/export/json')
def export_json():
    try:
        # Verificar se há resultados
        if not search_results:
            return jsonify({"error": "Nenhum resultado disponível para exportação."}), 404
        
        # Criar objeto JSON
        data = {
            "search_params": search_params,
            "total_found": len(search_results),
            "results": search_results
        }
        
        # Criar um objeto de arquivo em memória
        buffer = io.BytesIO()
        buffer.write(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))
        buffer.seek(0)
        
        # Gerar nome do arquivo com timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"resultados_{timestamp}.json"
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/json'
        )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/export/csv')
def export_csv():
    try:
        # Verificar se há resultados
        if not search_results:
            return jsonify({"error": "Nenhum resultado disponível para exportação."}), 404
        
        # Criar conteúdo CSV
        headers = [
            'Nome',
            'Tipo',
            'Endereço',
            'Telefone',
            'Website',
            'Horário',
            'Avaliação Média',
            'Contagem de Avaliações',
            'Introdução',
            'Compras na Loja',
            'Retirada na Loja',
            'Entrega'
        ]
        
        # Linhas de dados
        rows = []
        for result in search_results:
            row = [
                f'"' + str(result.get("name", "N/A")).replace('"', '""') + '"',
                f'"' + str(result.get("type", "N/A")).replace('"', '""') + '"',
                f'"' + str(result.get("address", "N/A")).replace('"', '""') + '"',
                f'"' + str(result.get("phone", "N/A")).replace('"', '""') + '"',
                f'"' + str(result.get("website", "N/A")).replace('"', '""') + '"',
                f'"' + str(result.get("opening_hours", "N/A")).replace('"', '""') + '"',
                f'"' + str(result.get("average_rating", "N/A")) + '"',
                f'"' + str(result.get("review_count", "N/A")) + '"',
                f'"' + str(result.get("introduction", "N/A")).replace('"', '""') + '"',
                'Sim' if result.get('store_shopping') else 'Não',
                'Sim' if result.get('in_store_pickup') else 'Não',
                'Sim' if result.get('delivery') else 'Não'
            ]
            rows.append(row)
        
        # Montar conteúdo CSV
        content = ','.join(headers) + '\n'
        for row in rows:
            content += ','.join(row) + '\n'
        
        # Criar um objeto de arquivo em memória
        buffer = io.BytesIO()
        buffer.write(content.encode('utf-8'))
        buffer.seek(0)
        
        # Gerar nome do arquivo com timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"resultados_{timestamp}.csv"
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Iniciando Google Maps Scraper Web...")
    print("Acesse http://localhost:5000 no seu navegador")
    app.run(host='0.0.0.0', port=5000, debug=True)
