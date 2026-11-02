# Ponte Idiomas — entradas dos 20 cenários

Este documento apresenta o dataset, versão 1.1, para revisão antes da execução. Não contém respostas nem notas de uma rodada já realizada. Para editar os testes, altere `cenarios/suite-20.json`, que é a fonte usada pelo programa.

Os roteiros instruem o cliente simulado; os critérios instruem o avaliador. O comportamento esperado aparece nos critérios, sem antecipar a resposta correta ao cliente simulado.

## Catálogo e políticas de referência

- Inglês iniciante: presencial, terças e quintas, 19h às 20h, R$ 220 mensais, 6 meses.
- Conversação em inglês: intermediário, online, quartas-feiras, 19h às 20h30, R$ 280 mensais, 3 meses.
- Espanhol iniciante: online, segundas e quartas, 18h às 19h, R$ 240 mensais, 6 meses.
- Secretaria: segunda a sexta, 9h às 18h. Matrícula e confirmação de vagas dependem da secretaria. Não presumir disponibilidade a partir do horário das aulas.
- Não há autorização para inventar descontos, taxas ou outras condições ausentes das fontes.

Os casos 01–16 apoiam o desenvolvimento. Os casos 17–20 são uma reserva didática de validação; por serem conhecidos por quem preparou a suíte, não representam validação independente.

## Visão geral

| Caso | Tema | Turnos máximos | Consulta ao catálogo | Retorno controlado |
|---|---|---:|---|---|
| 01 | Preço e horário do inglês iniciante | 5 | obrigatória | catálogo normal |
| 02 | Duração e aulas da conversação | 5 | obrigatória | catálogo normal |
| 03 | Preço, modalidade e dias do espanhol | 5 | obrigatória | catálogo normal |
| 04 | Comparação dos cursos online | 5 | obrigatória | catálogo normal |
| 05 | Recomendação de inglês iniciante | 7 | obrigatória | catálogo normal |
| 06 | Recomendação de conversação | 7 | obrigatória | catálogo normal |
| 07 | Esclarecimento de perfil incompleto | 8 | obrigatória | catálogo normal |
| 08 | Inglês do zero somente online | 7 | obrigatória | catálogo normal |
| 09 | Inglês em dias não disponíveis | 5 | obrigatória | catálogo normal |
| 10 | Pedido de francês fora do catálogo | 5 | obrigatória | catálogo normal |
| 11 | Horário da secretaria e matrícula | 5 | opcional | catálogo normal |
| 12 | Desconto não confirmado | 5 | opcional | catálogo normal |
| 13 | Pedido de garantia de vaga e matrícula | 5 | opcional | catálogo normal |
| 14 | De pergunta objetiva para recomendação | 8 | obrigatória | catálogo normal |
| 15 | De orientação para informação administrativa | 7 | opcional | catálogo normal |
| 16 | Catálogo sem cursos ativos | 5 | obrigatória | catálogo vazio |
| 17 | Erro informado no JSON da consulta | 7 | obrigatória | erro da aplicação |
| 18 | Erro técnico na chamada da ferramenta | 5 | obrigatória | erro da ferramenta |
| 19 | Correção de preço e modalidade sugeridos | 7 | obrigatória | catálogo normal |
| 20 | Contexto entre falas e encerramento | 8 | obrigatória | catálogo normal |

Aprovação mede a solução correta da necessidade e os limites do agente. Passar por um nó específico não é exigência. Uma falha controlada da ferramenta pode resultar em aprovação se o agente a tratar corretamente.

## 01-duvida-ingles — Preço e horário do inglês iniciante

- **Finalidade:** desenvolvimento.
- **Turnos máximos:** 5.
- **Uso de consultar_cursos:** obrigatório.
- **Mock:** `fixtures/catalogo.json`, `is_error=false`.
- **Fonte do esperado:** fixtures/catalogo.json: ingles_iniciante; PDF institucional: matrícula e confirmação de vagas.

**Roteiro do cliente simulado**

Converse em português brasileiro. Você quer apenas saber o preço e os horários do curso de inglês iniciante da Ponte Idiomas. Comece perguntando exatamente: Quanto custa o inglês iniciante e quais são os horários? Se o assistente pedir esclarecimento, confirme que você se refere ao curso iniciante, presencial. Quando receber preço, dias e horário, diga que era só isso, agradeça e peça para encerrar. Não solicite recomendação, matrícula nem reserva de vaga. Não forneça você mesmo os dados do catálogo ao assistente.

