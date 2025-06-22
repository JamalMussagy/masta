💖 Curador de Relacionamentos Bot 💑
Bem-vindo ao Curador de Relacionamentos Bot! Este bot foi desenvolvido para ajudar casais e indivíduos a fortalecerem os seus laços, navegarem por desafios diários e encontrarem inspiração para manter a paixão acesa. Com dicas personalizadas e um quiz interativo, o nosso bot é o seu parceiro digital para uma vida a dois mais feliz.

✨ Funcionalidades Principais
Dicas de Relacionamento Personalizadas: Obtenha conselhos práticos e inspiradores sobre diversos temas como romance, encontros, surpresas e resolução de conflitos, gerados dinamicamente por Inteligência Artificial (Google Gemini).

Quiz de Conhecimento de Relacionamento: Teste os seus conhecimentos com um quiz dinâmico e sempre diferente, gerado pela IA. As perguntas são informais, motivacionais e focadas em situações do dia a dia, com as suas respostas e pontuação reveladas apenas no final!

Gestão de Favoritos: Salve as suas dicas preferidas para consultar mais tarde.

Eventos Especiais: Descubra datas comemorativas e ideias para celebrar momentos importantes.

Interface Amigável: Navegação intuitiva com botões inline para uma experiência de utilizador fluida.

Conteúdo Adaptável: Dicas e opções de quiz formatadas para uma leitura confortável em telemóveis.

🚀 Como Começar (para Desenvolvedores)
Para configurar e executar o bot localmente, siga estes passos:

Pré-requisitos
Python 3.8+

Uma conta Telegram e um token de bot (obtido do @BotFather).

Acesso à Google Gemini API e uma chave de API válida (obtida do Google AI Studio).

Instalação
Clone o repositório (se estiver num repositório Git) ou salve o ficheiro bot_dicas.py no seu computador.

Instale as dependências Python:

pip install python-telegram-bot httpx

Configuração das Variáveis de Ambiente
Crie um ficheiro .env na mesma pasta do bot_dicas.py ou defina as seguintes variáveis de ambiente diretamente no seu sistema:

TELEGRAM_TOKEN: O token do seu bot do Telegram.

GEMINI_API_KEY: A sua chave da Google Gemini API.

Exemplo de ficheiro .env:

TELEGRAM_TOKEN="SEU_TOKEN_DO_TELEGRAM_AQUI"
GEMINI_API_KEY="SUA_CHAVE_GEMINI_API_AQUI"

Importante: Certifique-se de que a sua GEMINI_API_KEY está correta e ativa. Erros na geração de conteúdo da IA são frequentemente relacionados a uma chave inválida ou inativa.

Executar o Bot
Navegue até a pasta onde salvou o bot_dicas.py no seu terminal e execute:

python bot_dicas.py

O bot iniciará e estará pronto para receber mensagens no Telegram.

💡 Como Usar o Bot (para Utilizadores)
Iniciar o Bot: Procure o seu bot no Telegram e envie /start. Ele irá cumprimentá-lo e apresentar o menu principal.

Navegar pelo Menu: Utilize os botões inline para explorar as categorias (Romance, Encontros, Conselhos, Surpresas), iniciar o Quiz, ver Eventos, aceder aos seus Favoritos ou Pesquisar.

Pesquisar Dicas: Clique em "🔎 Pesquisar" e digite a sua pergunta ou tema (ex: "como pedir em namoro", "ideias para um encontro especial"). A IA irá gerar uma dica personalizada.

Quiz Interativo: Clique em "🧩 Quiz" para iniciar um jogo de 10 perguntas. As perguntas são de múltipla escolha e a sua pontuação, juntamente com as respostas corretas, será mostrada apenas no final do quiz.

Favoritar Dicas: Após receber uma dica (seja por pesquisa ou categoria), clique no botão "⭐ Favoritar" para guardá-la.

Gerir Favoritos: Aceda aos seus favoritos através do menu principal para ver ou remover dicas guardadas.

Eventos Especiais: Verifique "📅 Eventos" para datas comemorativas e mensagens especiais.

Opção "Ler Mais": Se uma dica for muito longa, apenas os primeiros dois parágrafos serão exibidos, com um botão "Ler Mais 📖" para expandir o conteúdo.

⚠️ Aviso sobre Conteúdo Gerado por IA
As dicas e perguntas do quiz são geradas por Inteligência Artificial (Google Gemini). Embora nos esforcemos para fornecer conteúdo útil e relevante, as respostas da IA podem, ocasionalmente, ser imprecisas, incompletas ou não refletir nuances específicas. Utilize as dicas como inspiração e guia, e sempre considere o seu próprio contexto e julgamento.

🤝 Suporte e Contacto
Para quaisquer dúvidas, sugestões ou problemas, entre em contacto com o suporte através do canal do Telegram, se disponível.

Aproveite o Curador de Relacionamentos Bot e que ele ajude a fortalecer os seus laços!
