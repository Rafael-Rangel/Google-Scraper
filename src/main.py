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
import csv # Moved import csv to the top
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# --- Configuração de Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# Configuração global para armazenar os resultados da busca
search_results = []
search_params = {}
search_status = {
    "is_running": False,
    "progress": 0,
    "message": "",
    "error": None,
    "total_found": 0, # Will store the number of unique results found
    "unique_results": 0
}

# Removed check_memory_usage function

# Função para extrair dados de um elemento usando XPath
def extract_data(xpath, page, field_name="Dado"):
    """Extrai texto de um elemento usando XPath, com logging."""
    try:
        locator = page.locator(xpath)
        if locator.count() > 0:
            data = locator.first.inner_text().strip()
            return data
        else:
            return "N/A"
    except Exception as e:
        logging.error(f"Erro ao extrair {field_name} com XPath {xpath}: {e}")
        return "N/A"

# Função principal de scraping - Versão 3 (Garante resultados únicos)
def scrape_google_maps_v3(search_query, max_results):
    """Função principal para scraping do Google Maps, garantindo o número de resultados únicos."""
    global search_status
    results = []
    unique_results_set = set() # Conjunto para rastrear resultados únicos (nome, endereço, telefone)

    logging.info(f"[V3] Iniciando scraping para: '{search_query}', buscando até {max_results} resultados únicos.")
    search_status['unique_results'] = 0
    search_status['total_found'] = 0 # Reset total found count

    with sync_playwright() as p:
        search_status["progress"] = 5
        search_status["message"] = "Iniciando navegador..."
        logging.info("[V3] Iniciando navegador Playwright...")

        browser = None # Initialize browser variable
        try:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            page = context.new_page()
            logging.info("[V3] Navegador e página criados.")

            search_status["progress"] = 10
            search_status["message"] = "Acessando Google Maps..."
            logging.info("[V3] Acessando https://www.google.com/maps")
            page.goto("https://www.google.com/maps", timeout=60000)
            page.wait_for_timeout(5000)
            logging.info("[V3] Página do Google Maps carregada.")

            search_status["progress"] = 15
            search_status["message"] = f"Buscando por: {search_query}... "
            logging.info(f"[V3] Preenchendo busca: '{search_query}'")
            search_input_xpath = '//input[@id="searchboxinput"]'
            page.locator(search_input_xpath).fill(search_query)
            page.wait_for_timeout(1000)
            page.keyboard.press("Enter")
            logging.info("[V3] Busca realizada.")

            results_link_xpath = '//a[contains(@href, "https://www.google.com/maps/place")]'
            results_panel_xpath = '//div[contains(@aria-label, "Resultados para")]'

            try:
                logging.info("[V3] Aguardando painel de resultados...")
                page.wait_for_selector(f"{results_panel_xpath} | {results_link_xpath}", timeout=45000)
                logging.info("[V3] Painel de resultados encontrado.")
                search_status["message"] = "Resultados encontrados, carregando mais..."

                logging.info("[V3] Aplicando hover no primeiro resultado para focar na lista...")
                if page.locator(results_link_xpath).count() > 0:
                    page.locator(results_link_xpath).first.hover()
                    # page.wait_for_timeout(500) # Removed wait after hover
                else:
                    logging.warning("[V3] Nenhum link de resultado encontrado para aplicar hover inicial.")

            except PlaywrightTimeoutError as e:
                logging.error(f"[V3] Não foi possível encontrar resultados iniciais para '{search_query}': {e}")
                search_status["error"] = f"Não foi possível encontrar resultados para '{search_query}'"
                if browser: browser.close()
                return []

            search_status["progress"] = 20
            search_status["message"] = "Carregando lista inicial de resultados..."
            logging.info("[V3] Iniciando rolagem para carregar lista de resultados...")

            collected_urls_for_scroll_control = set()
            scroll_attempts = 0
            max_scroll_attempts = 100 # Limit scroll attempts to avoid infinite loops
            no_new_results_streak = 0
            max_no_new_results_streak = 5 # Stop scrolling if no new URLs found for 5 consecutive attempts

            scrollable_element_xpath = '//div[contains(@aria-label, "Resultados para")]/..//div[@role="feed"]'
            scroll_target = page.locator(scrollable_element_xpath).first if page.locator(scrollable_element_xpath).count() > 0 else page
            if scroll_target == page: logging.warning("[V3] Painel de rolagem específico não encontrado, rolando a página inteira.")
            else: logging.info("[V3] Painel de rolagem específico encontrado.")

            # Scroll until enough potential candidates are found or scrolling limits are reached
            while scroll_attempts < max_scroll_attempts:
                logging.info(f"[V3] Tentativa de rolagem {scroll_attempts + 1}/{max_scroll_attempts}")
                if scroll_target != page:
                    scroll_target.evaluate("node => node.scrollTop = node.scrollHeight")
                else:
                    page.mouse.wheel(0, 10000)
                page.wait_for_timeout(3000) # Wait for content to potentially load

                current_links_elements = page.locator(results_link_xpath).all()
                current_urls_for_control = set()
                for link in current_links_elements:
                    try:
                        href = link.get_attribute('href')
                        if href and "https://www.google.com/maps/place" in href:
                            current_urls_for_control.add(href)
                    except Exception: continue

                newly_found_count = len(current_urls_for_control - collected_urls_for_scroll_control)
                total_unique_found_urls = len(collected_urls_for_scroll_control.union(current_urls_for_control))

                logging.info(f"[V3] Rolagem {scroll_attempts + 1}: Encontrados {len(current_urls_for_control)} URLs visíveis. Total único (URLs) até agora: {total_unique_found_urls}. Novos nesta rolagem: {newly_found_count}")

                collected_urls_for_scroll_control.update(current_urls_for_control)
                current_url_count = len(collected_urls_for_scroll_control)

                # Estimate progress based on URL count vs max_results, capped at 30%
                scroll_progress = 20 + int((min(current_url_count, max_results * 2) / (max_results * 2)) * 10) if max_results > 0 else 20
                search_status["progress"] = min(scroll_progress, 30)
                search_status["message"] = f"Encontrados {current_url_count} links potenciais até agora..."

                # Stop scrolling if we have found significantly more URLs than needed, or if no new ones appear
                if current_url_count >= max_results * 2 and max_results > 0: # Heuristic: aim for 2x needed URLs
                    logging.info(f"[V3] Número suficiente de URLs ({current_url_count}) encontrados para processar. Parando rolagem.")
                    break

                if newly_found_count == 0:
                    no_new_results_streak += 1
                    logging.warning(f"[V3] Nenhum URL novo encontrado nesta rolagem (sequência: {no_new_results_streak}/{max_no_new_results_streak}).")
                    if no_new_results_streak >= max_no_new_results_streak:
                        logging.info("[V3] Parando rolagem devido à falta de novos URLs em tentativas consecutivas.")
                        break
                else:
                    no_new_results_streak = 0

                scroll_attempts += 1
                page.wait_for_timeout(500)

            logging.info(f"[V3] Rolagem concluída. {len(collected_urls_for_scroll_control)} URLs únicos encontrados para controle.")

            logging.info("[V3] Coletando elementos finais da lista para processamento por clique...")
            listings_elements = page.locator(results_link_xpath).all()
            total_elements_available = len(listings_elements)
            logging.info(f"[V3] {total_elements_available} elementos encontrados na lista final. Iniciando extração de detalhes até {max_results} resultados únicos.")

            search_status["message"] = f"Coletando detalhes de até {max_results} estabelecimentos únicos..."

            processed_elements_count = 0
            # Loop through all available elements, but break when max_results unique items are found
            for i, listing_element in enumerate(listings_elements):
                # Check if we already have enough unique results before processing the next element
                if len(results) >= max_results:
                    logging.info(f"[V3] Limite de {max_results} resultados únicos atingido. Interrompendo processamento de elementos.")
                    break

                processed_elements_count += 1
                # Update progress based on unique results found vs max_results requested
                progress = 30 + int((len(results) / max_results) * 65) if max_results > 0 else 30
                search_status["progress"] = progress
                search_status["message"] = f"Processando item {i+1}/{total_elements_available}. Coletados {len(results)}/{max_results} únicos..."
                logging.info(f"--- [V3] Processando Elemento {i+1}/{total_elements_available} (Únicos: {len(results)}/{max_results}) --- ")

                # *** Main try block for processing a single element ***
                try:
                    # Attempt to get URL for potential pre-filtering (optional, might be unreliable)
                    try: element_url = listing_element.get_attribute('href')
                    except Exception: element_url = None

                    # Skip if URL was already processed
                    if element_url in collected_urls_for_scroll_control:
                        logging.warning(f"[V3] URL já processada, ignorando elemento {i+1}.")
                        continue

                    logging.info(f"[V3] Clicando no elemento {i+1}...")
                    listing_element.click()

                    name_xpath = '//h1[contains(@class, "DUwDvf")] | //h1[contains(@class, "fontHeadlineLarge")]'
                    try:
                        # Wait for the details panel to likely update, using the name as a key indicator
                        page.wait_for_selector(name_xpath, timeout=15000)
                        logging.info(f"[V3] Detalhes do elemento {i+1} carregados (nome encontrado).")
                    except PlaywrightTimeoutError as wait_error:
                        logging.error(f"[V3] Erro ao esperar pelos detalhes do elemento {i+1} após clique: {wait_error}. Pulando item.")
                        continue # Skip to the next element in the outer loop

                    # page.wait_for_timeout(1500) # Removed small delay

                    # Define XPaths for data extraction
                    place_type_xpath = '//button[contains(@jsaction, "category")]'
                    address_xpath = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
                    phone_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
                    website_xpath = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
                    opening_hours_xpath = '//div[contains(@aria-label, "Horário")] | //button[contains(@data-item-id, "oh")]'
                    intro_xpath = '//div[contains(@class, "WeS02d")]//div[contains(@class, "PYvSYb")]'
                    reviews_xpath = '//div[contains(@class, "F7nice")]'
                    info_xpath_base = '//div[contains(@class, "LTs0Rc")] | //div[contains(@class, "iP2t7d")]'

                    # Extract data using the helper function
                    name = extract_data(name_xpath, page, "Nome")
                    place_type = extract_data(place_type_xpath, page, "Tipo")
                    address = extract_data(address_xpath, page, "Endereço")
                    phone = extract_data(phone_xpath, page, "Telefone")
                    website = extract_data(website_xpath, page, "Website")
                    opening_hours = extract_data(opening_hours_xpath, page, "Horário")
                    intro = extract_data(intro_xpath, page, "Introdução")

                    # Extract review data
                    rev_count = "N/A"
                    rev_avg = "N/A"
                    try:
                        if page.locator(reviews_xpath).count() > 0:
                            review_locator = page.locator(reviews_xpath).first
                            review_text = review_locator.inner_text()
                            parts = review_text.split()
                            if parts:
                                try: rev_avg = float(parts[0].replace(",", "."))
                                except (ValueError, IndexError): rev_avg = "N/A"
                                try:
                                    # Try finding count in parentheses first
                                    count_part = next((p.strip("()").replace(".", "").replace(",", "") for p in parts if p.startswith("(")), None)
                                    if count_part and count_part.isdigit(): rev_count = int(count_part)
                                    # Fallback: try second part if it looks like a number
                                    elif len(parts) > 1 and parts[1].replace(".", "").replace(",", "").isdigit(): rev_count = int(parts[1].replace(".", "").replace(",", ""))
                                    # Fallback: try aria-label on span
                                    else:
                                        count_span_xpath = reviews_xpath + '//span[contains(@aria-label, "avaliaç")]'
                                        if page.locator(count_span_xpath).count() > 0:
                                            aria_label = page.locator(count_span_xpath).first.get_attribute("aria-label")
                                            if aria_label:
                                                count_part_aria = aria_label.split()[0].replace(".", "").replace(",", "")
                                                if count_part_aria.isdigit(): rev_count = int(count_part_aria)
                                                else: rev_count = "N/A"
                                            else: rev_count = "N/A"
                                        else: rev_count = "N/A"
                                except (ValueError, IndexError, AttributeError, TypeError) as rev_e:
                                    logging.warning(f"[V3] Não foi possível extrair contagem de avaliações de '{review_text}': {rev_e}")
                                    rev_count = "N/A"
                        else: logging.warning("[V3] Bloco de avaliações não encontrado.")
                    except Exception as e_rev: logging.error(f"[V3] Erro ao processar bloco de avaliações: {e_rev}")

                    # Extract service info (delivery, pickup, etc.)
                    store_shopping = False
                    in_store_pickup = False
                    delivery = False
                    try:
                        info_elements = page.locator(info_xpath_base).all()
                        for info_element in info_elements:
                            info_text = info_element.inner_text().lower()
                            if "compra" in info_text or "shop" in info_text: store_shopping = True
                            if "retira" in info_text or "pickup" in info_text: in_store_pickup = True
                            if "entrega" in info_text or "delivery" in info_text: delivery = True
                    except Exception as e_info: logging.error(f"[V3] Erro ao extrair informações de serviço: {e_info}")

                    # Normalize data for unique key
                    normalized_name = name.lower().strip()
                    normalized_address = address.lower().strip() if address != "N/A" else ""
                    normalized_phone = phone.lower().strip() if phone != "N/A" else ""

                    # Define the unique key for duplicate checking
                    unique_key = (normalized_name, normalized_address, normalized_phone)

                    # Check for validity (must have a name) and uniqueness
                    if name != "N/A" and unique_key not in unique_results_set:
                        # Get the URL from the original element if possible
                        try: current_url = listing_element.get_attribute('href')
                        except Exception: current_url = "N/A"

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
                            "google_maps_url": current_url
                        }
                        results.append(result)
                        unique_results_set.add(unique_key)
                        search_status['unique_results'] = len(results) # Update status immediately
                        logging.info(f"[V3] Adicionado resultado único: {name} ({address if address != 'N/A' else phone})")
                    elif name != "N/A": # Log if it was a duplicate
                        logging.warning(f"[V3] Resultado duplicado encontrado e ignorado: {name} ({address if address != 'N/A' else phone})")
                    else: # Log if name was N/A
                        logging.warning(f"[V3] Resultado sem nome encontrado e ignorado (Elemento {i+1}).")

                # *** Corresponding except block for the main try ***
                except Exception as e_element:
                    logging.error(f"[V3] Erro GERAL ao processar elemento {i+1}: {e_element}")
                    traceback.print_exc()
                    # Continue to the next element even if one fails
                    continue

            # End of the loop processing elements
            search_status["progress"] = 95
            search_status["message"] = "Finalizando coleta de dados..."
            logging.info(f"[V3] Extração de detalhes concluída. Processados {processed_elements_count} elementos.")

        # *** Main except block for the whole scraping process ***
        except Exception as e:
            logging.error(f"[V3] Erro fatal durante o scraping: {e}")
            search_status["error"] = f"Erro durante a coleta: {str(e)}"
            search_status["message"] = f"Erro durante a coleta: {str(e)}"
            traceback.print_exc()
        # *** Finally block to ensure browser closure ***
        finally:
            if browser and browser.is_connected():
                logging.info("[V3] Fechando navegador...")
                browser.close()
                logging.info("[V3] Navegador fechado.")
            else:
                 logging.info("[V3] Navegador já estava fechado ou não foi iniciado.")

    # End of with sync_playwright()
    final_unique_count = len(results)
    logging.info(f"[V3] Scraping finalizado. {final_unique_count} resultados únicos coletados.")
    search_status['unique_results'] = final_unique_count
    search_status['total_found'] = final_unique_count # Set total_found to the final unique count
    return results

