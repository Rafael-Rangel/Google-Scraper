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
from playwright.sync_api import sync_playwright
import psutil # Moved from inside function

# --- Global variables and Flask app initialization ---
app = Flask(__name__)

search_results = []
search_params = {}
search_status = {
    "is_running": False,
    "progress": 0,
    "message": "",
    "error": None,
    "total_found": 0,
    "debug_logs": []
}

# --- Helper Functions ---
def check_memory_usage():
    """Verifica o uso de memória atual."""
    process = psutil.Process()
    memory_info = process.memory_info()
    return memory_info.rss / 1024 / 1024  # MB

def extract_data(xpath, page):
    """Extrai texto de um elemento usando XPath."""
    try:
        locator = page.locator(xpath).first
        if locator.count() > 0 and locator.is_visible():
            data = locator.inner_text()
            return data.strip() if data else "N/A"
        else:
            # Log why it's N/A
            # add_debug_log(f"⚠️ extract_data: Element not found or not visible for xpath {xpath}")
            return "N/A"
    except Exception as e:
        # add_debug_log(f"❌ Error in extract_data for xpath {xpath}: {e}")
        return "N/A (exception)"

def add_debug_log(message):
    """Adiciona log tanto no console quanto no status para o frontend."""
    log_entry = f"{datetime.now().strftime('%H:%M:%S')} - {message}"
    print(log_entry)
    search_status["debug_logs"].append(log_entry)
    if len(search_status["debug_logs"]) > 50:
        search_status["debug_logs"] = search_status["debug_logs"][-50:]