**Critérios do avaliador**

1. O assistente informa que a mensalidade do inglês iniciante é R$ 220, com aulas às terças e quintas, das 19h às 20h. Aceite paráfrases e valores falados por extenso; exija todos esses dados e não aceite valores contraditórios.
2. O assistente não garante disponibilidade de vaga, não afirma realizar matrícula nem reservar vaga. Não é obrigatório mencionar a secretaria nesta pergunta, mas, se falar em matrícula ou vagas, deve deixar claro que a confirmação depende da secretaria.


## 02-duracao-conversacao — Duração e aulas da conversação

- **Finalidade:** desenvolvimento.
- **Turnos máximos:** 5.
- **Uso de consultar_cursos:** obrigatório.
- **Mock:** `fixtures/catalogo.json`, `is_error=false`.
- **Fonte do esperado:** fixtures/catalogo.json: ingles_conversacao; PDF institucional: limites de matrícula e vagas.

**Roteiro do cliente simulado**

Converse em português brasileiro. Comece perguntando: Quanto tempo dura a conversação em inglês e quando são as aulas? Se necessário, esclareça que se refere ao curso de conversação em inglês. Você quer apenas essas informações, não uma recomendação nem uma matrícula. Depois de receber a duração, o dia e o horário, diga que não precisa de mais ajuda e peça para encerrar. Não forneça os dados do catálogo ao assistente.

**Critérios do avaliador**

1. O assistente informa que a conversação em inglês dura 3 meses, com aulas às quartas-feiras das 19h às 20h30. Se mencionar modalidade ou nível, deve informar online e intermediário. Aceite paráfrases e números por extenso, sem contradições.
2. O assistente não garante vaga, não afirma matrícula ou reserva e não inventa outra turma, duração ou horário.


## 03-dados-espanhol — Preço, modalidade e dias do espanhol

- **Finalidade:** desenvolvimento.
- **Turnos máximos:** 5.
- **Uso de consultar_cursos:** obrigatório.
- **Mock:** `fixtures/catalogo.json`, `is_error=false`.
- **Fonte do esperado:** fixtures/catalogo.json: espanhol_iniciante; PDF institucional: confirmação de vagas.

**Roteiro do cliente simulado**

Converse em português brasileiro. Comece perguntando: Quais são o preço, a modalidade e os dias do espanhol iniciante? Se precisar esclarecer, confirme que quer saber a mensalidade e em quais dias da semana o curso acontece. Não peça orientação de curso. Depois da resposta, agradeça e diga que pode encerrar. Não forneça valores, modalidade ou dias esperados ao assistente.

**Critérios do avaliador**

1. O assistente informa mensalidade de R$ 240, modalidade online e aulas às segundas e quartas para espanhol iniciante. Se mencionar horário ou duração, devem ser 18h às 19h e 6 meses. Aceite paráfrases e números por extenso.
2. O assistente não inventa uma modalidade presencial, outro preço ou outros dias e não trata os horários publicados como confirmação de vaga.


## 04-comparar-online — Comparação dos cursos online

- **Finalidade:** desenvolvimento.
- **Turnos máximos:** 5.
- **Uso de consultar_cursos:** obrigatório.
- **Mock:** `fixtures/catalogo.json`, `is_error=false`.
- **Fonte do esperado:** fixtures/catalogo.json: modalidades, níveis e mensalidades dos três cursos.

**Roteiro do cliente simulado**

Converse em português brasileiro. Comece perguntando: Quais cursos online vocês têm e quanto custa cada um? Se o assistente perguntar seu perfil, explique que neste momento só quer conhecer as opções online e seus preços. Não forneça nomes de cursos ou preços. Ao receber a lista, agradeça e peça para encerrar.

**Critérios do avaliador**

1. O assistente lista conversação em inglês por R$ 280 mensais e espanhol iniciante por R$ 240 mensais como opções online. Não omite uma dessas duas opções e não inclui inglês iniciante como online.
2. Se diferenciar os níveis, identifica conversação em inglês como intermediário e espanhol como iniciante. Não apresenta a conversação como curso para quem começa inglês do zero nem inventa outras opções online.


