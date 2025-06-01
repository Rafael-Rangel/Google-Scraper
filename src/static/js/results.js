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
        searchResults.forEach((result, index) => {
            const resultItem = document.createElement('div');
            resultItem.className = 'result-item';
            
            // Função para verificar se um valor é válido (não é N/A, null, undefined ou vazio)
            function isValidValue(value) {
                return value && value !== 'N/A' && value.trim() !== '';
            }
            
            // Construir HTML do item com apenas os campos que existem
            let resultHTML = `
                <div class="result-header">
                    <h3 class="result-title">${result.name || 'Nome não disponível'}</h3>
                    <span class="result-number">#${index + 1}</span>
                </div>
            `;
            
            // Adicionar tipo se disponível
            if (isValidValue(result.type)) {
                resultHTML += `<p class="result-info"><span class="result-label">Tipo:</span> ${result.type}</p>`;
            }
            
            // Adicionar endereço se disponível
            if (isValidValue(result.address)) {
                resultHTML += `<p class="result-info"><span class="result-label">Endereço:</span> ${result.address}</p>`;
            }
            
            // Adicionar telefone se disponível
            if (isValidValue(result.phone)) {
                resultHTML += `<p class="result-info"><span class="result-label">Telefone:</span> <a href="tel:${result.phone}">${result.phone}</a></p>`;
            }
            
            // Adicionar website se disponível
            if (isValidValue(result.website)) {
                const websiteUrl = result.website.startsWith('http') ? result.website : `https://${result.website}`;
                resultHTML += `<p class="result-info"><span class="result-label">Website:</span> <a href="${websiteUrl}" target="_blank" rel="noopener">${result.website}</a></p>`;
            }
            
            // Adicionar botões de ação
            resultHTML += `
                <div class="result-actions">
                    <a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent((result.name || '') + ' ' + (result.address || ''))}" 
                       target="_blank" 
                       rel="noopener"
                       class="btn btn-outline">
                        <span class="material-icons">map</span>
                        Ver no Google Maps
                    </a>
            `;
            
            // Adicionar botão de ligar se houver telefone
            if (isValidValue(result.phone)) {
                resultHTML += `
                    <a href="tel:${result.phone}" class="btn btn-outline">
                        <span class="material-icons">phone</span>
                        Ligar
                    </a>
                `;
            }
            
            // Adicionar botão do WhatsApp se houver telefone
            if (isValidValue(result.phone)) {
                const cleanPhone = result.phone.replace(/\D/g, ''); // Remove caracteres não numéricos
                if (cleanPhone.length >= 10) {
                    resultHTML += `
                        <a href="https://wa.me/55${cleanPhone}" 
                           target="_blank" 
                           rel="noopener"
                           class="btn btn-outline">
                            <span class="material-icons">chat</span>
                            WhatsApp
                        </a>
                    `;
                }
            }
            
            resultHTML += '</div>'; // Fechar result-actions
            
            resultItem.innerHTML = resultHTML;
            resultsList.appendChild(resultItem);
        });
    }
    
    // Função para mostrar alertas
    function showAlert(message, type) {
        alertContainer.innerHTML = `
            <div class="alert alert-${type}">
                <span class="material-icons">
                    ${type === 'error' ? 'error' : 'info'}
                </span>
                ${message}
            </div>
        `;
        
        // Limpar alerta após 5 segundos
        setTimeout(() => {
            alertContainer.innerHTML = '';
        }, 5000);
    }
    
    // Função para copiar informações para a área de transferência
    function copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            showAlert('Informações copiadas para a área de transferência!', 'success');
        }).catch(() => {
            showAlert('Erro ao copiar informações.', 'error');
        });
    }
    
    // Adicionar listener para botões de copiar (se você quiser adicionar essa funcionalidade)
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('copy-btn')) {
            const resultItem = e.target.closest('.result-item');
            const name = resultItem.querySelector('.result-title').textContent;
            const address = resultItem.querySelector('[data-field="address"]')?.textContent || '';
            const phone = resultItem.querySelector('[data-field="phone"]')?.textContent || '';
            
            const copyText = `${name}\n${address}\n${phone}`;
            copyToClipboard(copyText);
        }
    });
});
