# Avaliar seu próprio agente

Este guia parte de um agente já configurado na ElevenLabs. Ele explica como reaproveitar o runner do projeto e quais partes precisam ser adaptadas.

O exemplo incluído foi construído para uma escola de idiomas e uma ferramenta de catálogo. O repositório não cria automaticamente o agente, seus prompts ou sua base de conhecimento.

## 1. Prepare o ambiente local

Use Python 3.12 e abra o terminal na pasta do projeto. No Windows:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-evals.txt
Copy-Item .env.example .env
```

No Linux ou macOS:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-evals.txt
cp .env.example .env
```

Para abrir também o dashboard e executar todos os testes do programa, instale `requirements.txt` no mesmo ambiente. Se já criou o ambiente ao explorar o painel, aproveite-o e instale apenas as dependências adicionais.

## 2. Configure a própria conta e o agente

Preencha o `.env` local:

| Variável | Valor esperado |
|---|---|
| `ELEVENLABS_API_KEY` | Sua chave de API, com acesso aos testes e ao agente escolhido |
| `ELEVENLABS_AGENT_ID` | ID do seu agente |
| `ELEVENLABS_BRANCH_ID` | ID da branch do agente que deseja avaliar |
| `ELEVENLABS_TOOL_ID` | ID da ferramenta cujo retorno será controlado no teste |

Use os identificadores da sua própria configuração. Os aliases `demo_...` dos relatórios publicados não servem para consultar ou executar o agente original.

O arquivo `.env` fica somente no ambiente local e já está coberto pelo `.gitignore`. Não coloque a chave em cenários, arquivos de código ou no dashboard hospedado. Abrir a amostra do painel não exige esse arquivo.

Se quiser conferir autenticação antes das simulações:

```powershell
.\.venv\Scripts\python.exe verificar_acesso.py
```

Essa consulta verifica acesso ao agente, sem iniciar avaliações. A branch da ElevenLabs é independente da branch `main` do repositório GitHub.

## 3. Confira o contrato da ferramenta

No case, a ferramenta chama-se `consultar_cursos` e devolve dados como os de `fixtures/catalogo.json`. O mock é associado pelo **ID da ferramenta**, enquanto a verificação das evidências procura o nome configurado em cada cenário.

A implementação aceita um objeto JSON como retorno controlado, inclusive para ferramentas de outros negócios. No catálogo deste exemplo:

- `status` indica `ok` ou `erro`.
- Quando `status=ok` e existe o campo `cursos`, o runner confere se `total` corresponde à quantidade de cursos.
- Cada cenário fornece um retorno para a ferramenta selecionada.

Os campos dos cursos — preço, nível, modalidade e horário — são específicos deste exemplo. Para avaliar um agente de outro negócio, adapte os arquivos de dados, os critérios e as expectativas de chamada. Acrescente validações em `montar_teste`, no `avaliar_lote.py`, se quiser conferir o contrato específico da sua ferramenta. Confira também a verificação de evidências em `relatorios_lote.py`.

Se seu agente usa uma ferramenta equivalente, mantenha seu nome real no campo `ferramenta` dos cenários e informe o ID correto no `.env`. Para trabalhar com várias ferramentas ou respostas condicionadas por parâmetros, será necessário ampliar o mapeamento de mocks do runner.

O mock selecionado controla o retorno da ferramenta durante a simulação. Isso não mede a disponibilidade real da API de produção. Revise as demais integrações do agente: o exemplo não representa isolamento automático de todas as ferramentas externas.

## 4. Adapte os cenários e critérios

Comece por `cenarios/suite-minima.json`, com os exemplos 01, 11 e 17. Para conhecer o conjunto maior, leia `CENARIOS-20.md` e `cenarios/suite-20.json`.

| Campo do cenário | O que definir |
|---|---|
| `id` e `nome` | Identificação única do cenário |
| `cenario` | Objetivo e comportamento do cliente simulado |
| `criterios_sucesso` | Resultados observáveis que serão julgados |
| `max_turnos` | Limite de turnos da simulação |
| `ferramenta` | Nome da ferramenta a verificar nas evidências |
| `expectativa_ferramenta` | Uso obrigatório ou opcional |
| `mock.arquivo` | Arquivo de resposta controlada dentro de `fixtures/` |
| `mock.is_error` | Se o retorno deve ser marcado como erro da ferramenta |

Você pode criar uma suíte com a quantidade de casos necessária e salvá-la em `cenarios/`. Use `--suite cenarios/SEU-ARQUIVO.json` para selecioná-la; sem essa opção, o runner usa `cenarios/suite-20.json`. IDs e nomes devem ser únicos. Para executar apenas parte de uma suíte, acrescente `--casos "01,11"`.

