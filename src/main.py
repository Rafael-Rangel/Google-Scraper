# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import json
import time
import threading
import traceback
from datetime import datetime
import io
import os
import logging
from playwright.sync_api import sync_playwright

# --- Configuração de Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    "unique_results": 0 # Novo campo para resultados únicos
}

def check_memory_usage():
    """Verifica o uso de memória atual."""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        mem_mb = memory_info.rss / 1024 / 1024
        logging.info(f"Uso de memória atual: {mem_mb:.2f} MB")
        return mem_mb
    except ImportError:
        logging.warning("psutil não instalado. Não é possível verificar o uso de memória.")
        return 0
    except Exception as e:
        logging.error(f"Erro ao verificar uso de memória: {e}")
        return 0

# Função para extrair dados de um elemento usando XPath
def extract_data(xpath, page, field_name="Dado"):
    """Extrai texto de um elemento usando XPath, com logging."""
    try:
        locator = page.locator(xpath)
        if locator.count() > 0:
            data = locator.first.inner_text().strip()
            # logging.info(f"Extraído {field_name}: {data}")
            return data
        else:
            # logging.warning(f"{field_name} não encontrado com XPath: {xpath}")
            return "N/A"
    except Exception as e:
        logging.error(f"Erro ao extrair {field_name} com XPath {xpath}: {e}")
        return "N/A"