# --- Scraping Logic ---
def scrape_google_maps(search_query, max_results):
    """Função principal para scraping do Google Maps."""
    global search_status, search_results # Allow modification of global status
    local_results = [] # Use a local list for this run

    with sync_playwright() as p:
        search_status["progress"] = 5
        search_status["message"] = "Iniciando processo de scraping..."
        search_status["error"] = None # Clear previous errors
        search_status["is_running"] = True
        search_status["debug_logs"] = [] # Clear previous logs
        add_debug_log(f"🚀 INICIANDO SCRAPER - Query: '{search_query}', Max Results: {max_results}")

        browser = None
        page = None
        try:
            # --- Browser Setup ---
            search_status["progress"] = 10
            search_status["message"] = "Iniciando navegador..."
            # Consider adding args like '--disable-gpu', '--no-sandbox' if needed
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            add_debug_log("🤖 Navegador iniciado.")

            # --- Navigation and Search ---
            search_status["progress"] = 15
            search_status["message"] = "Acessando Google Maps..."
            add_debug_log("🌐 Acessando Google Maps...")
            page.goto("https://www.google.com/maps", timeout=60000)
            page.wait_for_selector('//input[@id="searchboxinput"]', timeout=45000)
            add_debug_log("✅ Google Maps carregado.")

            search_status["progress"] = 20
            search_status["message"] = f"Buscando por: {search_query}..."
            add_debug_log(f"🔍 Realizando busca por: {search_query}")
            page.locator('//input[@id="searchboxinput"]').fill(search_query)
            page.wait_for_timeout(500)
            page.keyboard.press("Enter")
            add_debug_log("⌨️ Busca enviada, aguardando resultados...")

            # --- Initial Results Check ---
            results_container_xpath = '//div[contains(@aria-label, "Resultados para")] | //div[contains(@aria-label, "Results for")]'
            results_xpath = f'{results_container_xpath}//a[contains(@href, "https://www.google.com/maps/place")]'
            try:
                page.wait_for_selector(results_container_xpath, timeout=30000)
                page.wait_for_timeout(2000) # Allow results to populate
                initial_count = page.locator(results_xpath).count()
                if initial_count == 0:
                    add_debug_log(f"⚠️ Nenhum resultado encontrado inicialmente para '{search_query}'. Verificando...")
                    no_results_xpath = '//div[contains(text(), "Nenhum resultado encontrado")] | //div[contains(text(), "No results found")]'
                    if page.locator(no_results_xpath).count() > 0:
                        add_debug_log(f"❌ Mensagem 'Nenhum resultado encontrado' detectada.")
                        raise Exception(f"Nenhum resultado encontrado para '{search_query}' no Google Maps.")
                    else:
                        add_debug_log(f"❓ Contagem inicial zero, mas sem mensagem 'Nenhum resultado'. Erro inesperado?")
                        raise Exception(f"Erro inesperado: contagem inicial de resultados zero para '{search_query}'.")
                else:
                    add_debug_log(f"🎯 Resultados iniciais encontrados: {initial_count}")
                    search_status["message"] = "Resultados encontrados, carregando mais..."
            except Exception as initial_error:
                # This catches errors specifically from the initial check block
                add_debug_log(f"❌ Erro na verificação inicial: {initial_error}")
                raise initial_error # Re-raise to be caught by the main except block

            # --- Scrolling for More Results ---
            search_status["progress"] = 30
            search_status["message"] = "Carregando mais resultados..."
            add_debug_log("📜 Iniciando scroll para carregar mais resultados...")
            previously_counted = 0
            scroll_attempts = 0
            max_scroll_attempts = 50 # Limit attempts
            stagnant_count = 0
            max_stagnant = 8 # Stop if no change for this many attempts

            while scroll_attempts < max_scroll_attempts:
                current_count = page.locator(results_xpath).count()
                add_debug_log(f"🔄 Scroll #{scroll_attempts + 1}, Contagem: {current_count}")

                if current_count >= max_results:
                    add_debug_log(f"🎯 Meta de {max_results} atingida ou superada ({current_count}). Parando scroll.")
                    break

                if current_count == previously_counted:
                    stagnant_count += 1
                    add_debug_log(f"⚠️ Sem mudança na contagem (estagnado #{stagnant_count})")
                    if stagnant_count >= max_stagnant:
                        add_debug_log(f"🏁 Scroll finalizado - sem progresso após {max_stagnant} tentativas.")
                        break
                    # Try scrolling the main feed element if possible, otherwise wheel event
                    scroll_target_xpath = '//div[contains(@role, "feed")]'
                    if page.locator(scroll_target_xpath).count() > 0:
                         page.locator(scroll_target_xpath).first.evaluate('(element) => element.scrollTop = element.scrollHeight')
                    else:
                        page.mouse.wheel(0, 15000) # Fallback to mouse wheel
                    page.wait_for_timeout(2500 + (stagnant_count * 500)) # Wait longer if stagnant
                else:
                    stagnant_count = 0 # Reset stagnation counter
                    previously_counted = current_count
                    search_status["message"] = f"Encontrados {current_count} resultados até agora..."
                    # Scroll down
                    scroll_target_xpath = '//div[contains(@role, "feed")]'
                    if page.locator(scroll_target_xpath).count() > 0:
                         page.locator(scroll_target_xpath).first.evaluate('(element) => element.scrollTop = element.scrollHeight')
                    else:
                        page.mouse.wheel(0, 15000)
                    page.wait_for_timeout(2000)

                scroll_attempts += 1
                current_progress = 30 + int((min(current_count, max_results) / max_results) * 30) # Scroll progress up to 60%
                search_status["progress"] = min(current_progress, 60)

            if scroll_attempts == max_scroll_attempts:
                add_debug_log(f"🏁 Scroll finalizado - limite de {max_scroll_attempts} tentativas atingido.")

            # --- Processing Results ---
            final_listings = page.locator(results_xpath).all()
            add_debug_log(f"📊 Contagem final de elementos encontrados: {len(final_listings)}")

            if len(final_listings) > max_results:
                final_listings = final_listings[:max_results]
                add_debug_log(f"✂️ Limitando resultados para {max_results}")

            search_status["total_found"] = len(final_listings)
            search_status["message"] = f"Encontrados {len(final_listings)} estabelecimentos. Coletando detalhes..."
            add_debug_log(f"🎯 PROCESSANDO {len(final_listings)} ESTABELECIMENTOS")

            for i, listing_link in enumerate(final_listings):
                item_progress = 60 + int(((i + 1) / len(final_listings)) * 35) # Item progress from 60% to 95%
                search_status["progress"] = item_progress
                search_status["message"] = f"Coletando dados ({i+1}/{len(final_listings)})..."
                add_debug_log(f"🏪 Processando estabelecimento {i+1}/{len(final_listings)}")

                try:
                    # Click result and wait for details
                    listing = listing_link.locator("xpath=..") # Parent element often contains more data
                    listing.click()
                    name_xpath = '//h1[contains(@class, "DUwDvf")] | //div[contains(@class, "fontHeadlineLarge")]/span'
                    page.wait_for_selector(name_xpath, timeout=15000)
                    page.wait_for_timeout(1500) # Extra wait for dynamic content

                    # Extract data
                    name = extract_data(name_xpath, page)
                    add_debug_log(f"  📝 Nome: {name}")
                    place_type = extract_data('//button[contains(@jsaction, "category")]', page)
                    address = extract_data('//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]', page)
                    phone = extract_data('//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]', page)
                    website = extract_data('//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]', page)
                    opening_hours = extract_data('//button[contains(@data-item-id, "oh")] | //div[contains(@aria-label, "Horário")]', page)
                    intro = extract_data('//div[contains(@class, "WeS02d")]//div[contains(@class, "PYvSYb")]', page)

                    # Extract reviews
                    reviews_xpath = '//div[contains(@class, "F7nice")]'
                    rev_count = "N/A"
                    rev_avg = "N/A"
                    if page.locator(reviews_xpath).count() > 0:
                        review_text = page.locator(reviews_xpath).first.inner_text()
                        parts = review_text.split()
                        try: rev_avg = float(parts[0].replace(",", "."))
                        except: pass
                        try:
                            count_part = parts[1].strip("()[]").replace(".", "").replace(",", "")
                            rev_count = int(count_part)
                        except:
                            try: # Fallback using aria-label
                                count_span_xpath = reviews_xpath + '//span[@aria-label]'
                                if page.locator(count_span_xpath).count() > 0:
                                    aria_label = page.locator(count_span_xpath).first.get_attribute("aria-label")
                                    count_part = aria_label.split()[0].replace(".", "").replace(",", "")
                                    rev_count = int(count_part)
                            except: pass

                    # Extract services
                    info_xpath_base = '//div[contains(@class, "LTs0Rc")] | //div[contains(@class, "iP2t7d")]'
                    store_shopping = False
                    in_store_pickup = False
                    delivery = False
                    info_elements = page.locator(info_xpath_base).all()
                    for info_element in info_elements:
                        info_text = info_element.inner_text().lower()
                        if "compra" in info_text or "shop" in info_text: store_shopping = True
                        if "retira" in info_text or "pickup" in info_text: in_store_pickup = True
                        if "entrega" in info_text or "delivery" in info_text: delivery = True

                    result = {
                        "name": name, "type": place_type, "address": address, "phone": phone,
                        "website": website, "opening_hours": opening_hours, "average_rating": rev_avg,
                        "review_count": rev_count, "introduction": intro, "store_shopping": store_shopping,
                        "in_store_pickup": in_store_pickup, "delivery": delivery
                    }
                    local_results.append(result)
                    add_debug_log(f"  ✅ Dados coletados para {name}")

                except Exception as item_error:
                    add_debug_log(f"⚠️ Erro ao processar estabelecimento {i+1}: {item_error}. Pulando item.")
                    # Optionally add a placeholder or skip
                    continue # Move to the next item

            # --- Success Case ---
            search_status["progress"] = 100
            search_status["message"] = "Coleta concluída com sucesso!"
            add_debug_log(f"✅ Coleta concluída. {len(local_results)} resultados processados.")

        except Exception as e:
            # --- Main Error Handling ---
            error_message = f"Erro durante a execução do scraper: {str(e)}"
            add_debug_log(f"❌ ERRO FATAL: {error_message}")
            traceback.print_exc() # Print full traceback to server console
            search_status["error"] = error_message
            search_status["message"] = "Ocorreu um erro durante a coleta."
            # Set progress to 100 or a specific error state? Let's keep it where it failed.
            # search_status["progress"] = 100

        finally:
            # --- Cleanup ---
            search_status["is_running"] = False
            if browser:
                try:
                    browser.close()
                    add_debug_log("🤖 Navegador fechado.")
                except Exception as close_err:
                    add_debug_log(f"⚠️ Erro ao fechar o navegador: {close_err}")
            # Update global results only at the end
            global search_results
            search_results = local_results
            add_debug_log(f"🏁 Processo finalizado. Retornando {len(local_results)} resultados.")
            # Return results from the function scope
            # Note: The Flask part will access the global `search_results`

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_search', methods=['POST'])
def start_search():
    global search_params, search_status, search_results
    if search_status["is_running"]:
        return jsonify({"error": "A search is already in progress."}), 400

    data = request.json
    establishment_type = data.get('establishment_type')
    location = data.get('location')
    max_results = int(data.get('max_results', 20)) # Default to 20 if not provided

    if not establishment_type or not location:
        return jsonify({"error": "Establishment type and location are required."}), 400

    search_params = {
        'establishment_type': establishment_type,
        'location': location,
        'max_results': max_results
    }
    search_results = [] # Clear previous results
    search_status = {
        "is_running": True,
        "progress": 0,
        "message": "Iniciando busca...",
        "error": None,
        "total_found": 0,
        "debug_logs": []
    }

    # Start the scraper in a separate thread
    thread = threading.Thread(target=run_scraper_wrapper, args=(establishment_type, location, max_results))
    thread.daemon = True # Allows app to exit even if thread is running
    thread.start()

    return jsonify({"message": "Search started successfully."})

