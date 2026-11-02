# Um passeio pelo repositório

Este guia é para quem quer explorar os arquivos antes de executar qualquer programa.

## 1. Comece pelo README

Volte à [página principal](../README.md) do projeto. O GitHub mostra a lista de arquivos e, abaixo, o README: apresentação, links, instruções e limites do case.

Observe a indicação **Public** e a branch **main**. `main` é a versão principal dos arquivos deste projeto. As branches do agente na ElevenLabs pertencem a outro controle de versões.

## 2. Leia o que foi testado

Abra [CENARIOS-20.md](../CENARIOS-20.md) para conhecer os roteiros e critérios em formato de documento. Depois veja [cenarios/suite-20.json](../cenarios/suite-20.json), que guarda as definições utilizadas pelo programa.

O arquivo `.md` é texto formatado. O `.json` guarda dados estruturados. Ambos ajudam a entender o mesmo conjunto de casos, mas o runner lê o JSON. A [suíte mínima](../cenarios/suite-minima.json) reúne os exemplos 01, 11 e 17 para começar a adaptação; também é possível criar outras suítes.

## 3. Confira os dados fornecidos à ferramenta

Em [fixtures/](../fixtures/), abra o catálogo normal e os exemplos de erro e lista vazia. Esses arquivos controlam a resposta da ferramenta nas simulações.

Isso permite perguntar, por exemplo: “Se a consulta devolver erro, o agente reconhece a falha ou inventa um preço?” O teste observa o tratamento da situação, sem depender da disponibilidade atual de uma API externa.

## 4. Explore uma rodada

Em [lotes/](../lotes/), há dois exemplos históricos revisados. Dentro de cada um:

| Arquivo | O que mostra |
|---|---|
| `manifesto.json` | Data, rótulo e contexto da rodada |
| `entradas.json` | Cenários e critérios utilizados naquela execução |
| `resumo.json` | Indicadores e resultados por cenário |
| `resumo.csv` | Resultados em formato de tabela |
| `casos/` | Transcrições, resumos e JSONs sanitizados de cada caso |

O nome `resultado-completo.json` foi mantido para compatibilidade com o leitor, mas os arquivos desta amostra são projeções sanitizadas. Os retornos brutos originais da conta não foram publicados.

Para uma leitura visual, abra a [demonstração online](https://ponte-idiomas-evals.streamlit.app/). Ela contém seis lotes do estudo; a cópia local deste repositório contém dois.

## 5. Conheça os programas

| Arquivo | Responsabilidade |
|---|---|
| `avaliar_lote.py` | Organizar os casos e solicitar as simulações |
| `relatorios_lote.py` | Consolidar resultados e conferir evidências |
| `avaliar.py` | Exemplo inicial de um cenário |
| `verificar_acesso.py` | Conferir autenticação e acesso ao agente |
| `dashboard_dados.py` | Ler e organizar os relatórios |
| `dashboard.py` | Exibir cartões, gráficos, filtros e conversas |

Leia o [guia de adaptação](COMO-ADAPTAR.md) antes de executar avaliações próprias. Abrir arquivos no GitHub ou navegar no dashboard não inicia simulações.

## 6. Entenda as verificações e o histórico

A pasta [tests/](../tests/) verifica o próprio código: montagem de dados, associação de resultados, tratamento de erros e sanitização. Ela usa dados e HTTP simulados.

Na aba **Actions** do GitHub ficam as verificações automáticas. O arquivo [`.github/workflows/testes.yml`](../.github/workflows/testes.yml) instala as bibliotecas e executa os testes do programa quando enviamos alterações ou abrimos uma proposta de mudança. Isso não solicita as 20 conversas na ElevenLabs.

Um **commit** registra uma alteração no histórico dos arquivos. Um **push** envia os commits locais ao GitHub. Um **pull request** é uma proposta de mudança para revisão antes de integrá-la à branch principal.

O GitHub não recebe automaticamente arquivos salvos no seu computador. Novos relatórios também precisam de revisão antes de qualquer envio.

## 7. Baixe uma cópia ou contribua

Na página principal do repositório, o botão **Code** oferece a opção **Download ZIP**. Extraia a pasta e siga o README. Quem usa Git pode clonar o repositório para manter uma cópia com histórico.

Para sugerir uma melhoria, use a aba **Issues** e descreva o cenário, o comportamento observado e o resultado esperado. Inclua exemplos revisados, sem chaves, dados pessoais ou metadados de conta. Se quiser propor código, crie um fork e abra um pull request.

O arquivo [LICENSE](../LICENSE) apresenta as condições de reutilização do código. Os cenários da escola são exemplos: adapte-os ao seu negócio e revise os resultados com critérios próprios.