# Função principal de scraping
def scrape_google_maps(search_query, max_results):
    """Função principal para scraping do Google Maps com melhorias."""
    global search_status
    results = []
    unique_results_set = set() # Conjunto para rastrear resultados únicos (nome, endereço)

    logging.info(f"Iniciando scraping para: '{search_query}', max_results={max_results}")
    search_status['unique_results'] = 0

    with sync_playwright() as p:
        search_status["progress"] = 5
        search_status["message"] = "Iniciando navegador..."
        logging.info("Iniciando navegador Playwright...")

        try:
            browser = p.chromium.launch(headless=True)
            # Definindo um User Agent comum
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            page = context.new_page()
            logging.info("Navegador e página criados.")

            search_status["progress"] = 10
            search_status["message"] = "Acessando Google Maps..."
            logging.info("Acessando https://www.google.com/maps")
            page.goto("https://www.google.com/maps", timeout=60000)
            # Aumentar o tempo de espera inicial pode ajudar em conexões lentas
            page.wait_for_timeout(5000)
            logging.info("Página do Google Maps carregada.")

            search_status["progress"] = 15
            search_status["message"] = f"Buscando por: {search_query}... "
            logging.info(f"Preenchendo busca: '{search_query}'")
            search_input_xpath = '//input[@id="searchboxinput"]'
            page.locator(search_input_xpath).fill(search_query)
            page.wait_for_timeout(1000)
            page.keyboard.press("Enter")
            logging.info("Busca realizada.")

            # Esperar pelos resultados iniciais
            # Usar um seletor mais específico para a lista de resultados, se possível
            # Este seletor pega qualquer link de lugar, pode ser muito genérico
            results_panel_xpath = '//div[contains(@aria-label, "Resultados para")]' # Tenta focar no painel
            results_link_xpath = '//a[contains(@href, "https://www.google.com/maps/place")]'

            try:
                logging.info("Aguardando painel de resultados...")
                # Espera pelo painel de resultados ou pelo primeiro link
                page.wait_for_selector(f"{results_panel_xpath} | {results_link_xpath}", timeout=45000)
                logging.info("Painel de resultados encontrado.")
                search_status["message"] = "Resultados encontrados, carregando mais..."
            except Exception as e:
                logging.error(f"Não foi possível encontrar resultados iniciais para '{search_query}': {e}")
                search_status["error"] = f"Não foi possível encontrar resultados para '{search_query}'"
                browser.close()
                return []

            # Rolar para carregar mais resultados
            search_status["progress"] = 20
            search_status["message"] = "Carregando resultados..."
            logging.info("Iniciando rolagem para carregar mais resultados...")

            previously_counted = 0
            scroll_attempts = 0
            max_scroll_attempts = 100 # Aumentado
            no_new_results_streak = 0
            max_no_new_results_streak = 5 # Parar após 5 tentativas sem novos resultados

            # Tentar focar no painel de rolagem correto
            scrollable_element_xpath = '//div[contains(@aria-label, "Resultados para")]/..//div[@role="feed"]' # XPath mais provável para o feed rolável
            # Fallback para rolagem da página inteira se o painel não for encontrado
            scroll_target = page.locator(scrollable_element_xpath).first if page.locator(scrollable_element_xpath).count() > 0 else page

            if scroll_target == page:
                 logging.warning("Painel de rolagem específico não encontrado, rolando a página inteira.")
            else:
                 logging.info("Painel de rolagem específico encontrado.")

            collected_urls = set() # Usar URLs para identificar links únicos

            while scroll_attempts < max_scroll_attempts:
                logging.info(f"Tentativa de rolagem {scroll_attempts + 1}/{max_scroll_attempts}")
                
                # Tentar rolar o elemento específico ou a página
                if scroll_target != page:
                    scroll_target.evaluate("node => node.scrollTop = node.scrollHeight")
                else:
                    page.mouse.wheel(0, 10000) # Rola a página inteira
                
                # Aumentar o tempo de espera após a rolagem
                page.wait_for_timeout(3000) # Espera 3 segundos para carregar

                # Coletar URLs atuais para verificar contagem e unicidade
                current_links = page.locator(results_link_xpath).all()
                current_urls = set()
                for link in current_links:
                    try:
                        href = link.get_attribute('href')
                        if href and "https://www.google.com/maps/place" in href:
                            current_urls.add(href)
                    except Exception:
                        continue # Ignora links que derem erro ao pegar href
                
                newly_found_count = len(current_urls - collected_urls)
                total_unique_found = len(collected_urls.union(current_urls))
                
                logging.info(f"Rolagem {scroll_attempts + 1}: Encontrados {len(current_urls)} links visíveis. Total único até agora: {total_unique_found}. Novos nesta rolagem: {newly_found_count}")

                collected_urls.update(current_urls)
                current_count = len(collected_urls)

                search_status["message"] = f"Encontrados {current_count} resultados únicos até agora..."

                if current_count >= max_results:
                    logging.info(f"Limite de {max_results} resultados únicos atingido.")
                    break

                if newly_found_count == 0:
                    no_new_results_streak += 1
                    logging.warning(f"Nenhum resultado novo encontrado nesta rolagem (sequência: {no_new_results_streak}/{max_no_new_results_streak}).")
                    if no_new_results_streak >= max_no_new_results_streak:
                        logging.info("Parando rolagem devido à falta de novos resultados em tentativas consecutivas.")
                        break
                else:
                    no_new_results_streak = 0 # Resetar a sequência

                previously_counted = current_count
                scroll_attempts += 1
                page.wait_for_timeout(500) # Pequena pausa antes da próxima rolagem

            logging.info(f"Rolagem concluída. Total de {len(collected_urls)} URLs únicos encontrados.")

            # Limitar ao max_results se necessário (após coletar todos os URLs únicos)
            final_urls = list(collected_urls)
            if len(final_urls) > max_results:
                logging.info(f"Limitando {len(final_urls)} URLs únicos encontrados para os {max_results} solicitados.")
                final_urls = final_urls[:max_results]

            search_status["total_found"] = len(final_urls) # Atualiza com o total de URLs únicos a processar
            search_status["message"] = f"Coletando detalhes para {len(final_urls)} estabelecimentos..."
            logging.info(f"Iniciando extração de detalhes para {len(final_urls)} URLs.")

            # Processar cada URL único
            for i, url in enumerate(final_urls):
                progress = 30 + int((i / len(final_urls)) * 65) # Ajustar cálculo do progresso
                search_status["progress"] = progress
                search_status["message"] = f"Coletando dados ({i+1}/{len(final_urls)})..."
                logging.info(f"--- Processando URL {i+1}/{len(final_urls)}: {url} ---")

                try:
                    # Navegar diretamente para a URL do estabelecimento pode ser mais estável
                    logging.info(f"Navegando para a página do estabelecimento: {url}")
                    page.goto(url, timeout=30000)
                    page.wait_for_timeout(2500) # Esperar um pouco para a página carregar

                    # Seletores (podem precisar de ajuste se o layout do Maps mudar)
                    # Usar seletores mais robustos baseados em data-item-id ou aria-label quando possível
                    name_xpath = '//h1[contains(@class, "DUwDvf")] | //h1[contains(@class, "fontHeadlineLarge")]'
                    place_type_xpath = '//button[contains(@jsaction, "category")]'
                    address_xpath = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
                    phone_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
                    website_xpath = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
                    # Horário pode ter múltiplos formatos
                    opening_hours_xpath = '//div[contains(@aria-label, "Horário")] | //button[contains(@data-item-id, "oh")]'
                    intro_xpath = '//div[contains(@class, "WeS02d")]//div[contains(@class, "PYvSYb")]' # Descrição
                    reviews_xpath = '//div[contains(@class, "F7nice")]' # Bloco de avaliação
                    info_xpath_base = '//div[contains(@class, "LTs0Rc")] | //div[contains(@class, "iP2t7d")]' # Ícones de informação (entrega, etc.)

                    # Esperar pelo nome como indicador de que a página carregou
                    try:
                        page.wait_for_selector(name_xpath, timeout=15000)
                        logging.info("Detalhes do estabelecimento carregados (nome encontrado).")
                    except Exception as wait_error:
                        logging.error(f"Erro ao esperar pelo nome do estabelecimento em {url}: {wait_error}. Pulando item.")
                        continue

                    # Extrair dados
                    name = extract_data(name_xpath, page, "Nome")
                    place_type = extract_data(place_type_xpath, page, "Tipo")
                    address = extract_data(address_xpath, page, "Endereço")
                    phone = extract_data(phone_xpath, page, "Telefone")
                    website = extract_data(website_xpath, page, "Website")
                    opening_hours = extract_data(opening_hours_xpath, page, "Horário")
                    intro = extract_data(intro_xpath, page, "Introdução")

                    # Extrair avaliações (lógica original mantida, mas com logging)
                    rev_count = "N/A"
                    rev_avg = "N/A"
                    try:
                        if page.locator(reviews_xpath).count() > 0:
                            review_locator = page.locator(reviews_xpath).first
                            review_text = review_locator.inner_text()
                            parts = review_text.split()
                            if parts:
                                try:
                                    rev_avg = float(parts[0].replace(",", "."))
                                except (ValueError, IndexError):
                                    logging.warning(f"Não foi possível extrair a média de avaliação de: '{review_text}'")
                                    rev_avg = "N/A"
                                
                                try:
                                    # Tenta encontrar a contagem no formato (XXX)
                                    count_part = next((p.strip("()").replace(".", "").replace(",", "") for p in parts if p.startswith("(")), None)
                                    if count_part:
                                         rev_count = int(count_part)
                                    else: # Tenta pegar o segundo número se não houver parênteses
                                         if len(parts) > 1 and parts[1].replace(".", "").replace(",", "").isdigit():
                                             rev_count = int(parts[1].replace(".", "").replace(",", ""))
                                         else: # Último recurso: buscar pelo aria-label
                                             count_span_xpath = reviews_xpath + '//span[contains(@aria-label, "avaliaç")]'
                                             if page.locator(count_span_xpath).count() > 0:
                                                 aria_label = page.locator(count_span_xpath).first.get_attribute("aria-label")
                                                 count_part_aria = aria_label.split()[0].replace(".", "").replace(",", "")
                                                 if count_part_aria.isdigit():
                                                     rev_count = int(count_part_aria)
                                                 else: rev_count = "N/A"
                                             else: rev_count = "N/A"
                                except (ValueError, IndexError, AttributeError) as rev_e:
                                    logging.warning(f"Não foi possível extrair contagem de avaliações de '{review_text}': {rev_e}")
                                    rev_count = "N/A"
                        else:
                            logging.warning("Bloco de avaliações não encontrado.")
                    except Exception as e_rev:
                         logging.error(f"Erro ao processar bloco de avaliações: {e_rev}")

                    # Extrair informações de serviços (lógica original mantida)
                    store_shopping = False
                    in_store_pickup = False
                    delivery = False
                    try:
                        info_elements = page.locator(info_xpath_base).all()
                        for info_element in info_elements:
                            info_text = info_element.inner_text().lower()
                            if "compra" in info_text or "shop" in info_text:
                                store_shopping = True
                            if "retira" in info_text or "pickup" in info_text:
                                in_store_pickup = True
                            if "entrega" in info_text or "delivery" in info_text:
                                delivery = True
                    except Exception as e_info:
                        logging.error(f"Erro ao extrair informações de serviço: {e_info}")

                    # --- Deduplicação --- 
                    # Usar uma combinação de nome e endereço (ou telefone) como chave única
                    unique_key = (name, address if address != "N/A" else phone) 
                    
                    if name != "N/A" and unique_key not in unique_results_set:
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
                            "delivery": delivery,
                            "google_maps_url": url # Adiciona a URL original
                        }
                        results.append(result)
                        unique_results_set.add(unique_key)
                        search_status['unique_results'] = len(results)
                        logging.info(f"Adicionado resultado único: {name} ({address})")
                    elif name != "N/A":
                         logging.warning(f"Resultado duplicado encontrado e ignorado: {name} ({address})")
                    else:
                         logging.warning(f"Resultado sem nome encontrado e ignorado (URL: {url}).")

                except Exception as e:
                    logging.error(f"Erro GERAL ao processar URL {url}: {e}")
                    traceback.print_exc() # Log completo do erro
                    continue # Pula para o próximo URL em caso de erro grave

                # Pequena pausa entre requisições para não sobrecarregar
                page.wait_for_timeout(500)
                check_memory_usage() # Verifica memória após cada item

            search_status["progress"] = 95
            search_status["message"] = "Finalizando coleta de dados..."
            logging.info("Extração de detalhes concluída.")

        except Exception as e:
            logging.error(f"Erro fatal durante o scraping: {e}")
            search_status["error"] = f"Erro durante a coleta: {str(e)}" # Mostrar erro na interface
            search_status["message"] = f"Erro durante a coleta: {str(e)}"
            traceback.print_exc()
        finally:
            if 'browser' in locals() and browser.is_connected():
                logging.info("Fechando navegador...")
                browser.close()
                logging.info("Navegador fechado.")
            else:
                 logging.info("Navegador já estava fechado ou não foi iniciado.")

    logging.info(f"Scraping finalizado. {len(results)} resultados únicos coletados.")
    search_status['unique_results'] = len(results)
    return results