def run_scraper(establishment_type, location, max_results):
    global search_results, search_params, search_status
    start_time = time.time()
    logging.info(f"[V3] Iniciando thread de scraping para: {establishment_type} em {location}, max: {max_results}")

    try:
        search_status['is_running'] = True
        search_status['progress'] = 0
        search_status['message'] = "Iniciando coleta..."
        search_status['error'] = None
        search_status['total_found'] = 0
        search_status['unique_results'] = 0
        search_results.clear()
        search_params.update({
            "establishment_type": establishment_type,
            "location": location,
            "max_results": max_results
        })

        search_query = f'{establishment_type} em {location}'

        # Call the updated scraping function
        results = scrape_google_maps_v3(search_query, max_results)

        search_results = results
        # Status total_found and unique_results are updated inside scrape_google_maps_v3

        end_time = time.time()
        duration = end_time - start_time
        final_count = len(results)
        logging.info(f"[V3] Coleta concluída em {duration:.2f} segundos. {final_count} resultados únicos.")

        search_status['progress'] = 100
        search_status['message'] = f"Coleta V3 concluída! {final_count} resultados únicos encontrados em {duration:.2f}s."
        search_status['is_running'] = False

    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        logging.exception("[V3] Erro crítico na thread do scraper.")
        search_status['error'] = f"Erro crítico: {str(e)}"
        search_status['message'] = f"Erro crítico após {duration:.2f}s. Verifique os logs."
        search_status['progress'] = 0
        search_status['is_running'] = False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    global search_params, search_status
    logging.info(f"[V3] Recebida requisição /search: {request.form}")

    establishment_type = request.form.get('establishment_type')
    location = request.form.get('location')
    try:
        max_results = int(request.form.get('max_results', 50))
        if max_results <= 0: max_results = 50
    except ValueError:
        max_results = 50
        logging.warning("[V3] max_results inválido, usando default 50.")

    if not establishment_type or not location:
        logging.error("[V3] Requisição /search inválida: Faltando tipo ou localização.")
        return jsonify({"error": "Tipo de estabelecimento e localização são obrigatórios."}), 400

    if search_status["is_running"]:
        logging.warning("[V3] Requisição /search recebida enquanto outra busca está em andamento.")
        return jsonify({"error": "Já existe uma busca em andamento. Aguarde a conclusão."}), 400

    scraper_thread = threading.Thread(
        target=run_scraper,
        args=(establishment_type, location, max_results)
    )
    scraper_thread.daemon = True
    scraper_thread.start()
    logging.info("[V3] Thread do scraper (V3) iniciada.")

    return redirect('/results')