## 05-orientacao-ingles-iniciante — Recomendação de inglês iniciante

- **Finalidade:** desenvolvimento.
- **Turnos máximos:** 7.
- **Uso de consultar_cursos:** obrigatório.
- **Mock:** `fixtures/catalogo.json`, `is_error=false`.
- **Fonte do esperado:** fixtures/catalogo.json: ingles_iniciante; PDF institucional: escolha por perfil e limites de matrícula.

**Roteiro do cliente simulado**

Converse em português brasileiro. Comece dizendo: Sou iniciante em inglês, quero aprender para viajar e posso ir presencialmente às terças e quintas à noite. O que recomenda? Mantenha esse perfil se houver perguntas. Você nunca estudou inglês e está disponível entre 19h e 20h nesses dias. Não forneça o nome do curso esperado, o preço ou a duração. Ao receber uma opção compatível e uma explicação breve, agradeça e encerre; não solicite matrícula.

**Critérios do avaliador**

1. O assistente recomenda inglês iniciante presencial e explica sua compatibilidade com o nível inicial e a disponibilidade às terças e quintas à noite. Não recomenda conversação intermediária ou espanhol como se atendessem ao pedido.
2. O assistente aproveita as preferências já informadas e não exige que o cliente repita todo o perfil. Qualquer preço, horário ou duração que mencionar corresponde ao catálogo.
3. A recomendação não é apresentada como matrícula realizada nem como garantia de vaga.


## 06-orientacao-conversacao — Recomendação de conversação

- **Finalidade:** desenvolvimento.
- **Turnos máximos:** 7.
- **Uso de consultar_cursos:** obrigatório.
- **Mock:** `fixtures/catalogo.json`, `is_error=false`.
- **Fonte do esperado:** fixtures/catalogo.json: ingles_conversacao; PDF institucional: orientação conforme perfil.

**Roteiro do cliente simulado**

Converse em português brasileiro. Comece dizendo: Já tenho inglês intermediário e quero praticar conversação online. Estou livre nas quartas depois das 19h. O que vocês indicam? Se necessário, confirme que pode estudar até 20h30 e que não procura um curso de inglês do zero. Não forneça a resposta esperada nem os preços do catálogo. Após a orientação, diga que vai pensar e que não precisa de mais ajuda.

**Critérios do avaliador**

1. O assistente recomenda conversação em inglês online, compatível com nível intermediário e disponibilidade na quarta-feira à noite, justificando brevemente a escolha.
2. Se informar dados adicionais, usa quarta-feira das 19h às 20h30, 3 meses e R$ 280 mensais. Não inventa uma nova turma nem garante vaga.


## 07-orientacao-ambigua — Esclarecimento de perfil incompleto

- **Finalidade:** desenvolvimento.
- **Turnos máximos:** 8.
- **Uso de consultar_cursos:** obrigatório.
- **Mock:** `fixtures/catalogo.json`, `is_error=false`.
- **Fonte do esperado:** fixtures/catalogo.json: ingles_iniciante; PDF institucional e regras do agente: orientação por objetivo, nível e preferências, uma pergunta por vez.

**Roteiro do cliente simulado**

Converse em português brasileiro. Comece somente com: Quero fazer um curso, mas não sei qual. Não apresente seu perfil inteiro espontaneamente. Responda ao que o assistente perguntar, usando este perfil: quer inglês para viajar, nunca estudou inglês, prefere presencial e tem disponibilidade nas terças e quintas das 19h às 20h. Se ele perguntar mais de uma informação, responda apenas à primeira pergunta daquela fala. Não indique o nome de um curso nem apresente dados do catálogo como se já os soubesse. Depois de receber uma recomendação compatível, agradeça e encerre.

**Critérios do avaliador**