# Função para executar o scraper em uma thread separada
def run_scraper(establishment_type, location, max_results):
    global search_results, search_params, search_status
    start_time = time.time()
    logging.info(f"Iniciando thread de scraping para: {establishment_type} em {location}, max: {max_results}")

    try:
        # Resetar status antes de começar
        search_status['is_running'] = True
        search_status['progress'] = 0
        search_status['message'] = "Iniciando coleta..."
        search_status['error'] = None
        search_status['total_found'] = 0
        search_status['unique_results'] = 0
        search_results.clear() # Limpar resultados anteriores
        search_params.update({
            "establishment_type": establishment_type,
            "location": location,
            "max_results": max_results
        })

        # Construir a query de busca
        search_query = f'{establishment_type} em {location}'

        # Executar o scraper
        results = scrape_google_maps(search_query, max_results)

        # Armazenar resultados
        search_results = results
        search_status['total_found'] = len(results) # Agora reflete os únicos encontrados
        search_status['unique_results'] = len(results)

        end_time = time.time()
        duration = end_time - start_time
        logging.info(f"Coleta concluída em {duration:.2f} segundos. {len(results)} resultados únicos.")

        search_status['progress'] = 100
        search_status['message'] = f"Coleta concluída! {len(results)} resultados únicos encontrados em {duration:.2f}s."
        search_status['is_running'] = False

    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        logging.exception("Erro crítico na thread do scraper.") # Loga o traceback completo
        search_status['error'] = f"Erro crítico: {str(e)}"
        search_status['message'] = f"Erro crítico após {duration:.2f}s. Verifique os logs do servidor."
        search_status['progress'] = 0
        search_status['is_running'] = False
        # traceback.print_exc() # Já logado com logging.exception

