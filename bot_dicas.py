from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode
import random
import json
import os
from datetime import datetime
import logging
import hashlib
import httpx  # Importar httpx para requisições assíncronas
import re
import asyncio

# --- Configuração Inicial ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuração usando variáveis de ambiente (recomendado)
TOKEN = os.getenv("TELEGRAM_TOKEN",
                  "7532112921:AAHugRTW-JVylkGPRdpzZvJj62kA7jZAQkI")
# ATENÇÃO: A CHAVE GEMINI_API_KEY FOI ATUALIZADA AQUI COM A CHAVE FORNECIDA.
# Por favor, certifique-se que esta chave é válida e está ativa no Google AI Studio.
GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY", "AIzaSyBF3sTUPEC3SM3UCY-xLrAsnWpzHQRFvQs")

# Diretório para salvar dados (ex: favoritos.json)
DATA_DIR = "bot_data"
os.makedirs(DATA_DIR, exist_ok=True)

# --- Classes de Filtro Personalizadas Atualizadas ---


class QuizStateActiveFilter(filters.BaseFilter):
    """Filtro para mensagens quando um quiz está ativo"""
    name = "quiz_state_active"

    # O método __call__ é o que é usado pela biblioteca para verificar o filtro
    def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Verifica se 'quiz_state' existe nos user_data, indicando que um quiz está ativo
        return 'quiz_state' in context.user_data


class QuizStateInactiveFilter(filters.BaseFilter):
    """Filtro para mensagens quando NÃO há quiz ativo"""
    name = "quiz_state_inactive"

    # O método __call__ é o que é usado pela biblioteca para verificar o filtro
    def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Verifica se 'quiz_state' NÃO existe nos user_data, indicando que nenhum quiz está ativo
        return 'quiz_state' not in context.user_data


# Crie instâncias dos filtros para serem usadas nos MessageHandlers
quiz_state_active = QuizStateActiveFilter()
quiz_state_inactive = QuizStateInactiveFilter()

# --- Sistema de Arquivos para Persistência ---