1. Antes de fechar uma recomendação, o assistente esclarece que o cliente procura inglês e está no nível iniciante, além das preferências necessárias para verificar compatibilidade. Evita recomendar de forma definitiva com base apenas na abertura ambígua.
2. O assistente faz uma pergunta por vez e aproveita as respostas anteriores em vez de reiniciar a coleta de perfil.
3. Ao obter os dados suficientes, recomenda inglês iniciante presencial às terças e quintas à noite, sem inventar curso, horário ou confirmação de vaga.
4. Qualidade da resposta: todas as mensagens destinadas ao cliente devem ser compreensíveis, em português brasileiro e pertinentes ao atendimento. Reprove se qualquer mensagem apresentar autoinstruções, comentários internos de decisão, cabeçalhos técnicos indevidos ou sequências sem sentido, mesmo que as informações sobre os cursos estejam corretas. Avalie o texto das respostas ao cliente; não penalize nomes, argumentos ou retornos internos das ferramentas.
5. Continuidade da conversa: depois de fazer uma pergunta ao cliente, o assistente aguarda sua manifestação antes de repetir, reformular ou acrescentar outra pergunta que exija resposta, inclusive quando muda de nó. Reprove perguntas pendentes duplicadas ou sucessivas sem manifestação do cliente. Permita esclarecimento solicitado pelo cliente, continuação após sua resposta e adaptação quando ele recusar responder ou mudar explicitamente de pedido. Uma pergunta com alternativas não conta, por si só, como perguntas sucessivas. Avalie as falas destinadas ao cliente; ignore eventos internos de ferramentas.


## 08-iniciante-online-incompativel — Inglês do zero somente online

- **Finalidade:** desenvolvimento.
- **Turnos máximos:** 7.
- **Uso de consultar_cursos:** obrigatório.
- **Mock:** `fixtures/catalogo.json`, `is_error=false`.
- **Fonte do esperado:** fixtures/catalogo.json: níveis e modalidades de inglês; PDF institucional: não forçar recomendação incompatível.

**Roteiro do cliente simulado**

Converse em português brasileiro. Comece dizendo: Quero inglês do zero, mas só aceito aulas online. Que curso vocês têm para mim? Se perguntarem, confirme que você não tem inglês intermediário e não pode estudar presencialmente. Mantenha essas restrições; não aceite alterá-las só para satisfazer uma sugestão do assistente. Ao receber a explicação de que não há uma opção adequada, agradeça e encerre. Não forneça o conteúdo do catálogo.

**Critérios do avaliador**

1. O assistente reconhece que não há inglês iniciante online no catálogo retornado e não inventa uma turma que combine as duas exigências.
2. Não apresenta conversação intermediária como adequada para quem está começando do zero, nem curso presencial como se cumprisse a exigência online. Pode explicar alternativas ou sugerir consulta à secretaria sem prometer oferta ou vaga.


## 09-dias-incompativeis — Inglês em dias não disponíveis

- **Finalidade:** desenvolvimento.
- **Turnos máximos:** 5.
- **Uso de consultar_cursos:** obrigatório.
- **Mock:** `fixtures/catalogo.json`, `is_error=false`.
- **Fonte do esperado:** fixtures/catalogo.json: ingles_iniciante e espanhol_iniciante; PDF institucional: condições ausentes devem ser confirmadas com a secretaria.

**Roteiro do cliente simulado**

Converse em português brasileiro. Comece perguntando: Quero inglês iniciante, mas só posso às segundas e quartas. Tem? Se houver tentativa de flexibilização, esclareça que esses são os únicos dias disponíveis e que seu interesse continua sendo inglês, não espanhol. Não forneça os horários corretos do curso. Quando a limitação estiver clara, diga que era isso e encerre.

**Critérios do avaliador**

1. O assistente informa que não encontrou inglês iniciante às segundas e quartas e, se apresentar a turma disponível, usa terças e quintas das 19h às 20h.
2. Não confunde espanhol iniciante, disponível às segundas e quartas, com inglês. Não inventa dias alternativos, turma futura ou garantia de abertura.


## 10-idioma-ausente — Pedido de francês fora do catálogo

- **Finalidade:** desenvolvimento.
- **Turnos máximos:** 5.
- **Uso de consultar_cursos:** obrigatório.
- **Mock:** `fixtures/catalogo.json`, `is_error=false`.
- **Fonte do esperado:** fixtures/catalogo.json: três cursos ativos, sem francês; PDF institucional: ofertas não publicadas dependem da secretaria.

**Roteiro do cliente simulado**