# Rotas da API (sem alterações significativas, exceto talvez passar o unique_results)
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    global search_params, search_status
    logging.info(f"Recebida requisição /search: {request.form}")

    establishment_type = request.form.get('establishment_type')
    location = request.form.get('location')
    try:
        max_results = int(request.form.get('max_results', 50))
        if max_results <= 0:
             max_results = 50 # Default seguro
    except ValueError:
        max_results = 50
        logging.warning("max_results inválido, usando default 50.")

    if not establishment_type or not location:
        logging.error("Requisição /search inválida: Faltando tipo ou localização.")
        return jsonify({
            "error": "Tipo de estabelecimento e localização são obrigatórios."
        }), 400

    if search_status["is_running"]:
        logging.warning("Requisição /search recebida enquanto outra busca está em andamento.")
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
    logging.info("Thread do scraper iniciada.")

    return redirect('/results')

@app.route('/results')
def results():
    # Passar os parâmetros iniciais para a página de resultados, se necessário
    return render_template('results.html', initial_params=search_params)

@app.route('/api/results')
def api_results():
    # Retorna os resultados atuais e os parâmetros da última busca
    return jsonify({
        "search_params": search_params,
        "total_unique_found": search_status['unique_results'], # Renomeado para clareza
        "results": search_results
    })

@app.route('/api/status')
def api_status():
    # Retorna o status atual da busca
    return jsonify(search_status)

