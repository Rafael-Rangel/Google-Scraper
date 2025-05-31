from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import json
import pandas as pd
import time
import threading
import traceback
from datetime import datetime
import subprocess
import io
import os

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

# Caminho para o script de scraping
SCRAPER_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "scraper.py")

# Função para executar o scraper em uma thread separada
def run_scraper(establishment_type, location, max_results):
    global search_results, search_status
    
    try:
        search_status["is_running"] = True
        search_status["progress"] = 10
        search_status["message"] = "Iniciando coleta de dados..."
        search_status["error"] = None
        
        # Construir o comando para executar o script de scraping
        search_query = f"{establishment_type} em {location}"
        command = [
            "python", 
            SCRAPER_SCRIPT_PATH, 
            "-s", search_query, 
            "-t", str(max_results)
        ]
        
        search_status["progress"] = 20
        search_status["message"] = "Executando script de coleta..."
        
        # Executar o script como um processo separado
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Monitorar o progresso
        while True:
            output_line = process.stdout.readline()
            if not output_line and process.poll() is not None:
                break
            
            if "Total Found:" in output_line:
                try:
                    total_found = int(output_line.split("Total Found:")[1].strip())
                    search_status["total_found"] = total_found
                    search_status["progress"] = 40
                    search_status["message"] = f"Encontrados {total_found} estabelecimentos..."
                except:
                    pass
            
            if "Coletando dados do estabelecimento" in output_line:
                try:
                    current, total = output_line.split("estabelecimento")[1].split("/")
                    current = int(current.strip())
                    total = int(total.split("]")[0].strip())
                    progress = min(40 + int((current / total) * 50), 90)
                    search_status["progress"] = progress
                    search_status["message"] = f"Coletando dados ({current}/{total})..."
                except:
                    pass
        
        # Verificar se houve erro
        stderr_output = process.stderr.read()
        if stderr_output:
            search_status["error"] = stderr_output
            search_status["message"] = "Erro durante a coleta de dados."
            search_status["progress"] = 0
            search_status["is_running"] = False
            return
        
        # Ler o arquivo de resultados
        search_status["progress"] = 95
        search_status["message"] = "Processando resultados..."
        
        # Tentar ler o arquivo TXT e converter para estrutura de dados
        try:
            results_file_path = os.path.join(os.path.dirname(__file__), "resultados.txt")
            
            if os.path.exists(results_file_path):
                with open(results_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Processar o conteúdo do arquivo TXT para extrair os dados estruturados
                sections = content.split("------------------------------")
                
                # Limpar a lista de resultados
                search_results.clear()
                
                # Processar cada seção (cada estabelecimento)
                for section in sections:
                    if not section.strip():
                        continue
                    
                    result = {}
                    lines = section.strip().split('\n')
                    
                    for line in lines:
                        if not line.strip():
                            continue
                        
                        if ': ' in line:
                            key, value = line.split(': ', 1)
                            
                            # Mapear as chaves do TXT para as chaves do JSON
                            key_mapping = {
                                'Nome': 'name',
                                'Tipo': 'type',
                                'Endereço': 'address',
                                'Telefone': 'phone',
                                'Website': 'website',
                                'Horário': 'opening_hours',
                                'Avaliação Média': 'average_rating',
                                'Contagem de Avaliações': 'review_count',
                                'Introdução': 'introduction',
                                'Compras na Loja': 'store_shopping',
                                'Retirada na Loja': 'in_store_pickup',
                                'Entrega': 'delivery'
                            }
                            
                            if key in key_mapping:
                                json_key = key_mapping[key]
                                
                                # Converter valores booleanos
                                if value in ['Sim', 'Yes']:
                                    result[json_key] = True
                                elif value in ['Não', 'No']:
                                    result[json_key] = False
                                else:
                                    # Tentar converter números
                                    try:
                                        if '.' in value:
                                            result[json_key] = float(value)
                                        else:
                                            result[json_key] = int(value)
                                    except:
                                        result[json_key] = value
                    
                    if result:  # Se o dicionário não estiver vazio
                        search_results.append(result)
            
            search_status["total_found"] = len(search_results)
        except Exception as e:
            search_status["error"] = str(e)
            search_status["message"] = "Erro ao processar resultados."
            search_status["progress"] = 0
            search_status["is_running"] = False
            return
        
        search_status["progress"] = 100
        search_status["message"] = "Coleta concluída com sucesso!"
        search_status["is_running"] = False
        
    except Exception as e:
        search_status["error"] = str(e)
        search_status["message"] = "Erro durante a coleta de dados."
        search_status["progress"] = 0
        search_status["is_running"] = False
        traceback.print_exc()

@app.route('/')
def index():
    return app.send_static_file('index.html')

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
    return app.send_static_file('results.html')

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

@app.route('/export/excel')
def export_excel():
    try:
        # Verificar se há resultados
        if not search_results:
            return jsonify({"error": "Nenhum resultado disponível para exportação."}), 404
        
        # Converter para DataFrame
        df = pd.DataFrame(search_results)
        
        # Criar um objeto de arquivo em memória
        buffer = io.BytesIO()
        
        # Escrever para Excel
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Resultados')
        
        buffer.seek(0)
        
        # Gerar nome do arquivo com timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"resultados_{timestamp}.xlsx"
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Garantir que o diretório static existe
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    os.makedirs(static_dir, exist_ok=True)
    
    print("Iniciando Google Maps Scraper Web...")
    print("Acesse http://localhost:5000 no seu navegador")
    app.run(host='0.0.0.0', port=5000, debug=True)
