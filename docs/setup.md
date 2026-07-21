# Setup — youtube-pub-mcp

## 1. Pré-requisitos
- Python 3.11+
- `uv` instalado
- Conta Google com acesso ao YouTube
- Projeto no Google Cloud com YouTube Data API v3 ativado
- Credenciais OAuth 2.0 do tipo *Desktop app* (JSON salvo fora deste repositório)

> Este NÃO é um guia completo do Google Cloud.  
> Se precisar, consulte a documentação oficial do YouTube Data API.

---

## 2. Instalar dependências
```bash
uv sync
```

---

## 3. Variáveis de ambiente
Crie um `.env` na raiz (não versionado pelo `.gitignore`).

Exemplo mínimo:
- Variáveis específicas aqui

---

## 4. Autorizar o primeiro canal
1. Abra o Google Cloud Console.
2. Certifique-se de que o cliente OAuth criado é do tipo **Desktop app**.
3. Baixe o JSON das credenciais e guarde como `credentials.json` em `~/.config/youtube-pub-mcp/` — **não** coloque no repositório.
4. Execute:
```bash
uv run <comando de autorização aqui>
```
5. O fluxo abre no navegador e, ao concluir, gera um `token.json` em `~/.config/youtube-pub-mcp/`, que também **não deve ser commitado**.

---

## 5. Rodar o projeto
```bash
uv run <comando de execução aqui>
```

## 6. Dicas
- Se quiser usar outra conta/channel, basta reautorizar.
- Tokens expiram/param; reexecute o passo de autorização quando pedido.