# Funções de exportação (sem alterações, mas agora exportarão resultados únicos)
@app.route('/export/txt')
def export_txt():
    logging.info("Requisição /export/txt recebida.")
    try:
        if not search_results:
            return jsonify({"error": "Nenhum resultado disponível para exportação."}), 404

        content = f"Resultados da busca por: {search_params.get('establishment_type', 'N/A')} em {search_params.get('location', 'N/A')}\n"
        content += f"Total de estabelecimentos únicos encontrados: {len(search_results)}\n"
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
            content += f"URL Google Maps: {result.get('google_maps_url', 'N/A')}\n"
            content += "---" * 10 + "\n\n"

        buffer = io.BytesIO()
        buffer.write(content.encode('utf-8'))
        buffer.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"resultados_{timestamp}.txt"

        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='text/plain; charset=utf-8'
        )

    except Exception as e:
        logging.exception("Erro ao gerar exportação TXT.")
        return jsonify({"error": f"Erro ao gerar TXT: {str(e)}"}), 500

@app.route('/export/json')
def export_json():
    logging.info("Requisição /export/json recebida.")
    try:
        if not search_results:
            return jsonify({"error": "Nenhum resultado disponível para exportação."}), 404

        data = {
            "search_params": search_params,
            "total_unique_found": len(search_results),
            "results": search_results
        }

        buffer = io.BytesIO()
        buffer.write(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))
        buffer.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"resultados_{timestamp}.json"

        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/json; charset=utf-8'
        )

    except Exception as e:
        logging.exception("Erro ao gerar exportação JSON.")
        return jsonify({"error": f"Erro ao gerar JSON: {str(e)}"}), 500

@app.route('/export/csv')
def export_csv():
    logging.info("Requisição /export/csv recebida.")
    try:
        if not search_results:
            return jsonify({"error": "Nenhum resultado disponível para exportação."}), 404

        # Usar io.StringIO para trabalhar com texto diretamente no CSV writer
        output = io.StringIO()
        # Usar ; como delimitador pode ser melhor para Excel em algumas regiões (como Brasil)
        writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # Cabeçalhos (incluindo a nova URL)
        headers = [
            'Nome', 'Tipo', 'Endereço', 'Telefone', 'Website', 'Horário',
            'Avaliação Média', 'Contagem de Avaliações', 'Introdução',
            'Compras na Loja', 'Retirada na Loja', 'Entrega', 'URL Google Maps'
        ]
        writer.writerow(headers)

        # Escrever dados
        for result in search_results:
            writer.writerow([
                result.get('name', 'N/A'),
                result.get('type', 'N/A'),
                result.get('address', 'N/A'),
                result.get('phone', 'N/A'),
                result.get('website', 'N/A'),
                result.get('opening_hours', 'N/A'),
                result.get('average_rating', 'N/A'),
                result.get('review_count', 'N/A'),
                result.get('introduction', 'N/A'),
                'Sim' if result.get('store_shopping') else 'Não',
                'Sim' if result.get('in_store_pickup') else 'Não',
                'Sim' if result.get('delivery') else 'Não',
                result.get('google_maps_url', 'N/A')
            ])

        # Preparar para envio
        buffer = io.BytesIO()
        # Codificar como UTF-8 com BOM para melhor compatibilidade com Excel
        buffer.write(output.getvalue().encode('utf-8-sig'))
        buffer.seek(0)
        output.close()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"resultados_{timestamp}.csv"

        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv; charset=utf-8-sig'
        )

    except NameError: # Caso csv não tenha sido importado
         logging.error("Módulo CSV não importado.")
         return jsonify({"error": "Erro interno: Módulo CSV não disponível."}), 500
    except Exception as e:
        logging.exception("Erro ao gerar exportação CSV.")
        return jsonify({"error": f"Erro ao gerar CSV: {str(e)}"}), 500

# Importar CSV apenas se necessário
try:
    import csv
except ImportError:
    logging.warning("Módulo CSV não encontrado. Exportação CSV estará desabilitada.")
    # Remover a rota se o módulo não existir?
    pass

if __name__ == '__main__':
    # Rodar em 0.0.0.0 para ser acessível externamente (necessário para Render)
    # Usar uma porta definida pelo ambiente ou default 5000
    port = int(os.environ.get('PORT', 5000))
    logging.info(f"Iniciando servidor Flask na porta {port}")
    # Usar waitrees ou gunicorn em produção em vez do servidor de desenvolvimento Flask
    # app.run(host='0.0.0.0', port=port, debug=False) # debug=False é importante para produção
    # Para deploy no Render, o comando de start geralmente usa gunicorn:
    # gunicorn --bind 0.0.0.0:$PORT src.main:app
    # A linha app.run é mais para desenvolvimento local.
    # Se for rodar localmente para teste: 
    app.run(host='0.0.0.0', port=port, debug=True) # Mudar debug para False antes de deploy final
