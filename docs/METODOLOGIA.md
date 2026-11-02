# Método, evidências e limites

## O problema estudado

O case avalia um agente de atendimento de uma escola de idiomas: responder informações de cursos, orientar a escolha, respeitar limites e tratar falhas. O exercício transforma impressões de uma conversa isolada em cenários e evidências comparáveis.

As simulações são por texto. Elas não medem qualidade de áudio, interrupções, latência de voz, carga ou atendimento simultâneo.

## Ciclo de avaliação

1. Escrever um roteiro do cliente simulado, critérios observáveis e limite de turnos.
2. Fixar os retornos da ferramenta para controlar os dados disponíveis.
3. Executar a seleção na branch configurada e registrar a versão retornada pela plataforma.
4. Receber o julgamento dos critérios da ElevenLabs e conferir evidências da ferramenta em Python.
5. Revisar conversas e justificativas, inclusive amostras aprovadas.
6. Alterar uma hipótese no agente e repetir os mesmos casos, buscando melhorias e regressões.

O método aplica conceitos do [workflow de avaliação da Claude Academy](https://academy.claude.com/courses/building-with-the-claude-api/a-typical-eval-workflow) aos recursos de [Agent Testing da ElevenLabs](https://elevenlabs.io/docs/eleven-agents/customization/agent-testing). As execuções utilizam o SDK da ElevenLabs. O Codex apoiou o desenvolvimento e a investigação dos resultados.

## Dataset e respostas controladas

A suíte tem 20 cenários. Os casos 01–16 foram usados para desenvolvimento e 17–20 reservados para uma validação didática. Todos foram preparados no mesmo exercício e seus conteúdos são conhecidos; eles não constituem um benchmark independente.

Os critérios aceitam paráfrases e procuram resultados corretos, sem impor uma frase exata. Um caminho por um nó específico não define sucesso quando a necessidade do usuário foi atendida. Perguntas institucionais podem dispensar a consulta ao catálogo.

| Perfil do mock | Retorno | Comportamento esperado |
|---|---|---|
| Catálogo normal | Três cursos com dados fixos | Informar ou orientar sem contradizer os dados |
| Catálogo vazio | Sucesso com lista vazia | Reconhecer a ausência de cursos ativos na consulta |
| Erro da aplicação | JSON de erro, com `is_error=false` | Reconhecer que os dados não foram confirmados |
| Erro da ferramenta | Retorno com `is_error=true` | Tratar a falha sem inventar informações |

Uma falha esperada da ferramenta pode resultar em um atendimento aprovado se o agente a tratar corretamente. O mock substitui o retorno de `consultar_cursos`, não verifica a disponibilidade real de uma planilha ou API. Ferramentas de sistema e workflow continuam funcionando; outras integrações precisam de revisão própria.

## Assinatura, versão e repetição

A assinatura é um hash da definição preparada do teste, incluindo roteiro, critérios e mock. Ela permite reutilizar um cadastro quando a definição permanece igual e reconhecer mudanças nessa definição. Não representa o estado completo do agente.

O runner registra a versão efetivamente retornada e o uso de rascunho quando a plataforma fornece essa informação. Para comparar mudanças do agente, mantenha critérios e mocks iguais e confira a versão avaliada.

`--rotulo` identifica o lote localmente. Repetir `--executar` cria uma nova rodada e pode consumir créditos. Um envio com resposta perdida deve ser investigado e consultado antes de uma nova tentativa.

## Como interpretar os resultados

A ElevenLabs julga os critérios em linguagem natural. O Python confere a chamada e o retorno da ferramenta conforme a expectativa do cenário. O resumo distingue:

| Resultado | Significado |
|---|---|
| `APROVADO` | Avaliação aprovada e evidências exigidas confirmadas |
| `REPROVADO` | A avaliação informou falha nos critérios |
| `REVISAR_EVIDENCIA` | Avaliação positiva com evidência exigida não comprovada |
| `INCONCLUSIVO` | Resultado pendente, desconhecido ou erro técnico |
| `CANCELADO` | Execução cancelada |

Essas classificações são automáticas. A conversa e a justificativa devem ser lidas antes de concluir que o atendimento falhou ou que o agente está adequado para produção.

## Métricas do dashboard

| Indicador | Cálculo ou origem | Como ler |
|---|---|---|
| Aprovação automática | Aprovados ÷ (aprovados + reprovados) | Inconclusivos, cancelados e evidências pendentes ficam fora do denominador |
| Cobertura decisiva | (Aprovados + reprovados) ÷ casos planejados | Indica quanto do lote teve conclusão decisiva |
| Créditos informados | Consumo registrado nos resultados | Não corresponde a saldo, preço em dinheiro ou teto de consumo |
| Chamadas de transição | Eventos de ferramentas de transição executadas | Um volume alto merece investigação, mas não reprova automaticamente |
| Definição idêntica | Mesma assinatura do teste | Não garante que agente, modelo e condições foram iguais |

Valores ausentes permanecem ausentes, sem virar zero. Os modelos do agente são lidos nas mensagens correspondentes, sem atribuir a ele modelos utilizados apenas pelo simulador ou avaliador. A contagem de ferramentas considera os eventos executados e não soma novamente ferramentas aninhadas nos retornos do workflow.

## Amostra incluída neste repositório

O estudo completo reuniu seis lotes e 51 execuções. O repositório público inclui dois lotes sanitizados, com 22 execuções e 9.451 créditos informados:

| Lote | Casos incluídos | Resultado automático | Créditos |
|---|---|---|---:|
| `triagem-v2-override` | 07 e 13 | 07 reprovado; 13 aprovado | 776 |
| `baseline-completa`, rodada de 29/10/2026 às 21:06 | 01 a 20 | 20 aprovados | 8.675 |

As rodadas têm coberturas diferentes. Somar seus resultados não produz uma taxa comparável de evolução do agente. A demonstração online mantém os seis lotes do estudo; o painel local deste repositório abre o recorte de dois.

Na rodada completa, a revisão humana encontrou:

- **Caso 07:** repetição de pergunta antes da resposta do usuário, apesar de um critério de espera. É um falso positivo naquele critério.
- **Caso 14:** resposta final adequada com 135 oscilações entre dois nós. Foram 137 chamadas de transição, incluindo entrada e encerramento, e 3.384 créditos — cerca de 39% do total da rodada.

Essas observações não foram convertidas em novas notas nos relatórios. O dashboard conserva as conclusões automáticas e informa que não há pareceres humanos estruturados nos arquivos. Conteúdo final, trajetória e custo precisam ser interpretados em conjunto.

## O que é reproduzível

O painel pode ser aberto sem conta ou chave da ElevenLabs. Os arquivos publicados são uma projeção revisada: IDs substituídos, metadados desnecessários omitidos e conclusões preservadas. Os aliases não permitem retomar execuções na conta original.

O runner pode ser usado com agente, credenciais e configurações próprios, seguindo o [guia de adaptação](COMO-ADAPTAR.md). A configuração completa do agente do estudo, a base institucional e a integração original não estão incluídas como infraestrutura reproduzível.

Os critérios foram refinados durante o estudo. Considere a assinatura e o snapshot das entradas ao comparar rodadas. Repetições posteriores ajudam a investigar variabilidade; uma aprovação isolada não garante estabilidade nem desempenho em produção.