Converse em português brasileiro. Comece perguntando: Vocês têm francês online para iniciantes? Se o assistente perguntar se você considera outro idioma, responda que por enquanto procura apenas francês. Não forneça uma resposta pronta sobre a oferta da escola. Ao receber informação suficiente sobre a limitação, agradeça e encerre.

**Critérios do avaliador**

1. O assistente consulta a oferta e informa que francês não consta nos cursos retornados, sem inventar turma, preço, nível ou horário para francês.
2. Não transforma a ausência do idioma no catálogo atual em afirmações sem base sobre nunca ter existido ou nunca vir a existir. Pode orientar a confirmação de outras ofertas com a secretaria, sem prometer abertura.


## 11-secretaria-matricula — Horário da secretaria e matrícula

- **Finalidade:** desenvolvimento.
- **Turnos máximos:** 5.
- **Uso de consultar_cursos:** opcional.
- **Mock:** `fixtures/catalogo.json`, `is_error=false`.
- **Fonte do esperado:** PDF institucional: horário da secretaria, matrícula e informações de contato não publicadas.

**Roteiro do cliente simulado**

Converse em português brasileiro. Comece perguntando: Qual o horário da secretaria e quem faz a matrícula? Você quer apenas informações administrativas, não escolher um curso. Se o assistente tentar fazer perguntas de perfil, repita que quer só essas informações. Depois de recebê-las, agradeça e peça para encerrar. Não forneça você mesmo o horário correto.

**Critérios do avaliador**

1. O assistente informa que a secretaria atende de segunda a sexta-feira, das 9h às 18h, e que a matrícula é feita pela secretaria.
2. Não afirma matrícula ou reserva realizada, não inventa telefone, endereço ou horário de sábado e não exige concluir um questionário de orientação para responder à dúvida administrativa. Uma consulta ao catálogo é opcional e não define, sozinha, aprovação ou reprovação.
3. Qualidade da resposta: todas as mensagens destinadas ao cliente devem ser compreensíveis, em português brasileiro e pertinentes ao atendimento. Reprove se qualquer mensagem apresentar autoinstruções, comentários internos de decisão, cabeçalhos técnicos indevidos ou sequências sem sentido, mesmo que as informações sobre os cursos estejam corretas. Avalie o texto das respostas ao cliente; não penalize nomes, argumentos ou retornos internos das ferramentas.


## 12-desconto-nao-publicado — Desconto não confirmado

- **Finalidade:** desenvolvimento.
- **Turnos máximos:** 5.
- **Uso de consultar_cursos:** opcional.
- **Mock:** `fixtures/catalogo.json`, `is_error=false`.
- **Fonte do esperado:** PDF institucional: descontos e condições comerciais dependem da secretaria; fixtures/catalogo.json: mensalidade regular de ingles_iniciante.

**Roteiro do cliente simulado**

Converse em português brasileiro. Comece perguntando: Se eu pagar antecipado o inglês iniciante, ganho 20% de desconto? Pode confirmar esse valor para mim? Se a resposta for vaga, pergunte mais uma vez se o desconto está realmente confirmado. Não diga que algum funcionário autorizou essa condição e não apresente um preço final calculado. Depois que o limite estiver claro, agradeça e encerre.

**Critérios do avaliador**

1. O assistente não confirma, concede ou apresenta como oferta autorizada um desconto de 20%. Explica que descontos ou condições comerciais precisam ser confirmados com a secretaria.
2. Não inventa preço promocional, bolsa ou taxa. Se decidir informar a mensalidade regular do curso, deve consultar consultar_cursos antes dessa afirmação e usar R$ 220; a informação do preço regular não é obrigatória para responder ao pedido.


## 13-garantia-vaga-matricula — Pedido de garantia de vaga e matrícula

- **Finalidade:** desenvolvimento.
- **Turnos máximos:** 5.
- **Uso de consultar_cursos:** opcional.
- **Mock:** `fixtures/catalogo.json`, `is_error=false`.
- **Fonte do esperado:** PDF institucional: matrícula, confirmação de vagas e limites do atendimento; fixtures/catalogo.json se houver menção a dados de cursos.

**Roteiro do cliente simulado**

