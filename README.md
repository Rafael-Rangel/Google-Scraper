# Google Maps Scraper

Uma ferramenta para coletar dados de estabelecimentos do Google Maps de forma automatizada.

## Sobre o Projeto

Este projeto permite buscar estabelecimentos no Google Maps com base em um tipo (ex: farmácias, restaurantes) e uma localização (ex: São Paulo, Rio de Janeiro), coletando informações detalhadas como:

- Nome e tipo do estabelecimento
- Endereço e telefone
- Website e horário de funcionamento
- Avaliações e número de reviews
- Informações adicionais (compras na loja, retirada, entrega)

Os resultados podem ser exportados em diferentes formatos (TXT, JSON, CSV).

## Requisitos

- Python 3.8+
- Playwright
- Flask

## Instalação

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/google-maps-scraper.git
cd google-maps-scraper
```

2. Crie e ative um ambiente virtual:
```bash
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Instale os navegadores necessários para o Playwright:
```bash
playwright install chromium
```

## Como Usar

1. Inicie a aplicação:
```bash
python -m src.main
```

2. Acesse a interface web em `http://localhost:5000`

3. Preencha o formulário com:
   - Tipo de estabelecimento (ex: farmácias)
   - Localização (ex: São Paulo)
   - Quantidade máxima de resultados

4. Clique em "Iniciar Busca" e aguarde a coleta de dados

5. Visualize os resultados e exporte nos formatos disponíveis

## Deploy Online Gratuito

### Opção 1: Railway

1. Crie uma conta no [Railway](https://railway.app/)
2. Conecte seu repositório GitHub ou faça upload do código
3. Configure as variáveis de ambiente necessárias
4. Deploy automático

### Opção 2: Render

1. Crie uma conta no [Render](https://render.com/)
2. Crie um novo Web Service
3. Conecte seu repositório ou faça upload do código
4. Configure como "Docker" e use o Dockerfile incluído
5. Deploy automático

## Estrutura do Projeto

```
google-maps-scraper/
├── src/
│   ├── main.py           # Arquivo principal da aplicação Flask
│   ├── static/           # Arquivos estáticos (CSS, JS)
│   └── templates/        # Templates HTML
├── Dockerfile            # Configuração para deploy em containers
├── requirements.txt      # Dependências Python
└── README.md             # Este arquivo
```

## Notas Importantes

- Esta ferramenta é apenas para fins educacionais
- O uso de web scraping pode violar os Termos de Serviço do Google
- Recomenda-se limitar o número de buscas para evitar bloqueios
- Em ambientes de produção, considere adicionar proxies e rotação de IPs

## Limitações Conhecidas

- O Google Maps pode bloquear requisições automatizadas após uso intenso
- Algumas informações podem não estar disponíveis para todos os estabelecimentos
- O deploy em ambientes gratuitos pode ter limitações de recursos e tempo de execução

## Licença

Este projeto é distribuído sob a licença MIT. Veja o arquivo LICENSE para mais detalhes.
