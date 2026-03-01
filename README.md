
# Trabalho final de sistemas distribuidos
# Sync-Beat -- Documento do Projeto

## 1. Descrição Geral do Projeto

O Sync-Beat é um sistema distribuído competitivo no qual um servidor
central, denominado **Orquestrador**, emite uma sequência rítmica de
símbolos (comandos) que devem ser executados pelos nós clientes
(Jogadores) com precisão de milissegundos.

A proposta do sistema é avaliar não apenas a capacidade de reação do
jogador, mas principalmente a correta ordenação e validação de eventos
em um ambiente distribuído sujeito a latência e variações de rede.

### 1.1 Analogia Conceitual

O funcionamento do sistema pode ser comparado a jogos rítmicos, nos
quais o jogador deve pressionar uma tecla no momento exato em que um
comando é exibido na tela.

No Sync-Beat:

-   O servidor envia um sinal (por exemplo, a letra 'W').
-   O cliente exibe o sinal ao jogador.
-   O jogador possui uma janela de oportunidade (por exemplo, 500 ms)
    para reagir.

O principal desafio técnico consiste em garantir que, caso dois
jogadores realizem a ação simultaneamente, o servidor seja capaz de
determinar de forma justa quem foi mais preciso, independentemente da
qualidade da conexão de cada participante.

------------------------------------------------------------------------

## 2. Arquitetura do Sistema

A arquitetura do sistema está organizada em três pilares principais:

### 2.1 Camada de Apresentação -- Front-end (React)

Responsabilidades:

-   Exibir os símbolos na interface do usuário.
-   Capturar eventos de teclado.
-   Gerar o timestamp local.
-   Atualizar e anexar o contador do Relógio Lógico de Lamport no
    momento exato do clique.
-   Enviar os dados ao servidor por meio do middleware.

------------------------------------------------------------------------

### 2.2 Camada de Lógica e Middleware -- Servidor (Node.js)

#### a) Orquestrador

-   Define qual será o próximo comando.
-   Determina o momento exato de sua exibição.

#### b) Middleware (Socket.io)

-   Gerencia a comunicação assíncrona entre múltiplos clientes.
-   Controla conexões, reconexões e transmissão de eventos em tempo
    real.

#### c) Árbitro de Concorrência

-   Recebe os eventos enviados pelos jogadores.
-   Compara os relógios lógicos.
-   Determina o vencedor da rodada com base em critérios de ordenação
    lógica.

------------------------------------------------------------------------

### 2.3 Camada de Persistência -- Banco de Dados (SQL)

Responsável por:

-   Armazenar o ranking global.
-   Registrar logs detalhados dos eventos.
-   Garantir rastreabilidade e auditoria do funcionamento da
    sincronização.

------------------------------------------------------------------------

## 3. Atendimento aos Requisitos da Disciplina

### 3.1 Comunicação e Middleware (RPC/RMI e Abstração)

Um dos requisitos do projeto é que o cliente não manipule diretamente
detalhes de rede, como IP, porta ou buffers.

Para atender a esse requisito, foi adotado o Socket.io como middleware
de comunicação.

No front-end, o cliente apenas realiza chamadas como:

    socket.emit('enviar_clique', dados)

Essa abordagem simula o conceito de RPC (Remote Procedure Call), pois,
para o cliente, a operação aparenta ser uma chamada local. O middleware
é responsável por serializar os dados (em formato JSON), transmiti-los
ao servidor e gerenciar a comunicação subjacente.

Dessa forma, garante-se a abstração completa da camada de rede.

------------------------------------------------------------------------

## 4. Características de Sistemas Distribuídos

### 4.1 Sincronização -- Relógios Lógicos de Lamport

#### Problema

Em ambientes reais, a latência de rede pode variar significativamente.
Caso o servidor utilizasse apenas o tempo de chegada dos eventos,
jogadores com conexões mais rápidas seriam favorecidos.

#### Solução

Foi implementado o Relógio Lógico de Lamport.

Cada evento enviado pelo cliente contém um número sequencial (L), que
representa sua posição lógica na linha do tempo distribuída.

Em situações de condição de corrida (eventos muito próximos), o servidor
utiliza o valor do relógio lógico para determinar a ordem correta dos
acontecimentos, garantindo justiça e consistência.

------------------------------------------------------------------------

### 4.2 Tolerância a Falhas (Disponibilidade)

O sistema foi projetado para suportar falhas parciais sem comprometer
completamente sua operação.

-   O Socket.io possui mecanismo nativo de heartbeat (batimento
    cardíaco).
-   Em caso de instabilidade de conexão, são realizadas tentativas
    automáticas de reconexão.

No servidor:

-   São utilizados blocos de tratamento de exceção (try/catch) na
    conexão com o banco de dados.
-   Caso o banco de dados fique temporariamente indisponível, o servidor
    principal continua operando.

Essa abordagem assegura maior disponibilidade e resiliência do sistema.

------------------------------------------------------------------------

### 4.3 Descoberta de Serviços (Transparência de Localização)

#### Problema

Em sistemas distribuídos reais, o endereço IP do servidor pode mudar
devido a reinicializações, migrações ou escalabilidade. Caso o endereço
esteja fixo no código do cliente, o sistema se tornaria frágil.

#### Solução

Foi proposta a implementação de um Service Registry simplificado.

Funcionamento:

1.  O servidor Node.js, ao iniciar, registra seu endereço em um endpoint
    ou arquivo conhecido.
2.  O cliente React, antes de iniciar a sessão, consulta esse catálogo
    para descobrir o endereço e a porta atual do servidor.

Essa estratégia garante transparência de localização e prepara o sistema
para cenários de escalabilidade.

------------------------------------------------------------------------

## 5. Considerações Finais

O Sync-Beat constitui uma aplicação prática de conceitos fundamentais de
Sistemas Distribuídos, incluindo:

-   Comunicação mediada por middleware.
-   Abstração via RPC.
-   Sincronização com relógios lógicos.
-   Tolerância a falhas.
-   Descoberta de serviços.
-   Separação arquitetural em camadas.

O projeto demonstra, de forma aplicada, como desafios relacionados a
concorrência, latência e consistência podem ser tratados de maneira
estruturada e tecnicamente fundamentada.