# Wrapper function to handle the global state update within the thread
def run_scraper_wrapper(establishment_type, location, max_results):
    global search_results, search_status
    try:
        # The scrape_google_maps function now handles its own status updates and error logging
        scrape_google_maps(establishment_type, location, max_results)
        # Note: scrape_google_maps updates the global search_results internally now
    except Exception as e:
        # This catches errors if scrape_google_maps itself fails catastrophically before its own try/except
        error_msg = f"Erro fatal no wrapper do scraper: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        search_status["error"] = error_msg
        search_status["message"] = "Erro crítico ao executar a coleta."
        search_status["is_running"] = False
        search_status["progress"] = 100 # Indicate completion, albeit with error

@app.route('/status')
def get_status():
    global search_status
    # Add memory usage to status for monitoring
    status_copy = search_status.copy()
    status_copy['memory_mb'] = check_memory_usage()
    return jsonify(status_copy)

@app.route('/results')
def get_results():
    global search_results
    return jsonify(search_results)

@app.route('/download_results')
def download_results():
    global search_results
    if not search_results:
        return "Nenhum resultado para baixar.", 404

    # Create JSON file in memory
    json_data = json.dumps(search_results, indent=4, ensure_ascii=False)
    mem_file = io.BytesIO()
    mem_file.write(json_data.encode('utf-8'))
    mem_file.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"google_maps_results_{timestamp}.json"

    return send_file(
        mem_file,
        mimetype='application/json',
        as_attachment=True,
        download_name=filename
    )

if __name__ == '__main__':
    # Make sure the static folder exists if needed for CSS/JS
    if not os.path.exists('static'):
        os.makedirs('static')
    # Make sure templates folder exists
    if not os.path.exists('templates'):
        os.makedirs('templates')
        # Create a basic index.html if it doesn't exist
        if not os.path.exists('templates/index.html'):
             with open('templates/index.html', 'w') as f:
                 f.write('<html><head><title>Scraper</title></head><body><h1>Scraper Interface</h1><p>Placeholder</p></body></html>')

    # Run Flask app
    # Use host='0.0.0.0' to make it accessible externally if needed
    app.run(debug=True, host='0.0.0.0', port=5000)

