// Google Maps Scraper - JavaScript para página de resultados

document.addEventListener('DOMContentLoaded', function() {
    const resultsList = document.getElementById('resultsList');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const progressContainer = document.getElementById('progressContainer');
    const progressBarFill = document.getElementById('progressBarFill');
    const progressStatus = document.getElementById('progressStatus');
    
    // Função para mostrar alerta
    function showAlert(message, type) {
        const alertContainer = document.getElementById('alertContainer');
        const alertElement = document.createElement('div');
        alertElement.className = `alert alert-${type}`;
        alertElement.textContent = message;
        alertContainer.appendChild(alertElement);
        
        // Auto-remover após 5 segundos
        setTimeout(() => {
            alertElement.remove();
        }, 5000);
    }
    
    // Template para um item de resultado
    function createResultItem(result, index) {
        return `
            <li class="result-card">
                <div class="result-header" onclick="toggleResultBody(${index})">
                    <h3>${result.name || 'Nome não disponível'}</h3>
                    <span class="material-icons">expand_more</span>
                </div>
                <div class="result-body" id="result-body-${index}">
                    <div class="result-info">
                        <p><strong>Tipo:</strong> ${result.type || 'N/A'}</p>
                        <p><strong>Endereço:</strong> ${result.address || 'N/A'}</p>
                        <p><strong>Telefone:</strong> ${result.phone || 'N/A'}</p>
                        <p><strong>Website:</strong> ${result.website ? `<a href="${result.website}" target="_blank">${result.website}</a>` : 'N/A'}</p>
                        <p><strong>Horário:</strong> ${result.opening_hours || 'N/A'}</p>
                        <p><strong>Avaliação:</strong> ${result.average_rating || 'N/A'} (${result.review_count || '0'} avaliações)</p>
                        <p><strong>Introdução:</strong> ${result.introduction || 'N/A'}</p>
                        <p><strong>Compras na Loja:</strong> ${result.store_shopping ? 'Sim' : 'Não'}</p>
                        <p><strong>Retirada na Loja:</strong> ${result.in_store_pickup ? 'Sim' : 'Não'}</p>
                        <p><strong>Entrega:</strong> ${result.delivery ? 'Sim' : 'Não'}</p>
                    </div>
                </div>
            </li>
        `;
    }
    
    // Função para alternar a visibilidade do corpo do resultado
    window.toggleResultBody = function(index) {
        const resultBody = document.getElementById(`result-body-${index}`);
        resultBody.classList.toggle('active');
    };
    
    // Função para verificar o status da coleta
    function checkStatus() {
        fetch('/api/status')
            .then(response => response.json())
            .then(data => {
                // Atualizar barra de progresso
                if (data.is_running) {
                    progressContainer.style.display = 'block';
                    progressBarFill.style.width = `${data.progress}%`;
                    progressStatus.textContent = data.message;
                    
                    // Continuar verificando o status
                    setTimeout(checkStatus, 1000);
                } else {
                    // Coleta concluída ou com erro
                    if (data.error) {
                        showAlert(`Erro na coleta: ${data.error}`, 'error');
                        loadingOverlay.classList.remove('active');
                        progressContainer.style.display = 'none';
                    } else if (data.progress === 100) {
                        // Coleta concluída com sucesso, carregar resultados
                        loadResults();
                    }
                }
            })
            .catch(error => {
                console.error('Erro ao verificar status:', error);
                showAlert('Erro ao verificar status da coleta.', 'error');
                loadingOverlay.classList.remove('active');
            });
    }
    
    // Função para carregar os resultados
    function loadResults() {
        fetch('/api/results')
            .then(response => response.json())
            .then(data => {
                // Atualizar informações de busca
                document.getElementById('searchQuery').textContent = 
                    `${data.search_params.establishment_type} em ${data.search_params.location}`;
                document.getElementById('totalResults').textContent = data.total_found;
                
                // Limpar lista de resultados
                resultsList.innerHTML = '';
                
                // Adicionar resultados à lista
                if (data.results && data.results.length > 0) {
                    data.results.forEach((result, index) => {
                        resultsList.innerHTML += createResultItem(result, index);
                    });
                    showAlert(`${data.results.length} resultados encontrados.`, 'success');
                } else {
                    showAlert('Nenhum resultado encontrado para esta busca.', 'error');
                }
                
                // Esconder overlay de carregamento e barra de progresso
                loadingOverlay.classList.remove('active');
                progressContainer.style.display = 'none';
            })
            .catch(error => {
                console.error('Erro ao carregar resultados:', error);
                showAlert('Erro ao carregar resultados.', 'error');
                loadingOverlay.classList.remove('active');
                progressContainer.style.display = 'none';
            });
    }
    
    // Iniciar verificação de status
    checkStatus();
});
