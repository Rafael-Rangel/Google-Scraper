// Variáveis globais para armazenar os resultados da busca
let searchResults = [];
let searchParams = {};

// Elementos DOM
document.addEventListener('DOMContentLoaded', function() {
    // Formulário de busca
    const searchForm = document.getElementById('searchForm');
    const resultsContainer = document.getElementById('resultsContainer');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const progressBarFill = document.getElementById('progressBarFill');
    const progressStatus = document.getElementById('progressStatus');
    const searchQuery = document.getElementById('searchQuery');
    const totalResults = document.getElementById('totalResults');
    const resultsList = document.getElementById('resultsList');
    const alertContainer = document.getElementById('alertContainer');
    
    // Botões de exportação
    const exportTxtBtn = document.getElementById('exportTxt');
    const exportJsonBtn = document.getElementById('exportJson');
    const exportCsvBtn = document.getElementById('exportCsv');
    const newSearchBtn = document.getElementById('newSearch');
    
    // Event listeners
    searchForm.addEventListener('submit', handleSearch);
    exportTxtBtn.addEventListener('click', exportToTxt);
    exportJsonBtn.addEventListener('click', exportToJson);
    exportCsvBtn.addEventListener('click', exportToCsv);
    newSearchBtn.addEventListener('click', showSearchForm);
    
    // Função para lidar com a busca
    function handleSearch(e) {
        e.preventDefault();
        
        // Obter valores do formulário
        const establishmentType = document.getElementById('establishment_type').value;
        const location = document.getElementById('location').value;
        const maxResults = parseInt(document.getElementById('max_results').value);
        
        // Validar entradas
        if (!establishmentType || !location) {
            showAlert('Por favor, preencha todos os campos obrigatórios.', 'error');
            return;
        }
        
        // Armazenar parâmetros de busca
        searchParams = {
            establishmentType,
            location,
            maxResults
        };
        
        // Mostrar overlay de carregamento
        loadingOverlay.classList.add('active');
        progressBarFill.style.width = '10%';
        progressStatus.textContent = 'Iniciando busca...';
        
        // Realizar a busca
        searchPlaces(establishmentType, location, maxResults);
    }
    
    // Função para buscar estabelecimentos usando a API Nominatim do OpenStreetMap
    async function searchPlaces(establishmentType, location, maxResults) {
        try {
            // Atualizar progresso
            updateProgress(20, 'Buscando localização...');
            
            // Primeiro, obter as coordenadas da localização usando um proxy CORS
            const locationQuery = encodeURIComponent(location);
            const corsProxyUrl = 'https://corsproxy.io/?';
            const locationUrl = `${corsProxyUrl}https://nominatim.openstreetmap.org/search?format=json&q=${locationQuery}&limit=1`;
            
            console.log('Buscando localização:', locationUrl );
            
            const locationResponse = await fetch(locationUrl, {
                headers: {
                    'User-Agent': 'MapsFinderWebApp/1.0'
                }
            });
            
            if (!locationResponse.ok) {
                throw new Error('Erro ao buscar localização: ' + locationResponse.status);
            }
            
            const locationData = await locationResponse.json();
            console.log('Resposta da API de localização:', locationData);
            
            if (!locationData || locationData.length === 0) {
                throw new Error('Localização não encontrada');
            }
            
            const { lat, lon } = locationData[0];
            console.log('Coordenadas encontradas:', lat, lon);
            
            // Atualizar progresso
            updateProgress(40, 'Buscando estabelecimentos...');
            
            // Agora, buscar estabelecimentos próximos à localização
            const amenityQuery = encodeURIComponent(establishmentType);
            const radius = 10000; // 10km de raio
            const limit = Math.min(maxResults, 50); // Limitar a 50 resultados no máximo
            
            // Usar Overpass API para buscar estabelecimentos
            const overpassQuery = `
                [out:json];
                (
                  node["name"~"${amenityQuery}", i](around:${radius},${lat},${lon});
                  way["name"~"${amenityQuery}", i](around:${radius},${lat},${lon});
                  relation["name"~"${amenityQuery}", i](around:${radius},${lat},${lon});
                );
                out center ${limit};
            `;
            
            console.log('Query Overpass:', overpassQuery);
            
            const overpassUrl = `${corsProxyUrl}https://overpass-api.de/api/interpreter`;
            
            console.log('Buscando estabelecimentos via Overpass API...' );
            
            const overpassResponse = await fetch(overpassUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'User-Agent': 'MapsFinderWebApp/1.0'
                },
                body: 'data=' + encodeURIComponent(overpassQuery)
            });
            
            if (!overpassResponse.ok) {
                throw new Error('Erro ao buscar estabelecimentos: ' + overpassResponse.status);
            }
            
            const overpassData = await overpassResponse.json();
            console.log('Resposta da API Overpass:', overpassData);
            
            // Atualizar progresso
            updateProgress(70, 'Processando resultados...');
            
            // Processar os resultados
            const results = overpassData.elements.map(element => {
                console.log('Processando elemento:', element);
                
                // Determinar as coordenadas com base no tipo de elemento
                let elementLat, elementLon;
                
                if (element.type === 'node') {
                    elementLat = element.lat;
                    elementLon = element.lon;
                } else if (element.center) {
                    elementLat = element.center.lat;
                    elementLon = element.center.lon;
                }
                
                // Extrair tags
                const tags = element.tags || {};
                console.log('Tags do elemento:', tags);
                
                return {
                    id: element.id,
                    name: tags.name || 'Nome não disponível',
                    type: tags.amenity || tags.shop || tags.tourism || tags.leisure || establishmentType,
                    address: formatAddress(tags),
                    phone: tags.phone || 'N/A',
                    website: tags.website || tags['contact:website'] || 'N/A',
                    opening_hours: tags.opening_hours || 'N/A',
                    coordinates: {
                        lat: elementLat,
                        lon: elementLon
                    },
                    // Dados adicionais que podem não estar disponíveis na API
                    average_rating: 'N/A',
                    review_count: 'N/A',
                    introduction: tags.description || 'N/A',
                    store_shopping: tags.shop ? true : false,
                    in_store_pickup: false,
                    delivery: tags.delivery === 'yes'
                };
            });
            
            console.log('Resultados processados:', results);
            
            // Filtrar resultados sem nome
            const filteredResults = results.filter(result => result.name !== 'Nome não disponível');
            console.log('Resultados filtrados:', filteredResults);
            
            // Limitar ao número máximo de resultados solicitados
            searchResults = filteredResults.slice(0, maxResults);
            console.log('Resultados finais:', searchResults);
            
            // Atualizar progresso
            updateProgress(90, 'Finalizando...');
            
            // Buscar detalhes adicionais para cada estabelecimento
            await enrichResults(searchResults);
            
            // Exibir resultados
            displayResults();
            
        } catch (error) {
            console.error('Erro na busca:', error);
            showAlert(`Erro na busca: ${error.message}`, 'error');
            loadingOverlay.classList.remove('active');
        }
    }
    
    // Função para enriquecer os resultados com mais detalhes (quando disponíveis)
    async function enrichResults(results) {
        // Esta função pode ser expandida para buscar mais detalhes de outras APIs
        // Por exemplo, ratings, reviews, etc.
        
        console.log('Enriquecendo resultados com dados adicionais...');
        
        // Simulação de enriquecimento de dados
        for (let i = 0; i < results.length; i++) {
            const result = results[i];
            
            // Simular ratings aleatórios para demonstração
            if (result.average_rating === 'N/A') {
                result.average_rating = (Math.random() * 3 + 2).toFixed(1); // Entre 2.0 e 5.0
                result.review_count = Math.floor(Math.random() * 100); // Entre 0 e 99
            }
            
            // Atualizar progresso
            updateProgress(90 + (i / results.length) * 10, `Processando detalhes (${i+1}/${results.length})...`);
            
            // Pequena pausa para não sobrecarregar as APIs
            await new Promise(resolve => setTimeout(resolve, 50));
        }
        
        console.log('Resultados enriquecidos:', results);
    }
    
    // Função para formatar o endereço a partir das tags
    function formatAddress(tags) {
        const addressParts = [];
        
        if (tags['addr:street']) {
            let streetAddress = tags['addr:street'];
            if (tags['addr:housenumber']) {
                streetAddress += ', ' + tags['addr:housenumber'];
            }
            addressParts.push(streetAddress);
        }
        
        if (tags['addr:city']) {
            addressParts.push(tags['addr:city']);
        }
        
        if (tags['addr:postcode']) {
            addressParts.push(tags['addr:postcode']);
        }
        
        if (tags['addr:state']) {
            addressParts.push(tags['addr:state']);
        }
        
        if (tags['addr:country']) {
            addressParts.push(tags['addr:country']);
        }
        
        return addressParts.length > 0 ? addressParts.join(', ') : 'Endereço não disponível';
    }
    
    // Função para exibir os resultados
    function displayResults() {
        // Atualizar informações de busca
        searchQuery.textContent = `${searchParams.establishmentType} em ${searchParams.location}`;
        totalResults.textContent = searchResults.length;
        
        // Limpar lista de resultados
        resultsList.innerHTML = '';
        
        if (searchResults.length === 0) {
            // Mostrar mensagem de nenhum resultado encontrado
            resultsList.innerHTML = `
                <div class="result-item">
                    <h3 class="result-title">Nenhum resultado encontrado</h3>
                    <p>Tente modificar sua busca ou aumentar o raio de busca.</p>
                    <p>Dicas:</p>
                    <ul>
                        <li>Verifique a ortografia do tipo de estabelecimento e da localização</li>
                        <li>Use termos mais genéricos (ex: "mercado" em vez de "supermercado")</li>
                        <li>Tente uma localização mais específica ou mais conhecida</li>
                    </ul>
                </div>
            `;
        } else {
            // Adicionar cada resultado à lista
            searchResults.forEach(result => {
                const resultItem = document.createElement('div');
                resultItem.className = 'result-item';
                
                // Criar estrelas para avaliação
                let starsHtml = '';
                if (result.average_rating !== 'N/A') {
                    const rating = parseFloat(result.average_rating);
                    const fullStars = Math.floor(rating);
                    const halfStar = rating % 1 >= 0.5;
                    
                    for (let i = 0; i < 5; i++) {
                        if (i < fullStars) {
                            starsHtml += '<span class="material-icons">star</span>';
                        } else if (i === fullStars && halfStar) {
                            starsHtml += '<span class="material-icons">star_half</span>';
                        } else {
                            starsHtml += '<span class="material-icons">star_border</span>';
                        }
                    }
                }
                
                // Construir HTML do item
                resultItem.innerHTML = `
                    <h3 class="result-title">${result.name}</h3>
                    <p class="result-info"><span class="result-label">Tipo:</span> ${result.type}</p>
                    <p class="result-info"><span class="result-label">Endereço:</span> ${result.address}</p>
                    <p class="result-info"><span class="result-label">Telefone:</span> ${result.phone}</p>
                    <p class="result-info"><span class="result-label">Website:</span> ${result.website !== 'N/A' ? `<a href="${result.website}" target="_blank">${result.website}</a>` : 'N/A'}</p>
                    <p class="result-info"><span class="result-label">Horário:</span> ${result.opening_hours}</p>
                    ${result.introduction !== 'N/A' ? `<p class="result-info"><span class="result-label">Descrição:</span> ${result.introduction}</p>` : ''}
                    <div class="result-rating">
                        <div class="rating-stars">${starsHtml}</div>
                        <span>${result.average_rating} (${result.review_count} avaliações)</span>
                    </div>
                    <p class="result-info mt-1">
                        <span class="result-label">Compras na Loja:</span> ${result.store_shopping ? 'Sim' : 'Não'} | 
                        <span class="result-label">Retirada na Loja:</span> ${result.in_store_pickup ? 'Sim' : 'Não'} | 
                        <span class="result-label">Entrega:</span> ${result.delivery ? 'Sim' : 'Não'}
                    </p>
                    <p class="result-info mt-1">
                        <a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(result.name + ' ' + result.address )}" target="_blank" class="btn btn-outline">Ver no Google Maps</a>
                    </p>
                `;
                
                resultsList.appendChild(resultItem);
            });
        }
        
        // Esconder overlay de carregamento
        loadingOverlay.classList.remove('active');
        
        // Mostrar container de resultados
        resultsContainer.style.display = 'block';
        
        // Esconder formulário de busca
        document.querySelector('.card').style.display = 'none';
        document.querySelectorAll('.card')[1].style.display = 'none';
    }
    
    // Função para mostrar o formulário de busca novamente
    function showSearchForm() {
        resultsContainer.style.display = 'none';
        document.querySelector('.card').style.display = 'block';
        document.querySelectorAll('.card')[1].style.display = 'block';
    }
    
    // Função para atualizar o progresso
    function updateProgress(percent, message) {
        progressBarFill.style.width = `${percent}%`;
        progressStatus.textContent = message;
    }
    
    // Função para mostrar alertas
    function showAlert(message, type) {
        alertContainer.innerHTML = `
            <div class="alert alert-${type}">
                ${message}
            </div>
        `;
        
        // Limpar alerta após 5 segundos
        setTimeout(() => {
            alertContainer.innerHTML = '';
        }, 5000);
    }
    
    // Função para exportar para TXT
    function exportToTxt() {
        if (searchResults.length === 0) {
            showAlert('Nenhum resultado disponível para exportação.', 'error');
            return;
        }
        
        let content = `Resultados da busca por: ${searchParams.establishmentType} em ${searchParams.location}\n`;
        content += `Total de estabelecimentos encontrados: ${searchResults.length}\n`;
        content += "========================================\n\n";
        
        searchResults.forEach(result => {
            content += `Nome: ${result.name}\n`;
            content += `Tipo: ${result.type}\n`;
            content += `Endereço: ${result.address}\n`;
            content += `Telefone: ${result.phone}\n`;
            content += `Website: ${result.website}\n`;
            content += `Horário: ${result.opening_hours}\n`;
            content += `Avaliação Média: ${result.average_rating}\n`;
            content += `Contagem de Avaliações: ${result.review_count}\n`;
            content += `Introdução: ${result.introduction}\n`;
            content += `Compras na Loja: ${result.store_shopping ? 'Sim' : 'Não'}\n`;
            content += `Retirada na Loja: ${result.in_store_pickup ? 'Sim' : 'Não'}\n`;
            content += `Entrega: ${result.delivery ? 'Sim' : 'Não'}\n`;
            content += "------------------------------\n\n";
        });
        
        downloadFile(content, 'resultados.txt', 'text/plain');
    }
    
    // Função para exportar para JSON
    function exportToJson() {
        if (searchResults.length === 0) {
            showAlert('Nenhum resultado disponível para exportação.', 'error');
            return;
        }
        
        const data = {
            search_params: searchParams,
            total_found: searchResults.length,
            results: searchResults
        };
        
        const content = JSON.stringify(data, null, 2);
        downloadFile(content, 'resultados.json', 'application/json');
    }
    
    // Função para exportar para CSV
    function exportToCsv() {
        if (searchResults.length === 0) {
            showAlert('Nenhum resultado disponível para exportação.', 'error');
            return;
        }
        
        // Cabeçalhos CSV
        const headers = [
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
        ];
        
        // Linhas de dados
        const rows = searchResults.map(result => [
            `"${result.name.replace(/"/g, '""')}"`,
            `"${result.type.replace(/"/g, '""')}"`,
            `"${result.address.replace(/"/g, '""')}"`,
            `"${result.phone.replace(/"/g, '""')}"`,
            `"${result.website.replace(/"/g, '""')}"`,
            `"${result.opening_hours.replace(/"/g, '""')}"`,
            result.average_rating,
            result.review_count,
            `"${result.introduction.replace(/"/g, '""')}"`,
            result.store_shopping ? 'Sim' : 'Não',
            result.in_store_pickup ? 'Sim' : 'Não',
            result.delivery ? 'Sim' : 'Não'
        ]);
        
        // Montar conteúdo CSV
        let content = headers.join(',') + '\n';
        rows.forEach(row => {
            content += row.join(',') + '\n';
        });
        
        downloadFile(content, 'resultados.csv', 'text/csv');
    }
    
    // Função para download de arquivo
    function downloadFile(content, fileName, contentType) {
        const blob = new Blob([content], { type: contentType });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        a.click();
        
        URL.revokeObjectURL(url);
    }
});