@app.route('/results')
def results():
    return render_template('results.html', initial_params=search_params)

@app.route('/api/results')
def api_results():
    return jsonify({
        "search_params": search_params,
        "total_unique_found": search_status['unique_results'], # Use unique_results here
        "results": search_results
    })

@app.route('/api/status')
def api_status():
    return jsonify(search_status)

@app.route('/export/txt')
def export_txt():
    logging.info("[V3] Requisição /export/txt recebida.")
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
        logging.exception("[V3] Erro ao gerar exportação TXT.")
        return jsonify({"error": f"Erro ao gerar TXT: {str(e)}"}), 500

@app.route('/export/json')
def export_json():
    logging.info("[V3] Requisição /export/json recebida.")
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
        logging.exception("[V3] Erro ao gerar exportação JSON.")
        return jsonify({"error": f"Erro ao gerar JSON: {str(e)}"}), 500

@app.route('/export/csv')
def export_csv():
    logging.info("[V3] Requisição /export/csv recebida.")
    try:
        if not search_results:
            return jsonify({"error": "Nenhum resultado disponível para exportação."}), 404
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # Define headers for the CSV file
        headers = [
            'Nome', 'Tipo', 'Endereço', 'Telefone', 'Website', 'Horário',
            'Avaliação Média', 'Contagem de Avaliações', 'Introdução',
            'Compras na Loja', 'Retirada na Loja', 'Entrega', 'URL Google Maps'
        ]
        writer.writerow(headers)

        # Write data rows
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

        # Prepare buffer for sending the file
        buffer = io.BytesIO()
        # Use utf-8-sig to ensure correct encoding with BOM for Excel compatibility
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

    except Exception as e:
        logging.exception("[V3] Erro ao gerar exportação CSV.")
        return jsonify({"error": f"Erro ao gerar CSV: {str(e)}"}), 500

# Removed the try-except block for csv import as it's now at the top

if __name__ == '__main__':
    # Use PORT environment variable provided by Render, default to 5000 locally
    port = int(os.environ.get('PORT', 5000))
    # Set debug=False for production environments like Render
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    logging.info(f"[V3] Iniciando servidor Flask na porta {port} (Debug: {debug_mode})")
    # Listen on 0.0.0.0 to be accessible externally
    app.run(host='0.0.0.0', port=port, debug=debug_mode)