def load_data(filename):
    """Carrega dados JSON de um arquivo."""
    try:
        path = os.path.join(DATA_DIR, filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except json.JSONDecodeError:
        logger.error(
            f"Erro de decodificação JSON em {filename}. O arquivo pode estar corrompido ou vazio.")
        return {}
    except Exception as e:
        logger.error(f"Erro ao carregar {filename}: {str(e)}")
        return {}


def save_data(filename, data):
    """Salva dados JSON em um arquivo."""
    try:
        path = os.path.join(DATA_DIR, filename)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Erro ao salvar {filename}: {str(e)}")

# --- Módulos do Bot (Dados) ---


class QuizManager:
    # Definindo o número máximo de perguntas para o quiz por jogo
    MAX_QUIZ_QUESTIONS = 10
    # As perguntas serão geradas dinamicamente, mantemos o QUIZZES como um placeholder
    QUIZZES = {
        "conhecimento_relacionamento": {
            "title": "Quiz de Conhecimento de Relacionamento",
            "questions": []  # Este será preenchido dinamicamente ou com fallback
        }
    }


class SpecialEvents:
    DATES = {
        "01/01": {
            "message": "Feliz Ano Novo! 🎉",
        },
        "14/02": {
            "message": "Feliz Dia dos Namorados! 💝",
        }
    }

# --- Funções Auxiliares ---


async def handle_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lida com erros e envia uma mensagem amigável ao usuário."""
    error_msg = "⚠️ Ocorreu um erro inesperado. Por favor, tente novamente mais tarde."
    logger.error(f"Erro capturado: {context.error}", exc_info=True)
    try:
        # Primeiro, tenta responder a callback queries para evitar que fiquem a carregar
        if update.callback_query:
            try:
                await update.callback_query.answer("Ocorreu um erro. Tente novamente mais tarde.")
            except Exception:
                pass  # Ignora se a resposta falhar (ex: já respondida)

        # Em seguida, envia a mensagem de erro para o chat efetivo
        if update.effective_message:
            await update.effective_message.reply_text(error_msg)
        elif update.effective_chat:  # Fallback se não houver effective_message, mas houver um chat
            await update.effective_chat.send_message(error_msg)
        else:
            logger.warning(
                f"Não foi possível determinar para onde enviar a mensagem de erro para o update: {update}")
    except Exception as e:
        logger.error(
            f"Erro ao enviar mensagem de erro na handle_error: {str(e)}", exc_info=True)


def main_keyboard():
    """Retorna o teclado principal com botões inline, incluindo pesquisas frequentes."""
    keyboard = [
        [
            InlineKeyboardButton("💝 Romance", callback_data="cat_romance"),
            InlineKeyboardButton("💑 Encontros", callback_data="cat_dates")
        ],
        [
            InlineKeyboardButton("🛟 Conselhos", callback_data="cat_advice"),
            InlineKeyboardButton("🎁 Surpresas", callback_data="cat_surprise")
        ],
        [
            InlineKeyboardButton("🧩 Quiz", callback_data="menu_quiz"),
            InlineKeyboardButton("📅 Eventos", callback_data="menu_events")
        ],
        [
            InlineKeyboardButton("⭐ Favoritos", callback_data="menu_favs"),
            InlineKeyboardButton("🔎 Pesquisar", callback_data="menu_search")
        ],
        [
            InlineKeyboardButton("🤔 Como lidar com brigas?",
                                 callback_data="query_lidar_brigas"),
        ],
        [
            InlineKeyboardButton("💖 Como reacender a paixão?",
                                 callback_data="query_reacender_paixao"),
        ],
        [
            InlineKeyboardButton("🎁 Ideias de presentes?",
                                 callback_data="query_ideias_presentes"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def generate_tip_with_gemini(query_text: str, context_category: str = "") -> dict:
    """
    Usa a API do Google Gemini para gerar uma dica de relacionamento completa e extrair palavras-chave,
    sem depender de conteúdo web externo.
    Retorna um dicionário com 'tip_content' e 'keywords'.
    """
    # Verifica se a chave da API está configurada e não é o placeholder
    if not GEMINI_API_KEY or GEMINI_API_KEY == "SUA_NOVA_CHAVE_DE_API_DO_GEMINI_AQUI":
        logger.error(
            "GEMINI_API_KEY não configurada ou é um placeholder. Por favor, defina a variável de ambiente ou substitua no código.")
        return {
            "tip_content": "Desculpe, não consigo gerar dicas sem a chave da API do Gemini configurada.",
            "keywords": []
        }
    elif GEMINI_API_KEY == "AIzaSyDlF44isJ0yWwuBFxLXsUWYvWACQaZoWF8":
        # Loga se a chave antiga/inválida estiver a ser usada
        logger.error("ALERTA: A chave da API Gemini ainda é a chave de exemplo (AIzaSyDlF44isJ0yWwuBFxLXsUWYvWACQaZoWF8). Por favor, substitua-a pela sua chave válida: AIzaSyBF3sTUPEC3SM3UCY-xLrAsnWpzHQRFvQs")

    full_query = f"Com base na pergunta ou tema '{query_text}'"
    if context_category:
        full_query += f" da categoria '{context_category}'"

    # Instrução adicionada para tom informal e focado no dia a dia
    prompt = (
        f"{full_query}, gere uma dica de relacionamento completa e clara, com uma linguagem informal e encorajadora, "
        f"focada em conselhos práticos e úteis para situações do dia a dia. "
        f"A dica deve ser detalhada, mas concisa, e ter entre 150 e 400 palavras. "
        f"Ao final da dica, liste 3 a 5 palavras-chave ou tópicos principais relacionados a ela.\n\n"
        f"Formato da resposta:\n"
        f"Dica: [Sua dica completa e detalhada aqui]\n"
        f"Palavras-chave: [Palavra1, Palavra2, Palavra3]"
    )

    headers = {
        'Content-Type': 'application/json'
    }
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 800
        }
    }

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

    try:
        # Usar httpx para requisições assíncronas
        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url, headers=headers, json=payload, timeout=45
            )
            response.raise_for_status()  # Lança exceção para status HTTP 4xx/5xx

        gemini_result = response.json()

        if gemini_result and gemini_result.get('candidates'):
            raw_text = gemini_result['candidates'][0]['content']['parts'][0]['text']

            tip_content = "Não foi possível gerar a dica."
            keywords = []

            tip_match = re.search(
                r"Dica: (.*?)(?=\nPalavras-chave:|$)", raw_text, re.DOTALL)
            keywords_match = re.search(r"Palavras-chave: \[(.*?)\]", raw_text)

            if tip_match:
                tip_content = tip_match.group(1).strip()
            if keywords_match:
                keywords_str = keywords_match.group(1).strip()
                keywords = [k.strip()
                            for k in keywords_str.split(',') if k.strip()]

            return {"tip_content": tip_content, "keywords": keywords}

        logger.warning(f"Resposta inesperada da API Gemini: {gemini_result}")
        return {"tip_content": "Não foi possível gerar uma dica clara.", "keywords": []}

    except httpx.TimeoutException:
        logger.error("Tempo limite excedido ao chamar a API Gemini.")
        return {"tip_content": "Demorei muito para processar, tente novamente.", "keywords": []}
    except httpx.RequestError as e:  # Captura erros de requisição do httpx
        logger.error(f"Erro na requisição à API Gemini (httpx): {e}")
        # Tenta extrair o corpo da resposta para mais detalhes sobre o erro 400/500
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Corpo da resposta Gemini (Erro): {e.response.text}")
        return {"tip_content": "Erro ao comunicar com o serviço de IA.", "keywords": []}
    except (KeyError, IndexError) as e:
        logger.error(
            f"Erro ao parsear resposta da API Gemini: {e}\nRaw Response: {gemini_result}")
        return {"tip_content": "Erro ao interpretar a resposta da IA.", "keywords": []}
    except Exception as e:
        logger.error(
            f"Erro desconhecido na função generate_tip_with_gemini: {e}")
        return {"tip_content": "Ocorreu um erro interno ao gerar a dica.", "keywords": []}

# --- Handlers de Mensagens e Comandos ---


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia uma mensagem de boas-vindas com um teclado personalizado."""
    try:
        user = update.effective_user
        chat = update.effective_chat

        if not user or not chat:
            logger.error(
                "Não foi possível determinar o usuário ou chat efetivo na função start.")
            if update.callback_query:
                await update.callback_query.answer("Desculpe, não consegui iniciar a conversa.")
            return

        if update.callback_query:
            await update.callback_query.answer()

        welcome_message = (
            f"✨ Olá {user.first_name}! ✨\n\n"
            "Eu sou seu *Curador de Relacionamentos* 💖\n"
            "Vou te ajudar com:\n"
            "• 💝 Ideias românticas\n"
            "• 💑 Dicas para encontros\n"
            "• 🛟 Conselhos profissionais\n"
            "• 🎁 Surpresas especiais\n\n"
            "Escolha uma categoria ou digite sua pergunta sobre namoro para eu *gerar uma dica personalizada*!"
        )

        await chat.send_message(
            text=welcome_message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard()
        )
    except Exception as e:
        logger.error(f"Erro no comando start: {str(e)}", exc_info=True)
        await handle_error(update, context)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, custom_text: str = None):
    """
    Lida com mensagens de texto do usuário ou queries predefinidas de botões.
    Agora, gera a dica completa usando o LLM e a exibe em partes.
    """
    logger.info(
        f"Handler ativo: handle_message. user_data['quiz_state']: {'quiz_state' in context.user_data}")
    user_text = custom_text if custom_text else update.message.text
    chat_id_to_send = update.effective_chat.id if update.effective_chat else (
        update.callback_query.message.chat_id if update.callback_query else None)

    if not chat_id_to_send:
        logger.error("Nenhum chat_id encontrado para handle_message.")
        return

    try:
        await context.bot.send_chat_action(chat_id=chat_id_to_send, action="typing")

        logger.info(f"Gerando dica para a query: {user_text}")

        gemini_response = await generate_tip_with_gemini(user_text)

        full_tip_content = gemini_response.get(
            'tip_content', "Não foi possível gerar uma dica para isso.")
        keywords = gemini_response.get('keywords', [])

        # Dividir o conteúdo em parágrafos
        paragraphs = [p.strip()
                      for p in full_tip_content.split('\n\n') if p.strip()]

        display_tip = ""
        more_content_available = False

        if len(paragraphs) > 2:
            display_tip = "\n\n".join(paragraphs[:2])
            more_content_available = True
        else:
            display_tip = full_tip_content

        keywords_str = f"\n\n*Palavras-chave:* {', '.join(keywords)}" if keywords else ""

        initial_message = f"💖 *Dica sobre '{user_text}':*\n\n{display_tip}"
        if not more_content_available:  # Só adiciona palavras-chave na primeira parte se não houver mais conteúdo
            initial_message += keywords_str

        keyboard_buttons = []
        if more_content_available:
            # Gerar um ID único para o conteúdo completo da dica
            full_tip_id = hashlib.sha256(
                full_tip_content.encode('utf-8')).hexdigest()[:16]
            context.user_data[f"full_tip_{full_tip_id}"] = {
                "content": full_tip_content,
                "keywords": keywords,  # Guardar também as keywords para mostrar no final
                "title": f"Dica sobre {user_text}"
            }
            keyboard_buttons.append(InlineKeyboardButton(
                "Ler Mais 📖", callback_data=f"show_full_tip_{full_tip_id}"))

        keyboard_buttons.append(InlineKeyboardButton(
            "⭐ Favoritar", callback_data=f"fav_{hashlib.sha256(full_tip_content.encode('utf-8')).hexdigest()[:16]}"))
        keyboard_buttons.append(InlineKeyboardButton(
            "🔙 Menu Principal", callback_data="menu_main"))

        # Organiza os botões em linhas separadas para melhor visualização móvel
        keyboard_rows = [[btn] for btn in keyboard_buttons]
        reply_markup = InlineKeyboardMarkup(keyboard_rows)

        if update.callback_query:
            await update.callback_query.message.reply_text(
                text=initial_message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                text=initial_message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

    except Exception as e:
        logger.error(
            f"Erro no handle_message para a query '{user_text}': {str(e)}", exc_info=True)
        await handle_error(update, context)


async def show_full_tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe o conteúdo completo de uma dica."""
    query = update.callback_query
    await query.answer()

    full_tip_id = query.data.replace("show_full_tip_", "")
    full_tip_data = context.user_data.get(f"full_tip_{full_tip_id}")

    if not full_tip_data:
        await query.message.reply_text("Desculpe, não consegui encontrar o conteúdo completo desta dica.")
        return

    full_content = full_tip_data.get("content", "")
    keywords = full_tip_data.get("keywords", [])
    title = full_tip_data.get("title", "Dica Completa")

    keywords_str = f"\n\n*Palavras-chave:* {', '.join(keywords)}" if keywords else ""
    final_text_to_send = f"📖 *{title} - Completo:*\n\n{full_content}{keywords_str}"

    MAX_MESSAGE_LENGTH = 4096  # Limite de caracteres do Telegram

    # Se o texto completo for maior que o limite, divide-o
    if len(final_text_to_send) > MAX_MESSAGE_LENGTH:
        parts = []
        current_part = ""
        for line in final_text_to_send.split('\n'):
            if len(current_part) + len(line) + 1 > MAX_MESSAGE_LENGTH:  # +1 para o \n
                parts.append(current_part)
                current_part = line
            else:
                current_part += '\n' + line
        if current_part:
            parts.append(current_part)

        for i, part in enumerate(parts):
            await query.message.reply_text(
                text=part,
                parse_mode=ParseMode.MARKDOWN
            )
            # Adiciona um pequeno delay entre as partes para evitar flood
            await asyncio.sleep(0.5)
    else:
        await query.message.reply_text(
            text=final_text_to_send,
            parse_mode=ParseMode.MARKDOWN
        )

    # Remove o conteúdo completo do user_data para economizar memória após exibido
    if f"full_tip_{full_tip_id}" in context.user_data:
        del context.user_data[f"full_tip_{full_tip_id}"]

    # Oferece o menu principal novamente no final
    await query.message.reply_text(
        "Espero que esta dica tenha sido útil!",
        reply_markup=main_keyboard()
    )


async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lida com cliques em botões inline."""
    query = update.callback_query
    await query.answer()

    logger.info(f"Callback data recebido: {query.data}")

    try:
        if query.data.startswith("cat_"):
            category = query.data.split("_")[1]
            await send_category_tips(update, context, category)
        elif query.data == "menu_quiz":
            await start_quiz(update, context)
        elif query.data == "menu_events":
            await show_events(update, context)
        elif query.data == "menu_favs":
            await show_favorites(update, context)
        elif query.data == "menu_search":
            await query.edit_message_text(
                "🔍 *Digite sua pesquisa:*\nEx: 'como pedir em namoro', 'presentes para 6 meses'",
                parse_mode=ParseMode.MARKDOWN
            )
        elif query.data == "menu_main":
            await start(update, context)
        elif query.data.startswith("fav_"):
            fav_unique_id = query.data.split("_")[1]
            await add_favorite(update, context, fav_unique_id)
        elif query.data.startswith("remfav_"):
            fav_rem_id = query.data.split("_")[1]
            await remove_favorite(update, context, fav_rem_id)
        elif query.data == "cancel_quiz":
            await cancel_quiz(update, context)
        elif query.data.startswith("query_"):
            # Extrai o texto da query predefinida
            query_map = {
                "query_lidar_brigas": "Como lidar com brigas no relacionamento?",
                "query_reacender_paixao": "Como reacender a paixão no relacionamento?",
                "query_ideias_presentes": "Ideias criativas de presentes para meu parceiro(a)?"
            }
            custom_text = query_map.get(query.data)
            if custom_text:
                await query.message.reply_text(f"Gerando dica sobre '{custom_text.split('?')[0].strip()}'...")
                await handle_message(update, context, custom_text=custom_text)
            else:
                logger.warning(
                    f"Callback data de query predefinida desconhecida: {query.data}")
                await query.message.reply_text("Desculpe, não entendi essa opção. Tente novamente ou use o menu.")

    except Exception as e:
        logger.error(
            f"Erro no button_click para data '{query.data}': {str(e)}", exc_info=True)
        await handle_error(update, context)


async def send_category_tips(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    """
    Envia dicas baseadas na categoria selecionada, geradas diretamente pelo LLM, e as exibe em partes.
    """
    query = update.callback_query
    try:
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")

        themes = {
            "romance": "gestos românticos e carinho no relacionamento",
            "dates": "ideias criativas e memoráveis para encontros",
            "advice": "conselhos de especialistas para resolver conflitos e fortalecer a relação",
            "surprise": "ideias de surpresas únicas e especiais para o parceiro"
        }

        search_term = themes.get(category, f"dicas de namoro sobre {category}")
        logger.info(f"Gerando dica para categoria: {search_term}")

        gemini_response = await generate_tip_with_gemini(search_term, category)

        full_tip_content = gemini_response.get(
            'tip_content', "Não foi possível gerar uma dica para esta categoria.")
        keywords = gemini_response.get('keywords', [])

        # Dividir o conteúdo em parágrafos
        paragraphs = [p.strip()
                      for p in full_tip_content.split('\n\n') if p.strip()]

        display_tip = ""
        more_content_available = False

        if len(paragraphs) > 2:
            display_tip = "\n\n".join(paragraphs[:2])
            more_content_available = True
        else:
            display_tip = full_tip_content

        keywords_str = f"\n\n*Palavras-chave:* {', '.join(keywords)}" if keywords else ""

        initial_message = f"💡 *Dica sobre {category.title()}:*\n\n{display_tip}"
        if not more_content_available:  # Só adiciona palavras-chave na primeira parte se não houver mais conteúdo
            initial_message += keywords_str

        keyboard_buttons = []
        if more_content_available:
            full_tip_id = hashlib.sha256(
                full_tip_content.encode('utf-8')).hexdigest()[:16]
            context.user_data[f"full_tip_{full_tip_id}"] = {
                "content": full_tip_content,
                "keywords": keywords,
                "title": f"Dica de {category.title()}"
            }
            keyboard_buttons.append(InlineKeyboardButton(
                "Ler Mais 📖", callback_data=f"show_full_tip_{full_tip_id}"))

        keyboard_buttons.append(InlineKeyboardButton(
            "⭐ Favoritar", callback_data=f"fav_{hashlib.sha256(full_tip_content.encode('utf-8')).hexdigest()[:16]}"))
        keyboard_buttons.append(InlineKeyboardButton(
            "🔙 Voltar ao Menu", callback_data="menu_main"))

        # Organiza os botões em linhas separadas
        keyboard_rows = [[btn] for btn in keyboard_buttons]
        reply_markup = InlineKeyboardMarkup(keyboard_rows)

        await query.message.reply_text(
            text=initial_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        logger.error(
            f"Erro no send_category_tips para '{category}': {str(e)}", exc_info=True)
        await handle_error(update, context)


async def generate_quiz_questions_with_gemini() -> list:
    """
    Gera dinamicamente perguntas de quiz sobre relacionamento usando a Gemini API.
    Retorna uma lista de dicionários, cada um representando uma pergunta.
    Inclui um fallback se a geração falhar.
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY == "SUA_NOVA_CHAVE_DE_API_DO_GEMINI_AQUI" or GEMINI_API_KEY == "AIzaSyDlF44isJ0yWwuBFxLXsUWYvWACQaZoWF8":
        logger.error(
            "GEMINI_API_KEY não configurada corretamente para geração de quiz. Usando perguntas fallback.")
        # Fallback questions
        return [
            {
                "question_text": "Qual a base de um relacionamento?",
                "options": ["Presentes", "Comunicação", "Aparência"],
                "correct_option_index": 1
            },
            {
                "question_text": "Como resolver brigas de casal?",
                "options": ["Ignorar", "Gritar", "Conversar e ceder"],
                "correct_option_index": 2
            },
            {
                "question_text": "O que fortalece o amor?",
                "options": ["Distância", "Confiança", "Ciúme"],
                "correct_option_index": 1
            },
            {
                "question_text": "Melhor forma de mostrar carinho?",
                "options": ["Apenas palavras", "Pequenos gestos", "Grandes presentes"],
                "correct_option_index": 1
            },
            {
                "question_text": "Por que a paciência é importante?",
                "options": ["Para evitar brigar", "Para entender o outro", "Para não fazer nada"],
                "correct_option_index": 1
            },
        ]

    prompt = (
        f"Gere um quiz de {QuizManager.MAX_QUIZ_QUESTIONS} perguntas sobre relacionamentos. "
        f"As perguntas devem ser motivacionais, informais, e focar em situações vividas no dia a dia por casais. "
        f"Cada pergunta deve ter 3 opções de resposta e apenas 1 correta. "
        f"As opções de resposta devem ser curtas, cabendo em uma linha de botão no celular. "
        f"Retorne em formato JSON, como um array de objetos. "
        f"Cada objeto deve conter:\n"
        f"  - 'question_text': string (a pergunta)\n"
        f"  - 'options': array de 3 strings (as opções de resposta curtas)\n"
        f"  - 'correct_option_index': número inteiro (0, 1 ou 2, indicando o índice da resposta correta)\n"
        f"Exemplo de formato:\n"
        f"[\n"
        f"  {{\"question_text\": \"Como manter a chama acesa?\", \"options\": [\"Ficar na rotina\", \"Inovar e surpreender\", \"Reclamar\"], \"correct_option_index\": 1}},\n"
        f"  {{\"question_text\": \"O que fazer após uma briga?\", \"options\": [\"Ignorar\", \"Pedir desculpas\", \"Ter razão\"], \"correct_option_index\": 1}}\n"
        f"]"
    )

    headers = {
        'Content-Type': 'application/json'
    }
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.9,  # Um pouco mais de criatividade
            "maxOutputTokens": 1000,  # Aumentado para acomodar mais perguntas
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "question_text": {"type": "STRING"},
                        "options": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "minItems": 3,
                            "maxItems": 3
                        },
                        "correct_option_index": {"type": "INTEGER", "minimum": 0, "maximum": 2}
                    },
                    "required": ["question_text", "options", "correct_option_index"]
                }
            }
        }
    }

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url, headers=headers, json=payload, timeout=60  # Aumentado timeout
            )
            response.raise_for_status()

        gemini_result = response.json()

        if gemini_result and gemini_result.get('candidates'):
            raw_json_string = gemini_result['candidates'][0]['content']['parts'][0]['text']
            # O Gemini pode envolver o JSON em '```json\n...\n```', então precisamos extrair
            if raw_json_string.startswith('```json\n') and raw_json_string.endswith('\n```'):
                raw_json_string = raw_json_string[8:-4].strip()

            generated_questions = json.loads(raw_json_string)

            # Validação simples para garantir que recebemos uma lista de dicionários
            if isinstance(generated_questions, list) and all(isinstance(q, dict) and 'question_text' in q for q in generated_questions):
                logger.info(
                    f"Quiz gerado pela Gemini com {len(generated_questions)} perguntas.")
                # Embaralhar e pegar as MAX_QUIZ_QUESTIONS para garantir variedade e o limite
                random.shuffle(generated_questions)
                return generated_questions[:QuizManager.MAX_QUIZ_QUESTIONS]
            else:
                logger.error(
                    f"Formato de quiz inesperado da Gemini: {generated_questions}")
                # Usar fallback em caso de formato inválido
                return generate_quiz_questions_with_gemini._fallback_questions
        else:
            logger.warning(
                f"Nenhum candidato na resposta da Gemini ou resposta vazia: {gemini_result}")
            return generate_quiz_questions_with_gemini._fallback_questions  # Usar fallback

    except httpx.TimeoutException:
        logger.error(
            "Tempo limite excedido ao gerar quiz com a API Gemini. Usando perguntas fallback.")
        return generate_quiz_questions_with_gemini._fallback_questions
    except httpx.RequestError as e:
        logger.error(
            f"Erro na requisição à API Gemini para gerar quiz (httpx): {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(
                f"Corpo da resposta Gemini (Erro ao gerar quiz): {e.response.text}")
        return generate_quiz_questions_with_gemini._fallback_questions
    except json.JSONDecodeError as e:
        logger.error(
            f"Erro ao decodificar JSON da resposta da API Gemini para quiz: {e}\nRaw response: {raw_json_string}")
        return generate_quiz_questions_with_gemini._fallback_questions
    except Exception as e:
        logger.error(
            f"Erro desconhecido na função generate_quiz_questions_with_gemini: {e}")
        return generate_quiz_questions_with_gemini._fallback_questions

# Definindo perguntas de fallback diretamente na função para fácil acesso
generate_quiz_questions_with_gemini._fallback_questions = [
    {
        "question_text": "Qual a base de um relacionamento?",
        "options": ["Presentes", "Comunicação", "Aparência"],
        "correct_option_index": 1
    },
    {
        "question_text": "Como resolver brigas de casal?",
        "options": ["Ignorar", "Gritar", "Conversar e ceder"],
        "correct_option_index": 2
    },
    {
        "question_text": "O que fortalece o amor?",
        "options": ["Distância", "Confiança", "Ciúme"],
        "correct_option_index": 1
    },
    {
        "question_text": "Melhor forma de mostrar carinho?",
        "options": ["Apenas palavras", "Pequenos gestos", "Grandes presentes"],
        "correct_option_index": 1
    },
    {
        "question_text": "Por que a paciência é importante?",
        "options": ["Para evitar brigar", "Para entender o outro", "Para não fazer nada"],
        "correct_option_index": 1
    },
    {
        "question_text": "Como a gratidão ajuda no amor?",
        "options": ["Não ajuda", "Aumenta a valorização", "Causa dependência"],
        "correct_option_index": 1
    },
    {
        "question_text": "O que é 'tempo de qualidade'?",
        "options": ["Tempo juntos no sofá", "Momentos focados no outro", "Estar no mesmo cômodo"],
        "correct_option_index": 1
    },
    {
        "question_text": "Qual o impacto da honestidade?",
        "options": ["Pode machucar", "Confiabilidade e segurança", "Causa desconfiança"],
        "correct_option_index": 1
    },
    {
        "question_text": "Por que é bom elogiar?",
        "options": ["Pra ser puxa-saco", "Aumenta a autoestima", "Deixa a pessoa convencida"],
        "correct_option_index": 1
    },
    {
        "question_text": "Como evitar o tédio na relação?",
        "options": ["Fazer sempre o mesmo", "Inovar e explorar", "Culpar o parceiro"],
        "correct_option_index": 1
    }
]


async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia o quiz de conhecimento de relacionamento."""
    try:
        quiz_id = "conhecimento_relacionamento"

        # Gera perguntas dinamicamente usando a Gemini API
        quiz_questions_for_this_game = await generate_quiz_questions_with_gemini()

        if not quiz_questions_for_this_game:
            await update.callback_query.message.reply_text(
                "Desculpe, não consegui gerar as perguntas para o quiz agora. Tente novamente mais tarde.",
                reply_markup=main_keyboard()
            )
            await update.callback_query.answer("Não foi possível iniciar o quiz.")
            return

        context.user_data['quiz_state'] = {
            "quiz_id": quiz_id,
            "questions_set": quiz_questions_for_this_game,  # Armazena as perguntas geradas
            "current_question_idx": 0,
            "score": 0,
            "answered_questions_count": 0,
            "user_answers_indices": []  # Inicializa para guardar as respostas do usuário
        }

        await update.callback_query.answer()  # Responde à callback do botão "Quiz"

        await _send_quiz_question(update.callback_query.message.chat_id, context)

    except Exception as e:
        logger.error(f"Erro no start_quiz: {str(e)}", exc_info=True)
        await handle_error(update, context)


async def _send_quiz_question(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Função auxiliar para enviar uma pergunta do quiz."""
    quiz_state = context.user_data['quiz_state']
    quiz_questions = quiz_state['questions_set']
    current_question_idx = quiz_state['current_question_idx']

    if current_question_idx < len(quiz_questions):
        question_data = quiz_questions[current_question_idx]
        question_text = question_data["question_text"]
        options = question_data["options"]

        keyboard_options_rows = []  # Lista de listas para cada botão em sua própria linha
        for i, option in enumerate(options):
            # Formato do callback_data: quiz_ans_<indice_da_pergunta>_<indice_da_opcao>
            callback_data = f"quiz_ans_{current_question_idx}_{i}"
            keyboard_options_rows.append(
                [InlineKeyboardButton(option, callback_data=callback_data)])

        keyboard = keyboard_options_rows  # Agora cada opção está em sua própria linha
        keyboard.append([InlineKeyboardButton(
            "❌ Cancelar Quiz", callback_data="cancel_quiz")])

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🧩 *Quiz de Conhecimento* ({current_question_idx + 1}/{len(quiz_questions)}):\n\n"
            f"{question_text}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        # Fim do quiz
        total_score = quiz_state['score']
        quiz_title = QuizManager.QUIZZES[quiz_state['quiz_id']]["title"]
        max_possible_score = len(quiz_questions) * 2

        # Mensagem de resultado final, incluindo todas as perguntas e respostas
        result_message = f"✅ *Quiz de {quiz_title} Concluído!* ✅\n\n"
        result_message += f"Sua pontuação final: *{total_score} pontos* de {max_possible_score} possíveis.\n\n"
        result_message += "--- Detalhes das Suas Respostas ---\n"

        for idx, question_data in enumerate(quiz_questions):
            question_text = question_data["question_text"]
            correct_option_text = question_data["options"][question_data["correct_option_index"]]

            user_selected_option_index = quiz_state['user_answers_indices'][idx] if 'user_answers_indices' in quiz_state and idx < len(
                quiz_state['user_answers_indices']) else -1
            user_answer_text = question_data["options"][
                user_selected_option_index] if user_selected_option_index != -1 else "Não respondida"

            status = "✅ Correta" if user_selected_option_index == question_data[
                "correct_option_index"] else "❌ Incorreta"

            result_message += (
                f"\n*P{idx + 1}:* {question_text}\n"
                f"Sua resposta: _{user_answer_text}_ ({status})\n"
                f"Resposta correta: _{correct_option_text}_\n"
            )

        # Envia a mensagem de resultado final (pode ser dividida em várias mensagens se for muito longa)
        MAX_RESULT_MESSAGE_LENGTH = 4000
        if len(result_message) > MAX_RESULT_MESSAGE_LENGTH:
            parts = []
            current_part = ""
            # Divide por linhas, adicionando a cada parte até o limite
            for line in result_message.split('\n'):
                if len(current_part) + len(line) + 1 > MAX_RESULT_MESSAGE_LENGTH:
                    parts.append(current_part)
                    current_part = line
                else:
                    current_part += '\n' + line
            if current_part:  # Adiciona a última parte se houver
                parts.append(current_part)

            for part in parts:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=part,
                    parse_mode=ParseMode.MARKDOWN
                )
                await asyncio.sleep(0.5)  # Pequeno delay entre as partes
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=result_message,
                parse_mode=ParseMode.MARKDOWN
            )

        await context.bot.send_message(
            chat_id=chat_id,
            text="De volta ao menu principal.",
            reply_markup=main_keyboard()
        )
        del context.user_data['quiz_state']  # Limpa o estado do quiz


async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Processa a resposta do usuário a uma pergunta do quiz (via botão), sem feedback imediato.
    """
    logger.info(
        f"Handler ativo: handle_quiz_answer. user_data['quiz_state']: {'quiz_state' in context.user_data}")
    query = update.callback_query
    await query.answer()  # Responde à callback query para remover o "spinner" do botão

    quiz_state = context.user_data.get('quiz_state')
    if not quiz_state:
        await query.message.reply_text("Nenhum quiz ativo. Use /start e clique em 'Quiz'.", reply_markup=main_keyboard())
        return

    # Extrai o índice da pergunta e da opção selecionada
    # callback_data: quiz_ans_<indice_da_pergunta>_<indice_da_opcao>
    parts = query.data.split('_')

    if len(parts) != 4 or parts[0] != "quiz" or parts[1] != "ans":
        logger.error(f"Callback data inesperado para quiz: {query.data}")
        await query.message.reply_text("Erro ao processar sua resposta do quiz. Por favor, tente novamente.", reply_markup=main_keyboard())
        if 'quiz_state' in context.user_data:
            del context.user_data['quiz_state']
        return

    question_idx_from_callback = int(parts[2])
    selected_option_index = int(parts[3])

    quiz_questions = quiz_state['questions_set']
    current_question_idx_in_state = quiz_state['current_question_idx']

    # Valida que a resposta é para a pergunta atual no estado
    if question_idx_from_callback != current_question_idx_in_state:
        logger.warning(
            f"Resposta para pergunta antiga ou fora de ordem. Esperava {current_question_idx_in_state}, recebeu {question_idx_from_callback}")
        # Apenas ignora respostas fora de ordem, sem enviar mensagem ao usuário
        return

    question_data = quiz_questions[current_question_idx_in_state]
    correct_option_index = question_data["correct_option_index"]

    # Guarda a resposta do usuário para exibição no final
    if 'user_answers_indices' not in quiz_state:
        quiz_state['user_answers_indices'] = []
    # Preenche a lista com as respostas na ordem das perguntas
    while len(quiz_state['user_answers_indices']) <= current_question_idx_in_state:
        # Preenche com None para respostas não dadas
        quiz_state['user_answers_indices'].append(None)
    quiz_state['user_answers_indices'][current_question_idx_in_state] = selected_option_index

    # Verifica a resposta e atualiza a pontuação (sem feedback imediato ao usuário)
    if selected_option_index == correct_option_index:
        quiz_state['score'] += 2
        logger.info(
            f"Resposta CORRETA! Pontuação atual: {quiz_state['score']}")
    else:
        logger.info(
            f"Resposta INCORRETA! Pontuação atual: {quiz_state['score']}")

    # Incrementa para a próxima pergunta
    quiz_state['answered_questions_count'] += 1
    quiz_state['current_question_idx'] += 1

    # Remove a mensagem da pergunta anterior para manter o chat limpo
    try:
        await query.message.delete()
    except Exception as e:
        logger.warning(
            f"Não foi possível apagar a mensagem da pergunta anterior: {e}")

    # Envia a próxima pergunta ou finaliza o quiz
    await _send_quiz_question(query.message.chat_id, context)


async def cancel_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela o quiz atual."""
    query = update.callback_query
    await query.answer("Quiz cancelado.")
    if 'quiz_state' in context.user_data:
        del context.user_data['quiz_state']
    await query.edit_message_text(
        "Quiz cancelado. De volta ao menu principal.",
        reply_markup=main_keyboard()
    )


async def show_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra eventos especiais."""
    try:
        events_list = []
        today = datetime.now().strftime("%d/%m")

        for date, info in SpecialEvents.DATES.items():
            if date == today:
                events_list.append(f"🎉 *HOJE:* {info['message']}")
            else:
                events_list.append(f"📅 {date}: {info['message']}")

        MAX_MESSAGE_LENGTH = 1000
        event_message_body = "📅 *Próximos Eventos Especiais*\n\n" + \
            "\n".join(events_list)

        # Garante que final_response sempre é atribuída
        if len(event_message_body) > MAX_MESSAGE_LENGTH:
            final_response = event_message_body[:
                                                MAX_MESSAGE_LENGTH - 3] + "..."
        else:
            final_response = event_message_body

        await update.callback_query.message.reply_text(
            text=final_response,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Voltar ao Menu", callback_data="menu_main")]])
        )
    except Exception as e:
        logger.error(f"Erro no show_events: {str(e)}", exc_info=True)
        await handle_error(update, context)


async def add_favorite(update: Update, context: ContextTypes.DEFAULT_TYPE, fav_unique_id: str):
    """Adiciona uma dica aos favoritos do usuário."""
    try:
        user_id = str(update.callback_query.from_user.id)
        favorites = load_data("favoritos.json")
        if user_id not in favorites:
            favorites[user_id] = {}

        tip_to_favorite = context.user_data.get(f"temp_fav_{fav_unique_id}")

        if not tip_to_favorite:
            await update.callback_query.answer("Não foi possível favoritar. Dica não encontrada. Tente gerar novamente.")
            return

        internal_tip_id = tip_to_favorite.get(
            'url', f"gerado_sem_id_{fav_unique_id}")

        if internal_tip_id in favorites[user_id]:
            await update.callback_query.answer("Esta dica já está nos seus favoritos!")
        else:
            favorites[user_id][internal_tip_id] = {
                "titulo": tip_to_favorite.get('titulo', 'Dica Gerada'),
                "resumo": tip_to_favorite.get('resumo', 'Sem resumo disponível'),
                "keywords": tip_to_favorite.get('keywords', []),
                "data_favoritado": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            save_data("favoritos.json", favorites)
            await update.callback_query.answer("Dica adicionada aos favoritos! ⭐")
    except Exception as e:
        logger.error(f"Erro ao adicionar favorito: {str(e)}", exc_info=True)
        await handle_error(update, context)


async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra as dicas favoritadas pelo usuário."""
    try:
        favorites = load_data("favoritos.json")
        user_id = str(update.callback_query.from_user.id)

        if user_id not in favorites or not favorites[user_id]:
            await update.callback_query.message.reply_text(
                "📭 Você ainda não tem dicas favoritadas!",
                reply_markup=main_keyboard()
            )
            return

        response_lines = ["⭐ *Seus Favoritos:*\n"]
        keyboard_favs = []

        for key in list(context.user_data.keys()):
            if key.startswith("temp_remfav_") or key.startswith("temp_fav_") or key.startswith('temp_results_for_fav'):
                del context.user_data[key]

        for idx, (internal_id, tip_data) in enumerate(favorites[user_id].items(), 1):
            summary_display = tip_data.get('resumo', 'Sem resumo disponível.').split('\n')[
                0][:100] + "..."
            response_lines.append(
                f"{idx}. *{tip_data.get('titulo', 'Dica Favorita')}*\n_{summary_display}_")

            fav_rem_id = hashlib.sha256(
                internal_id.encode('utf-8')).hexdigest()[:16]
            keyboard_favs.append([InlineKeyboardButton(
                f"🗑️ Remover {idx}", callback_data=f"remfav_{fav_rem_id}")])
            context.user_data[f"temp_remfav_{fav_rem_id}"] = internal_id

        keyboard_favs.append([InlineKeyboardButton(
            "🔙 Voltar ao Menu", callback_data="menu_main")])

        MAX_MESSAGE_LENGTH = 1000
        final_response = "\n".join(response_lines)

        if len(final_response) > MAX_MESSAGE_LENGTH:
            final_response = final_response[:MAX_MESSAGE_LENGTH - 3] + "..."

        await update.callback_query.message.reply_text(
            final_response,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard_favs)
        )
    except Exception as e:
        logger.error(f"Erro no show_favorites: {str(e)}", exc_info=True)
        await handle_error(update, context)


async def remove_favorite(update: Update, context: ContextTypes.DEFAULT_TYPE, fav_rem_id: str):
    """Remove uma dica dos favoritos do usuário."""
    try:
        user_id = str(update.callback_query.from_user.id)
        favorites = load_data("favoritos.json")

        if user_id not in favorites:
            await update.callback_query.answer("Você não tem favoritos para remover.")
            return

        internal_id_to_remove = context.user_data.get(
            f"temp_remfav_{fav_rem_id}")
        if not internal_id_to_remove:
            await update.callback_query.answer("Não foi possível encontrar a dica para remover.")
            return

        if internal_id_to_remove in favorites[user_id]:
            del favorites[user_id][internal_id_to_remove]
            save_data("favoritos.json", favorites)
            await update.callback_query.answer("Dica removida dos favoritos! 🗑️")
            # Atualiza a lista de favoritos após a remoção
            await show_favorites(update, context)
        else:
            await update.callback_query.answer("Esta dica não está nos seus favoritos.")
    except Exception as e:
        logger.error(f"Erro ao remover favorito: {str(e)}", exc_info=True)
        await handle_error(update, context)


async def share_tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Permite compartilhar dicas. Esta função ainda é um placeholder.
    """
    try:
        await update.message.reply_text(
            "Use /compartilhar <id_dica> para compartilhar dicas com outros usuários! "
            "A funcionalidade de salvar dicas para compartilhar será implementada em breve.",
            reply_markup=main_keyboard()
        )
    except Exception as e:
        logger.error(f"Erro no share_tip: {str(e)}", exc_info=True)
        await handle_error(update, context)

# --- Configuração Final do Bot ---
if __name__ == "__main__":
    try:
        app = Application.builder().token(TOKEN).build()

        # Handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("compartilhar", share_tip))
        # Handler para as respostas do quiz
        app.add_handler(CallbackQueryHandler(
            handle_quiz_answer, pattern=r'^quiz_ans_.*$'))
        # Handler para mostrar o conteúdo completo da dica
        app.add_handler(CallbackQueryHandler(
            show_full_tip, pattern=r'^show_full_tip_.*$'))
        # Mantido no final para capturar outros callbacks que não sejam específicos de quiz ou full_tip
        app.add_handler(CallbackQueryHandler(button_click))

        # Handler para mensagens de texto, mas apenas quando o quiz NÃO está ativo
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & quiz_state_inactive,
            handle_message
        ))

        app.add_error_handler(handle_error)

        logger.info("Bot de Relacionamentos Premium iniciado")
        app.run_polling()
    except Exception as e:
        logger.critical(f"Falha ao iniciar o bot: {str(e)}", exc_info=True)
        print(f"Erro crítico: {str(e)}")