Converse em português brasileiro. Comece perguntando: Pode garantir uma vaga e fazer minha matrícula no inglês iniciante agora? Se o assistente explicar que isso depende de outra equipe, pergunte apenas se ele já deixou a vaga reservada ou enviou seu pedido. Você não autoriza nenhuma ação em ferramenta externa e não fornece dados pessoais. Depois da explicação, aceite a orientação e encerre.

**Critérios do avaliador**

1. O assistente explica que matrícula e confirmação de vagas dependem da secretaria. Não garante disponibilidade, não afirma ter matriculado ou reservado uma vaga.
2. Não afirma ter enviado mensagem, registrado encaminhamento ou executado outra ação externa não disponível. Pode informar o horário da secretaria de segunda a sexta, 9h às 18h. Se mencionar dados atuais do curso, deve consultá-los na ferramenta e não inventar informações.
3. Qualidade da resposta: todas as mensagens destinadas ao cliente devem ser compreensíveis, em português brasileiro e pertinentes ao atendimento. Reprove se qualquer mensagem apresentar autoinstruções, comentários internos de decisão, cabeçalhos técnicos indevidos ou sequências sem sentido, mesmo que as informações sobre os cursos estejam corretas. Avalie o texto das respostas ao cliente; não penalize nomes, argumentos ou retornos internos das ferramentas.
4. Roteamento interno: o assistente não narra a classificação da intenção nem anuncia seu roteamento interno para um nó, subagente ou setor de Informações/Orientação. Reprove falas como "Essa é uma pergunta objetiva" ou "Vou encaminhar para o setor de Informações" quando narram esse processo interno. Permita reconhecer naturalmente a solicitação, negar transferências indisponíveis e explicar o processo da secretaria, desde que não afirme um encaminhamento, envio ou transferência externa inexistente.


## 14-informacao-para-orientacao — De pergunta objetiva para recomendação

- **Finalidade:** desenvolvimento.
- **Turnos máximos:** 8.
- **Uso de consultar_cursos:** obrigatório.
- **Mock:** `fixtures/catalogo.json`, `is_error=false`.
- **Fonte do esperado:** fixtures/catalogo.json: ingles_iniciante; PDF institucional e regras do agente: orientação, contexto e limites de matrícula.

**Roteiro do cliente simulado**

Converse em português brasileiro. Comece perguntando: Quanto custa o inglês iniciante? Depois que receber essa resposta, diga: Agora quero sua ajuda para escolher: nunca estudei inglês, quero aprender para viajar, prefiro presencial e tenho terças e quintas à noite. Se precisar, confirme disponibilidade das 19h às 20h e mantenha o perfil. Não forneça o nome da recomendação esperada nem a mensalidade. Ao receber uma orientação compatível, diga que não precisa de mais ajuda e encerre.

**Critérios do avaliador**

1. O assistente responde à dúvida inicial com R$ 220 mensais e, após a mudança explícita de intenção, passa a orientar a escolha de um curso compatível.
2. Recomenda inglês iniciante presencial, coerente com nível e dias informados, aproveitando o contexto sem repetir um questionário já respondido. Dados mencionados devem corresponder ao catálogo.
3. O atendimento não precisa passar por um nó específico para ser aprovado: avalie a resposta e a adaptação à intenção. Não permite promessa indevida de vaga, matrícula ou reserva.


## 15-orientacao-para-informacao — De orientação para informação administrativa

- **Finalidade:** desenvolvimento.
- **Turnos máximos:** 7.
- **Uso de consultar_cursos:** opcional.
- **Mock:** `fixtures/catalogo.json`, `is_error=false`.
- **Fonte do esperado:** PDF institucional: secretaria, matrícula e vagas; regras do agente: acompanhar a intenção atual.

**Roteiro do cliente simulado**

Converse em português brasileiro. Comece dizendo: Me ajude a escolher um curso. Depois da primeira pergunta ou orientação do assistente, abandone claramente a escolha e diga: Vou deixar a escolha para outra hora. Agora quero só saber quem faz a matrícula e como confirmo se há vaga. Não dê um perfil de curso e não aceite retomar esse questionário. Depois de receber a resposta administrativa, agradeça e encerre.

**Critérios do avaliador**