Os IDs seguem o formato `01-nome-do-cenario`, com prefixo numérico de 01 a 99. O limite de turnos aceito é de 1 a 50. Prefira critérios verificáveis, como informar um valor correto, reconhecer a ausência de dados ou pedir esclarecimento antes de recomendar.

Os cenários de informações institucionais pressupõem que seu agente possua políticas compatíveis na base de conhecimento ou nos prompts. Você deve fornecer essas regras no próprio agente ou reescrever os casos; a integração original e o PDF do estudo não estão incluídos.

O exemplo individual `avaliar.py` lê `cenarios/01-duvida-ingles.json`. Se for utilizá-lo após adaptar a suíte, mantenha essa definição e o catálogo coerentes com o caso 01.

## 5. Faça uma prévia sem chamadas à API

```powershell
.\.venv\Scripts\python.exe avaliar_lote.py --preview --suite cenarios/suite-minima.json
```

A prévia mostra a seleção e grava `plano-lote.json` no computador. Não inicia simulações nem instancia o cliente da ElevenLabs. Ela funciona sem chave; confira os dados antes de preencher credenciais e executar.

Para filtrar uma suíte, use `--casos "01,11"`. No PowerShell, mantenha a lista entre aspas. Números com ou sem zero inicial são aceitos: `1` e `01` selecionam o mesmo caso.

## 6. Execute uma seleção pequena e revise

O comando abaixo solicita uma nova rodada na sua conta e **pode consumir créditos da ElevenLabs**:

```powershell
.\.venv\Scripts\python.exe avaliar_lote.py --executar --suite cenarios/suite-minima.json --rotulo minha-calibracao
```

Use somente os casos que já adaptou. O runner registra ou reutiliza definições de testes e solicita uma execução por caso selecionado. Ele não altera prompt, workflow ou publicação do agente.

Depois da execução, confira:

1. Se as falas atendem aos critérios e usam os dados esperados.
2. Se o avaliador explicou a aprovação ou reprovação de forma coerente.
3. Se a chamada e o retorno da ferramenta exigida ficaram comprovados.
4. Se a versão avaliada, os turnos e o consumo estão adequados à comparação.

Leia também alguns casos aprovados. O estudo contém um exemplo de falso positivo que só apareceu na revisão humana.

## 7. Consulte uma execução pendente antes de repetir

```powershell
.\.venv\Scripts\python.exe avaliar_lote.py --consultar
```

Esse modo recupera o último lote salvo, sem iniciar outro. Não combine `--consultar` com `--suite`: a consulta usa a cópia das entradas salva no lote. Se o envio tiver resultado incerto, confira a execução na plataforma e recupere o mesmo ID. Não apague os arquivos de estado para ignorar uma pendência: repetir `--executar` cria outra rodada e pode gerar novo consumo.

`--rotulo` identifica o lote localmente. A assinatura identifica a definição preparada do teste; a versão retornada pela plataforma identifica o agente efetivamente avaliado.

## 8. Explore os resultados e compare alterações

Cada rodada cria um diretório em `lotes/`, contendo manifesto, entradas, resumos JSON/CSV e os detalhes dos casos. Com as dependências do painel instaladas:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

Para comparar o agente antes e depois de um ajuste, mantenha os cenários e mocks iguais, registre a alteração e execute outra rodada com um novo rótulo. Confira tanto melhorias quanto regressões. Se alterar o teste, trate-o como outra definição.

No Linux ou macOS, substitua `.\.venv\Scripts\python.exe` por `.venv/bin/python` nos comandos.

## Compartilhar resultados com cuidado

Novos lotes locais são ignorados pelo Git, pois podem conter metadados da conta e dados das conversas. O dashboard hospedado não recebe automaticamente os arquivos do seu computador.

Para preparar uma amostra compartilhável:

```powershell
.\.venv\Scripts\python.exe scripts/exportar_demo.py --origem CAMINHO_DO_PROJETO_LOCAL --destino NOVA_PASTA_DE_EXPORTACAO
```

Origem e destino devem ser pastas separadas, e o destino não pode conter uma pasta `lotes/` existente. O exportador projeta campos conhecidos, substitui IDs e remove padrões conhecidos de e-mail, URL, caminho e credencial. Revise o resultado antes de publicar: nomes, telefones ou segredos com outros formatos podem exigir remoção adicional.

O código e os testes podem ser conferidos sem chamadas reais à API:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Instale os dois arquivos de dependências para executar toda essa verificação.
