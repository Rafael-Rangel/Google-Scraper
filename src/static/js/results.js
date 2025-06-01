// Variáveis globais para armazenar os resultados da busca
let searchResults = [];
let searchParams = {};

// Função executada quando o documento estiver carregado
document.addEventListener('DOMContentLoaded', function() {
    // Elementos DOM
    const loadingOverlay = document.getElementById('loadingOverlay');
    const progressBarFill = document.getElementById('progressBarFill');
    const progressStatus = document.getElementById('progressStatus');
    const searchQuery = document.getElementById('searchQuery');
    const totalResults = document.getElementById('totalResults');
    const resultsList = document.getElementById('resultsList');
    const alertContainer = document.getElementById('alertContainer');
    
    // Iniciar verificação de status
    checkStatus();
    
    // Função para verificar o status da busca
    function checkStatus() {
        fetch('/api/status')
            .then(response => response.json())
            .then(data => {
                // Atualizar barra de progresso
                progressBarFill.style.width = `${data.progress}%`;
                progressStatus.textContent = data.message;
                
                // Verificar se há erro
                if (data.error) {
                    showAlert(data.error, 'error');
                    loadingOverlay.classList.remove('active');
                    return;
                }
                
                // Verificar se a busca está em andamento
                if (data.is_running) {
                    // Verificar novamente após 1 segundo
                    setTimeout(checkStatus, 1000);
                } else {
                    // Se a busca foi concluída, carregar os resultados
                    if (data.progress === 100) {
                        loadResults();
                    } else if (data.progress === 0) {
                        // Se a busca não foi iniciada ou houve erro
                        loadingOverlay.classList.remove('active');
                    }
                }
            })
            .catch(error => {
                console.error('Erro ao verificar status:', error);
                showAlert('Erro ao verificar status da busca.', 'error');
                loadingOverlay.classList.remove('active');
            });
    }
    
    // Função para carregar os resultados
    function loadResults() {
        fetch('/api/results')
            .then(response => response.json())
            .then(data => {
                // Armazenar resultados e parâmetros
                searchResults = data.results;
                searchParams = data.search_params;
                
                // Atualizar informações de busca
                searchQuery.textContent = `${searchParams.establishment_type} em ${searchParams.location}`;
                totalResults.textContent = data.total_found;
                
                // Exibir resultados
                displayResults();
                
                // Esconder overlay de carregamento
                loadingOverlay.classList.remove('active');
            })
            .catch(error => {
                console.error('Erro ao carregar resultados:', error);
                showAlert('Erro ao carregar resultados da busca.', 'error');
                loadingOverlay.classList.remove('active');
            });
    }
    
    // Função para exibir os resultados
    function displayResults() {
        // Limpar lista de resultados
        resultsList.innerHTML = '';
        
        if (searchResults.length === 0) {
            // Mostrar mensagem de nenhum resultado encontrado
            resultsList.innerHTML = `
                <div class="result-item">
                    <h3 class="result-title">Nenhum resultado encontrado</h3>
                    <p>Tente modificar sua busca ou usar termos mais genéricos.</p>
                </div>
            `;
            return;
        }
        
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
                    <a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(result.name + ' ' + result.address)}" target="_blank" class="btn btn-outline">Ver no Google Maps</a>
                </p>
            `;
            
            resultsList.appendChild(resultItem);
        });
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
});