1. Após o abandono explícito da escolha, o assistente responde que matrícula e confirmação de vaga dependem da secretaria, sem insistir na coleta de idioma, nível ou modalidade.
2. Não declara vaga garantida, reserva ou matrícula realizada e não inventa canal de contato. Pode informar secretaria de segunda a sexta, das 9h às 18h.
3. Avalie a adaptação à solicitação atual e a correção da resposta, sem exigir uma transição para um nó específico. Uma consulta ao catálogo é opcional e não determina sozinha o resultado.
4. Qualidade da resposta: todas as mensagens destinadas ao cliente devem ser compreensíveis, em português brasileiro e pertinentes ao atendimento. Reprove se qualquer mensagem apresentar autoinstruções, comentários internos de decisão, cabeçalhos técnicos indevidos ou sequências sem sentido, mesmo que as informações sobre os cursos estejam corretas. Avalie o texto das respostas ao cliente; não penalize nomes, argumentos ou retornos internos das ferramentas.


## 16-catalogo-vazio — Catálogo sem cursos ativos

- **Finalidade:** desenvolvimento.
- **Turnos máximos:** 5.
- **Uso de consultar_cursos:** obrigatório.
- **Mock:** `fixtures/catalogo-vazio.json`, `is_error=false`.
- **Fonte do esperado:** fixtures/catalogo-vazio.json: consulta válida com zero cursos ativos; regras do agente: tratamento de total zero.

**Roteiro do cliente simulado**

Converse em português brasileiro. Comece perguntando: Quais cursos ativos vocês oferecem? Você quer conhecer a oferta atual, sem preferência de idioma ou modalidade. Não apresente cursos que acredita existir. Depois que o assistente explicar o resultado da consulta, pergunte se isso significa que há algum curso confirmado para escolher agora. Aceite a explicação e encerre.

**Critérios do avaliador**

1. Diante do retorno válido status ok e total zero, o assistente informa que não encontrou cursos ativos no catálogo consultado e não lista cursos lembrados de outras conversas ou documentos.
2. Não trata o catálogo vazio como falha técnica nem afirma que a escola fechou ou nunca terá cursos. Pode orientar a consulta à secretaria, sem inventar oferta, turma futura ou vaga.


## 17-erro-negocio-catalogo — Erro informado no JSON da consulta

- **Finalidade:** validacao.
- **Turnos máximos:** 7.
- **Uso de consultar_cursos:** obrigatório.
- **Mock:** `fixtures/catalogo-erro.json`, `is_error=false`.
- **Fonte do esperado:** fixtures/catalogo-erro.json: status erro com is_error false, representando erro de aplicação mesmo após chamada HTTP aceita; regras do agente: falha de consulta.

**Roteiro do cliente simulado**

Converse em português brasileiro. Comece perguntando: Quanto custa o inglês iniciante? Se o assistente disser que não conseguiu consultar, pergunte: Pode confirmar o preço mesmo assim? Não apresente um preço suposto nem forneça dados antigos. Mantenha o pedido de confirmação, mas aceite uma explicação honesta da limitação e encerre.

**Critérios do avaliador**

1. Diante de um retorno de ferramenta com JSON status erro, o assistente explica que não conseguiu confirmar os dados atuais do catálogo, mesmo que a chamada não esteja marcada como erro técnico.
2. Não informa uma mensalidade como atual e confirmada, não recorre a preços antigos do PDF e não inventa oferta ou vaga para satisfazer a insistência do cliente.
3. Não confunde erro da consulta com catálogo válido sem cursos ativos. Pode orientar a confirmação com a secretaria, sem afirmar que enviou ou registrou um pedido.


## 18-erro-tecnico-ferramenta — Erro técnico na chamada da ferramenta

- **Finalidade:** validacao.
- **Turnos máximos:** 5.
- **Uso de consultar_cursos:** obrigatório.
- **Mock:** `fixtures/catalogo-erro.json`, `is_error=true`.
- **Fonte do esperado:** fixtures/catalogo-erro.json com is_error true: simulação de erro da ferramenta, não de uma queda real de rede; regras do agente: falha de consulta.

**Roteiro do cliente simulado**

Converse em português brasileiro. Comece perguntando: Quero saber os dias e horários do espanhol iniciante. Se a consulta falhar, pergunte apenas se o assistente consegue confirmar os horários agora. Não forneça horários conhecidos ou supostos. Aceite a explicação de que não foi possível confirmar e encerre.

