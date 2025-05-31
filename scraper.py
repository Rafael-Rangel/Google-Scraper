from playwright.sync_api import sync_playwright
import pandas as pd
import argparse
import time
import os
import sys

# Initialize lists to store scraped data
names_list=[]
address_list=[]
website_list=[]
phones_list=[]
reviews_c_list=[]
reviews_a_list=[]
store_s_list=[]
in_store_list=[]
store_del_list=[]
place_t_list=[]
open_list=[]
intro_list=[]

def extract_data(xpath, data_list, page):
    """Safely extracts text from a given XPath, appending to a list."""
    try:
        if page.locator(xpath).count() > 0:
            data = page.locator(xpath).first.inner_text() # Use .first to avoid issues if multiple elements match
        else:
            data = "N/A"
    except Exception as e:
        # print(f"Error extracting data for xpath {xpath}: {e}") # Optional: for debugging
        data = "N/A" # Default to N/A on error
    data_list.append(data)

def main():
    with sync_playwright() as p:
        # Launch browser - Prioritize Chrome path for Windows, fallback to Playwright's Chromium
        browser = None
        try:
            # Try launching with specified Windows Chrome path first
            browser = p.chromium.launch(executable_path='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless=False)
        except Exception:
            try:
                # Fallback to Playwright's default Chromium if Chrome path fails or not on Windows
                browser = p.chromium.launch(headless=False)
            except Exception as e:
                print(f"Erro fatal: Não foi possível iniciar o navegador Chromium. Verifique a instalação do Playwright.")
                print(f"Detalhes do erro: {e}")
                return # Exit if browser cannot be launched

        page = browser.new_page()

        try:
            page.goto("https://www.google.com/maps", timeout=60000) # Go to base Maps URL
            page.wait_for_timeout(2000) # Allow time for page load

            # Search for the place
            page.locator('//input[@id="searchboxinput"]').fill(search_for)
            page.wait_for_timeout(1000) # Wait a bit after filling
            page.keyboard.press("Enter")
            print(f"Buscando por: {search_for}...")

            # Wait for search results to appear
            results_xpath = '//a[contains(@href, "https://www.google.com/maps/place")]'
            try:
                page.wait_for_selector(results_xpath, timeout=30000) # Wait up to 30 seconds for results
                print("Resultados encontrados, iniciando rolagem...")
            except Exception as e:
                print(f"Não foi possível encontrar resultados para \"{search_for}\" ou a página demorou muito para carregar.")
                print(f"Detalhes: {e}")
                browser.close()
                return

            # Scroll down to load more results
            page.hover(results_xpath) # Hover to ensure focus for scrolling
            previously_counted = 0
            scroll_attempts = 0
            max_scroll_attempts = 15 # Limit scroll attempts to prevent infinite loops

            while scroll_attempts < max_scroll_attempts:
                page.mouse.wheel(0, 10000) # Scroll down
                page.wait_for_timeout(2000) # Wait for content to load

                current_count = page.locator(results_xpath).count()

                if current_count >= total:
                    print(f"Número desejado de resultados ({total}) alcançado.")
                    break
                if current_count == previously_counted:
                    print(f"Não foram encontrados mais resultados após rolagem. Total: {current_count}")
                    break
                else:
                    previously_counted = current_count
                    print(f"Resultados encontrados até agora: {current_count}")
                    scroll_attempts += 1

            if scroll_attempts == max_scroll_attempts:
                print("Máximo de tentativas de rolagem atingido.")

            listings = page.locator(results_xpath).all()
            if len(listings) > total:
                 listings = listings[:total] # Limit to the requested total

            print(f"Total Found: {len(listings)}")
            print(f"Iniciando coleta de dados para {len(listings)} estabelecimentos...")

            # --- Scraping individual listings ---
            for i, listing_link in enumerate(listings):
                print(f"Coletando dados do estabelecimento {i+1}/{len(listings)}...")
                try:
                    listing = listing_link.locator("xpath=..") # Get the parent element
                    listing.click()
                    # Wait for the details panel to update, specifically for the name
                    name_xpath = '//div[contains(@class, "fontHeadlineLarge")]/span[contains(@class, "fontHeadlineLarge")] | //h1[contains(@class, "DUwDvf")]'
                    try:
                        page.wait_for_selector(name_xpath, timeout=15000) # Wait up to 15 seconds for name
                    except Exception:
                        print(f"  [Aviso] Demorou muito para carregar detalhes do estabelecimento {i+1}. Pulando.")
                        # Attempt to go back or refresh might be needed here in a more robust scraper
                        continue # Skip to the next listing

                    page.wait_for_timeout(1500) # Extra small delay for content rendering

                    # Define XPaths for data extraction (using more robust selectors where possible)
                    address_xpath = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
                    website_xpath = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
                    phone_number_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
                    # Combined reviews count and average (handle potential variations)
                    reviews_xpath = '//div[contains(@class, "F7nice")]'
                    # Service options (check multiple possible divs)
                    info_xpath_base = '//div[contains(@class, "LTs0Rc")] | //div[contains(@class, "iP2t7d")]'
                    # Opening hours (might need refinement)
                    opens_at_xpath = '//button[contains(@data-item-id, "oh")] | //div[contains(@aria-label, "Horário")]'
                    # Place type
                    place_type_xpath = '//button[contains(@jsaction, "category")]'
                    # Introduction/Description
                    intro_xpath = '//div[contains(@class, "WeS02d")]//div[contains(@class, "PYvSYb")]'

                    # --- Extract Data --- 
                    extract_data(name_xpath, names_list, page)
                    extract_data(place_type_xpath, place_t_list, page)
                    extract_data(address_xpath, address_list, page)
                    extract_data(phone_number_xpath, phones_list, page)
                    extract_data(website_xpath, website_list, page)

                    # Extract Reviews (Count and Average)
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
                            # Extract count, removing parentheses and commas
                            count_part = parts[1].strip("()").replace(",", "")
                            rev_count = int(count_part)
                        except (ValueError, IndexError):
                             # Try finding count in a different span if first fails
                             count_span_xpath = reviews_xpath + '//span[@aria-label]'
                             if page.locator(count_span_xpath).count() > 0:
                                 try:
                                     count_part = page.locator(count_span_xpath).first.get_attribute("aria-label").split()[0].replace(",", "")
                                     rev_count = int(count_part)
                                 except (ValueError, IndexError, AttributeError):
                                     rev_count = "N/A"
                             else:
                                 rev_count = "N/A"
                    reviews_a_list.append(rev_avg)
                    reviews_c_list.append(rev_count)

                    # Extract Service Info (Shopping, Pickup, Delivery)
                    store_shopping_flag = "No"
                    in_store_pickup_flag = "No"
                    store_delivery_flag = "No"
                    info_elements = page.locator(info_xpath_base).all()
                    for info_element in info_elements:
                        info_text = info_element.inner_text().lower()
                        if "compra" in info_text or "shop" in info_text:
                            store_shopping_flag = "Yes"
                        if "retira" in info_text or "pickup" in info_text:
                            in_store_pickup_flag = "Yes"
                        if "entrega" in info_text or "delivery" in info_text:
                            store_delivery_flag = "Yes"
                    store_s_list.append(store_shopping_flag)
                    in_store_list.append(in_store_pickup_flag)
                    store_del_list.append(store_delivery_flag)

                    # Extract Opening Hours
                    extract_data(opens_at_xpath, open_list, page)
                    # Extract Introduction
                    extract_data(intro_xpath, intro_list, page)

                except Exception as e:
                    print(f"  [Erro] Ocorreu um erro ao coletar dados do estabelecimento {i+1}: {e}")
                    # Append N/A to all lists to maintain alignment if an error occurs for one listing
                    names_list.append("Erro na Coleta")
                    place_t_list.append("N/A")
                    address_list.append("N/A")
                    phones_list.append("N/A")
                    website_list.append("N/A")
                    reviews_a_list.append("N/A")
                    reviews_c_list.append("N/A")
                    store_s_list.append("N/A")
                    in_store_list.append("N/A")
                    store_del_list.append("N/A")
                    open_list.append("N/A")
                    intro_list.append("N/A")
                finally:
                    # Optional: Add a small delay between listings to avoid overwhelming the site
                    page.wait_for_timeout(500)

            # --- Export to TXT --- Start
            output_filename = "resultados.txt"
            print(f"\nExportando dados para {output_filename}...")
            try:
                with open(output_filename, 'w', encoding='utf-8') as f:
                    f.write(f"Resultados da busca por: {search_for}\n")
                    f.write(f"Total de estabelecimentos coletados: {len(names_list)}\n")
                    f.write("="*40 + "\n\n")

                    for i in range(len(names_list)):
                        # Check if index exists before accessing, safety measure
                        def get_item(lst, index, default='N/A'):
                            try:
                                item = lst[index]
                                return item if item else default # Return default if item is empty string
                            except IndexError:
                                return default

                        f.write(f"Nome: {get_item(names_list, i)}\n")
                        f.write(f"Tipo: {get_item(place_t_list, i)}\n")
                        f.write(f"Endereço: {get_item(address_list, i)}\n")
                        f.write(f"Telefone: {get_item(phones_list, i)}\n")
                        f.write(f"Website: {get_item(website_list, i)}\n")
                        f.write(f"Horário: {get_item(open_list, i)}\n")
                        f.write(f"Avaliação Média: {get_item(reviews_a_list, i)}\n")
                        f.write(f"Contagem de Avaliações: {get_item(reviews_c_list, i)}\n")
                        f.write(f"Introdução: {get_item(intro_list, i)}\n")
                        f.write(f"Compras na Loja: {get_item(store_s_list, i)}\n")
                        f.write(f"Retirada na Loja: {get_item(in_store_list, i)}\n")
                        f.write(f"Entrega: {get_item(store_del_list, i)}\n")
                        f.write("---"*10 + "\n\n") # Separator
                print(f"Dados exportados com sucesso para {output_filename}")
            except Exception as e:
                print(f"Erro ao exportar para TXT: {e}")
            # --- Export to TXT --- End

        except Exception as e:
            print(f"Ocorreu um erro inesperado durante a execução: {e}")
        finally:
            if browser:
                browser.close()
                print("Navegador fechado.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coleta dados de estabelecimentos do Google Maps.")
    parser.add_argument("-s", "--search", type=str, required=True, help="Termo de busca (ex: \"farmácias em Campo Grande\")")
    parser.add_argument("-t", "--total", type=int, required=True, help="Número máximo de resultados a coletar")
    args = parser.parse_args()

    search_for = args.search
    total = args.total

    main()
