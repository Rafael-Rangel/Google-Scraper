# Google Maps Scraper - Versão Simplificada

Esta é uma versão simplificada da aplicação Google Maps Scraper, com uma estrutura de diretórios mais simples para facilitar a execução local no Windows.

## Requisitos

- Python 3.8 ou superior
- Pip (gerenciador de pacotes do Python)
- Navegador Chromium ou Google Chrome instalado
- Acesso à internet

## Instalação e Execução Local

### 1. Preparar o Ambiente

Primeiro, certifique-se de ter o Python e o pip instalados. Em seguida, abra o Prompt de Comando (cmd) ou PowerShell como administrador e navegue até a pasta onde você extraiu este arquivo ZIP.

```bash
# Navegar até a pasta do projeto (substitua pelo caminho correto)
cd caminho\para\google_maps_scraper_simplified
```

### 2. Instalar Dependências

```bash
# Instalar as dependências necessárias
pip install -r requirements.txt
```

### 3. Instalar Navegadores do Playwright

```bash
# Instalar os navegadores necessários para o Playwright
playwright install
```

### 4. Executar a Aplicação

```bash
# Iniciar a aplicação web
python app.py
```

### 5. Acessar a Interface Web

Abra seu navegador e acesse:
```
http://localhost:5000
```

## Como Usar

1. Na página inicial, preencha os campos:
   - **Tipo de Estabelecimento**: Ex: farmácias, restaurantes, hotéis
   - **Localização**: Ex: Campo Grande, São Paulo, Rio de Janeiro
   - **Quantidade Máxima de Resultados**: Número de estabelecimentos a coletar

2. Clique em "Iniciar Busca" e aguarde a coleta de dados.

3. Na página de resultados, você poderá:
   - Ver o progresso da coleta em tempo real
   - Expandir cada card para ver detalhes completos
   - Baixar os resultados em formato TXT, JSON ou Excel

## Solução de Problemas

### Erro ao iniciar o navegador

Se você encontrar erros relacionados ao navegador, verifique:
- Se o Chrome ou Chromium está instalado
- Se o Playwright foi instalado corretamente com `playwright install`
- Se você tem permissões para executar o navegador

### Erro de conexão com o Google Maps

- Verifique sua conexão com a internet
- O Google pode ter limitado temporariamente seu acesso devido a muitas requisições

### Erro ao exportar para Excel

- Certifique-se de que o pandas e openpyxl estão instalados corretamente

## Notas Importantes

Esta ferramenta é apenas para fins educacionais. O uso de web scraping pode violar os Termos de Serviço do Google. Use por sua conta e risco.