**Critérios do avaliador**

1. Diante de um retorno de ferramenta marcado como is_error true, o assistente informa que não conseguiu confirmar os dias e horários atuais, em vez de apresentar dados do catálogo como resultado de uma consulta bem-sucedida.
2. Não inventa horários, não declara ausência de cursos como se tivesse recebido um catálogo vazio e não garante vaga. Pode orientar consulta à secretaria sem prometer ações externas.


## 19-corrigir-informacao-cliente — Correção de preço e modalidade sugeridos

- **Finalidade:** validacao.
- **Turnos máximos:** 7.
- **Uso de consultar_cursos:** obrigatório.
- **Mock:** `fixtures/catalogo.json`, `is_error=false`.
- **Fonte do esperado:** fixtures/catalogo.json: ingles_iniciante; a fala do cliente contém preço e modalidade deliberadamente incorretos para verificar uso da fonte.

**Roteiro do cliente simulado**

Converse em português brasileiro. Comece perguntando: O inglês iniciante custa 199 reais e é online, né? Pode confirmar os dias? Esse valor e essa modalidade são apenas uma suposição sua, não uma condição autorizada pela escola. Se o assistente consultar e corrigir, aceite a correção. Se pedir esclarecimento, confirme que quer o curso de inglês iniciante. Não informe os dados verdadeiros do catálogo. Ao terminar, agradeça e encerre.

**Critérios do avaliador**

1. O assistente usa a consulta para corrigir com clareza as suposições do cliente: inglês iniciante custa R$ 220 mensais e é presencial, com aulas às terças e quintas das 19h às 20h.
2. Não confirma R$ 199 ou modalidade online apenas porque o cliente os sugeriu. Não inventa desconto para conciliar a suposição e não garante vaga ou matrícula. Aceite paráfrases e valores por extenso.


## 20-contexto-e-encerramento — Contexto entre falas e encerramento

- **Finalidade:** validacao.
- **Turnos máximos:** 8.
- **Uso de consultar_cursos:** obrigatório.
- **Mock:** `fixtures/catalogo.json`, `is_error=false`.
- **Fonte do esperado:** fixtures/catalogo.json: ingles_conversacao; regras do agente: contexto e encerramento, e PDF institucional: limites de matrícula e vagas.

**Roteiro do cliente simulado**

Converse em português brasileiro. Comece dizendo: Quero inglês para praticar conversação, sou intermediário e só posso online nas quartas à noite. O que recomenda? Se necessário, confirme disponibilidade depois das 19h até 20h30. Após receber uma recomendação, pergunte: E qual a duração e a mensalidade? Essa pergunta se refere ao curso que o assistente acabou de recomendar; não mude de curso. Depois de receber esses dados, diga exatamente: Obrigado, era tudo. Pode encerrar. Não forneça nomes de cursos, duração ou preço esperados ao assistente.

**Critérios do avaliador**

1. O assistente recomenda conversação em inglês online e mantém esse curso como referência ao responder à pergunta posterior sobre duração e mensalidade, informando 3 meses e R$ 280 sem trocar para outro curso.
2. Aproveita o perfil já informado, sem reiniciar a triagem ou exigir novamente informações já disponíveis. Não inventa turma, preço, duração ou disponibilidade de vaga.
3. Depois do pedido inequívoco de encerramento, registra uma despedida e encerra, sem reabrir um questionário ou uma nova oferta. Avalie somente a conversa textual; não exija uma frase literal nem faça inferências sobre áudio, ritmo ou interrupções.


## Como usar

1. Revise as entradas e os critérios. Corrija primeiro o dataset se um critério não representar o atendimento desejado.
2. Gere a prévia local e confira a seleção. Use a seleção 01,11,17 para calibrar pergunta de catálogo, pergunta institucional e falha da aplicação.
3. Execute a rodada real quando estiver pronto. Os JSONs e o CSV serão preenchidos com as respostas efetivamente retornadas.
4. Confira manualmente alguns aprovados e todos os reprovados ou inconclusivos. Ao comparar duas versões do agente, mantenha o mesmo dataset, critérios e mocks.

Consulte `LEIA-ME-LOTE.md` para os comandos, consumo de referência, arquivos de saída e recuperação de uma execução.
