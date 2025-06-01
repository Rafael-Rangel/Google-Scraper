# Função principal de scraping melhorada
def scrape_google_maps(search_query, max_results):
    """Função principal para scraping do Google Maps."""
    global search_status
    
    # Listas para armazenar dados
    results = []
    
    with sync_playwright() as p:
        search_status["progress"] = 15
        search_status["message"] = "Iniciando navegador..."
        
        # Iniciar navegador em modo headless (invisível) com configurações otimizadas
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-extensions',
                '--no-sandbox',
                '--disable-dev-shm-usage'
            ]
        )
        
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        try:
            search_status["progress"] = 20
            search_status["message"] = "Acessando Google Maps..."
            
            # Acessar Google Maps
            page.goto("https://www.google.com/maps", timeout=60000)
            page.wait_for_timeout(3000)
            
            # Buscar pelo termo
            search_status["progress"] = 25
            search_status["message"] = f"Buscando por: {search_query}..."
            
            search_box = page.locator('//input[@id="searchboxinput"]')
            search_box.fill(search_query)
            page.wait_for_timeout(1000)
            search_box.press("Enter")
            
            # Esperar pelos resultados com múltiplos seletores
            results_selectors = [
                '//a[contains(@href, "https://www.google.com/maps/place")]',
                '//div[@role="article"]',
                '//div[contains(@class, "Nv2PK")]'
            ]
            
            results_xpath = None
            for selector in results_selectors:
                try:
                    page.wait_for_selector(selector, timeout=15000)
                    if page.locator(selector).count() > 0:
                        results_xpath = selector
                        break
                except:
                    continue
            
            if not results_xpath:
                search_status["error"] = f"Não foi possível encontrar resultados para '{search_query}'"
                browser.close()
                return []
            
            search_status["message"] = "Resultados encontrados, carregando mais..."
            
            # Scroll melhorado para carregar mais resultados
            search_status["progress"] = 30
            search_status["message"] = "Carregando mais resultados..."
            
            # Localizar o painel de resultados para fazer scroll
            results_panel_selectors = [
                '//div[@role="main"]',
                '//div[contains(@class, "m6QErb")]',
                '//div[contains(@class, "siAUzd")]'
            ]
            
            results_panel = None
            for selector in results_panel_selectors:
                if page.locator(selector).count() > 0:
                    results_panel = page.locator(selector).first
                    break
            
            previously_counted = 0
            scroll_attempts = 0
            max_scroll_attempts = 50  # Aumentado
            stagnant_attempts = 0
            max_stagnant = 5
            
            while scroll_attempts < max_scroll_attempts and stagnant_attempts < max_stagnant:
                # Scroll no painel de resultados se disponível, senão na página
                if results_panel:
                    try:
                        results_panel.scroll_into_view_if_needed()
                        page.mouse.wheel(0, 5000)
                    except:
                        page.mouse.wheel(0, 5000)
                else:
                    page.mouse.wheel(0, 5000)
                
                # Esperar mais tempo para carregar
                page.wait_for_timeout(3000)
                
                # Verificar se apareceu o botão "Mais resultados" e clicar
                try:
                    more_button = page.locator('//button[contains(text(), "Mais") or contains(text(), "More")]')
                    if more_button.count() > 0:
                        more_button.first.click()
                        page.wait_for_timeout(2000)
                except:
                    pass
                
                current_count = page.locator(results_xpath).count()
                search_status["message"] = f"Encontrados {current_count} resultados até agora..."
                
                if current_count >= max_results:
                    break
                    
                if current_count == previously_counted:
                    stagnant_attempts += 1
                    # Tentar scroll mais agressivo quando estagnado
                    page.mouse.wheel(0, 10000)
                    page.wait_for_timeout(2000)
                else:
                    stagnant_attempts = 0
                    previously_counted = current_count
                
                scroll_attempts += 1
                
                # Scroll até o final da página também
                if scroll_attempts % 5 == 0:
                    page.keyboard.press("End")
                    page.wait_for_timeout(2000)
            
            # Tentar mais alguns scrolls forçados no final
            for _ in range(5):
                page.keyboard.press("End")
                page.wait_for_timeout(1000)
                page.mouse.wheel(0, 10000)
                page.wait_for_timeout(2000)
                
                new_count = page.locator(results_xpath).count()
                if new_count > current_count:
                    current_count = new_count
                    search_status["message"] = f"Encontrados {current_count} resultados..."
                    if current_count >= max_results:
                        break
            
            # Obter todos os resultados
            page.wait_for_timeout(2000)
            all_listings = page.locator(results_xpath).all()
            
            # Filtrar apenas links válidos de estabelecimentos
            valid_listings = []
            for listing in all_listings:
                try:
                    href = listing.get_attribute('href')
                    if href and 'place' in href and 'maps' in href:
                        valid_listings.append(listing)
                except:
                    continue
            
            if len(valid_listings) > max_results:
                valid_listings = valid_listings[:max_results]
            
            search_status["total_found"] = len(valid_listings)
            search_status["message"] = f"Encontrados {len(valid_listings)} estabelecimentos válidos. Coletando detalhes..."
            
            # Processar cada resultado com tratamento melhorado
            successful_extractions = 0
            
            for i, listing_link in enumerate(valid_listings):
                progress = 40 + int((i / len(valid_listings)) * 50)
                search_status["progress"] = progress
                search_status["message"] = f"Coletando dados ({i+1}/{len(valid_listings)}) - {successful_extractions} sucessos..."
                
                try:
                    # Scroll para o elemento antes de clicar
                    listing_link.scroll_into_view_if_needed()
                    page.wait_for_timeout(500)
                    
                    # Clicar no resultado
                    listing_link.click()
                    page.wait_for_timeout(2000)
                    
                    # Esperar pelo carregamento dos detalhes com múltiplos seletores
                    name_selectors = [
                        '//h1[contains(@class, "DUwDvf")]',
                        '//div[contains(@class, "fontHeadlineLarge")]/span',
                        '//h1[@data-attrid="title"]',
                        '//span[contains(@class, "DUwDvf")]'
                    ]
                    
                    name_found = False
                    for selector in name_selectors:
                        try:
                            page.wait_for_selector(selector, timeout=10000)
                            if page.locator(selector).count() > 0:
                                name_found = True
                                break
                        except:
                            continue
                    
                    if not name_found:
                        continue
                    
                    page.wait_for_timeout(2000)
                    
                    # Extrair dados com fallbacks múltiplos
                    name = extract_data_multiple([
                        '//h1[contains(@class, "DUwDvf")]',
                        '//div[contains(@class, "fontHeadlineLarge")]/span',
                        '//span[contains(@class, "DUwDvf")]'
                    ], page)
                    
                    place_type = extract_data_multiple([
                        '//button[contains(@jsaction, "category")]',
                        '//div[contains(@class, "DkEaL")]'
                    ], page)
                    
                    address = extract_data_multiple([
                        '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]',
                        '//div[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]',
                        '//button[contains(@data-value, "Address")]//div[contains(@class, "fontBodyMedium")]'
                    ], page)
                    
                    phone = extract_data_multiple([
                        '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]',
                        '//button[contains(@aria-label, "Phone")]//div[contains(@class, "fontBodyMedium")]',
                        '//a[contains(@href, "tel:")]'
                    ], page)
                    
                    website = extract_data_multiple([
                        '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]',
                        '//a[contains(@href, "http") and not(contains(@href, "google"))]',
                        '//button[@data-item-id="authority"]//div'
                    ], page)
                    
                    opening_hours = extract_data_multiple([
                        '//button[contains(@data-item-id, "oh")]',
                        '//div[contains(@aria-label, "Hours")]',
                        '//button[contains(@jsaction, "hours")]'
                    ], page)
                    
                    intro = extract_data_multiple([
                        '//div[contains(@class, "WeS02d")]//div[contains(@class, "PYvSYb")]',
                        '//div[contains(@class, "review-dialog-top")]//span'
                    ], page)
                    
                    # Extrair avaliações com múltiplas tentativas
                    reviews_selectors = [
                        '//div[contains(@class, "F7nice")]',
                        '//span[contains(@aria-label, "rating")]',
                        '//div[contains(@class, "TI5OEe")]'
                    ]
                    
                    rev_count = "N/A"
                    rev_avg = "N/A"
                    
                    for selector in reviews_selectors:
                        if page.locator(selector).count() > 0:
                            try:
                                review_text = page.locator(selector).first.inner_text()
                                # Tentar extrair nota e número de avaliações
                                import re
                                rating_match = re.search(r'(\d+[,.]?\d*)', review_text)
                                if rating_match:
                                    rev_avg = float(rating_match.group(1).replace(',', '.'))
                                
                                count_match = re.search(r'\((\d+(?:[.,]\d+)*)\)', review_text)
                                if count_match:
                                    rev_count = int(count_match.group(1).replace(',', '').replace('.', ''))
                                break
                            except:
                                continue
                    
                    # Se extraiu pelo menos o nome, considera sucesso
                    if name != "N/A":
                        # Extrair informações de serviços
                        info_xpath_base = '//div[contains(@class, "LTs0Rc")] | //div[contains(@class, "iP2t7d")]'
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
                        except:
                            pass
                        
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
                        successful_extractions += 1
                    
                except Exception as e:
                    print(f"Erro ao processar resultado {i+1}: {str(e)}")
                    continue
                
                # Pausa menor entre requisições
                page.wait_for_timeout(300)
            
            search_status["progress"] = 95
            search_status["message"] = f"Finalizando... {successful_extractions} estabelecimentos coletados com sucesso."
            
        except Exception as e:
            search_status["error"] = str(e)
            search_status["message"] = f"Erro durante a coleta: {str(e)}"
            print(f"Erro geral: {str(e)}")
        finally:
            browser.close()
    
    return results

# Função auxiliar para extrair dados com múltiplos seletores
def extract_data_multiple(xpaths, page):
    """Extrai texto tentando múltiplos XPaths."""
    for xpath in xpaths:
        try:
            if page.locator(xpath).count() > 0:
                data = page.locator(xpath).first.inner_text().strip()
                if data and data != "":
                    return data
        except Exception:
            continue
    return "N/A"
