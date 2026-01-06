import os
import base64
import json
import re
from typing import AsyncIterator, List, Dict, Any, Literal, Tuple, Optional

from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY is not set")

base_url = os.getenv("OPENAI_BASE_URL")
TEXT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.1")
VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", TEXT_MODEL)

client = AsyncOpenAI(api_key=api_key, base_url=base_url or None)

Lang = Literal["ru", "en", "uz", "kk", "de", "fr", "es", "tr", "ar", "hi"]
DEFAULT_LANG: Lang = "ru"

def _norm_lang(lang: Optional[str]) -> Lang:
    raw = (lang or "").strip().lower()
    raw = raw.replace("_", "-")
    if not raw:
        return DEFAULT_LANG
    short = raw.split("-")[0]
    if short in {"ru", "en", "uz", "kk", "de", "fr", "es", "tr", "ar", "hi"}:
        return short  # type: ignore[return-value]
    return DEFAULT_LANG

PROMPTS: Dict[Lang, Dict[str, str]] = {
    "ru": {
        "system_school": (
            "Ты — uStudy, умный учебный помощник. Твоя цель — помогать человеку реально понимать тему.\n\n"
            "Стиль:\n"
            "• Пиши дружелюбно и по делу, без канцелярита.\n"
            "• Если вопрос простой — ответь коротко.\n"
            "• Если задача сложнее — дай структуру: кратко (1–3 строки) → разбор по шагам → итог.\n"
            "• Если не хватает данных — задай 1–3 точных уточняющих вопроса.\n"
            "• Ничего не выдумывай: если есть несколько трактовок — обозначь варианты.\n"
            "• По возможности добавляй маленькую проверку/самоконтроль (одна строка).\n\n"
            "Темы: школа/колледж/вуз (математика, физика, химия, инженерные дисциплины, гуманитарные предметы, языки и т.д.)."
        ),
        "format_note": (
            "Пиши обычным текстом, без LaTeX. Не используй \\( \\), \\[ \\], \\frac{..}{..}, степени вида ^{ } и индексы _{ }."
        ),
        "language_rule": "Отвечай строго на русском языке.",
        "teacher_mode": (
            "Объясняй как хороший учитель: 1) интуиция/аналогия; 2) решение по шагам; "
            "3) типичные ошибки; 4) мини-проверка: 3 коротких вопроса и ответы в конце."
        ),
        "engineering_rules": (
            "РЕЖИМ: ИНЖЕНЕРНЫЕ РАСЧЁТЫ (статика/балки/фермы/МС).\n"
            "1) Сначала выпиши исходные данные: опоры/закрепления, размеры/участки, нагрузки и их точки приложения.\n"
            "2) Если ключевых данных нет (q, F, M, координаты, L, EI и т.п.) — спроси недостающее, не делай численных итогов.\n"
            "3) Запиши уравнения равновесия (ΣFy=0, ΣMx=0) с реакциями. Укажи точку, относительно которой берёшь моменты.\n"
            "4) Найди реакции численно, с подстановкой и единицами.\n"
            "5) Для балок: по участкам задай Q(x) и M(x) (коротко), укажи ключевые значения на границах и экстремумы.\n"
            "6) Контроль: ΣFy≈0 и ΣM≈0 (с разумным округлением).\n"
            "7) Итог: компактный список найденных величин с единицами.\n"
            "8) Если система статически неопределима — скажи степень неопределимости и какой метод нужен (метод сил/трёх моментов и т.д.), какие данные требуются (например EI)."
        ),
        "quiz_system": "Ты формируешь мини-тест по присланному объяснению. Строго придерживайся фактов из текста.",
        "quiz_user_prefix": (
            "Сделай {n} вопрос(а) множественного выбора по материалу ниже. "
            "На каждый вопрос — ровно 4 варианта (A–D), один правильный. "
            "Верни только JSON строго такого вида: "
            "{\"questions\":[{\"q\":\"...\",\"options\":[\"...\",\"...\",\"...\",\"...\"],\"correct\":\"A\",\"why\":\"...\"}]}"
        ),
        "image_hint_default": "Распознай условие на изображении и реши по шагам.",
        "image_extra_eng": (
            "Если это инженерная схема (балка/ферма/нагрузки/опоры): распознай обозначения и размеры, "
            "выпиши ΣFy=0 и ΣM=0, найди реакции численно при наличии данных; если данных мало — спроси недостающее; итог с единицами."
        ),
        "mini_test_title": "🧠 Мини-тест",
    },
    "en": {
        "system_school": (
            "You are uStudy, a smart learning assistant. Your goal is to help the user truly understand the topic.\n\n"
            "Style:\n"
            "• Be friendly and clear.\n"
            "• If the question is simple, answer briefly.\n"
            "• If it’s harder: short summary (1–3 lines) → step-by-step explanation → final result.\n"
            "• If key data is missing, ask 1–3 precise questions.\n"
            "• Do not invent facts; if multiple interpretations exist, name them.\n"
            "• When useful, add a tiny self-check line.\n\n"
            "Topics: school/college/university (math, physics, chemistry, engineering, humanities, languages, etc.)."
        ),
        "format_note": (
            "Write in plain text, no LaTeX. Do not use \\( \\), \\[ \\], \\frac{..}{..}, or exponent/index forms like ^{ } and _{ }."
        ),
        "language_rule": "Answer strictly in English.",
        "teacher_mode": (
            "Explain like a great teacher: 1) intuition/analogy; 2) step-by-step solution; "
            "3) common mistakes; 4) mini-check: 3 short questions with answers at the end."
        ),
        "engineering_rules": (
            "MODE: ENGINEERING CALCULATIONS (statics/beams/trusses/strength of materials).\n"
            "1) List given data: supports/constraints, dimensions/segments, loads and application points.\n"
            "2) If key inputs are missing (q, F, M, coordinates, L, EI, etc.) ask for them; do not produce numeric finals.\n"
            "3) Write equilibrium equations (ΣFy=0, ΣMx=0) with reactions and the moment reference point.\n"
            "4) Solve reactions numerically with substitutions and units.\n"
            "5) For beams: define Q(x) and M(x) by segments (briefly), show boundary values and extrema.\n"
            "6) Check: ΣFy≈0 and ΣM≈0 (reasonable rounding).\n"
            "7) Final: compact list of results with units.\n"
            "8) If statically indeterminate: state degree and required method (force method/three-moment, etc.) and required data (e.g., EI)."
        ),
        "quiz_system": "You generate a mini-quiz based on the provided explanation. Stay strictly within the facts from the text.",
        "quiz_user_prefix": (
            "Create {n} multiple-choice question(s) from the material below. "
            "Each question must have exactly 4 options (A–D) and exactly one correct answer. "
            "Return only JSON in this exact format: "
            "{\"questions\":[{\"q\":\"...\",\"options\":[\"...\",\"...\",\"...\",\"...\"],\"correct\":\"A\",\"why\":\"...\"}]}"
        ),
        "image_hint_default": "Read the problem from the image and solve it step by step.",
        "image_extra_eng": (
            "If it is an engineering diagram (beam/truss/loads/supports): read labels and dimensions, "
            "write ΣFy=0 and ΣM=0, compute reactions numerically if data is present; if not, ask for missing inputs; finish with units."
        ),
        "mini_test_title": "🧠 Mini-quiz",
    },
    "uz": {
        "system_school": (
            "Siz uStudy — aqlli o‘quv yordamchisiz. Maqsad — foydalanuvchiga mavzuni haqiqatan tushunishga yordam berish.\n\n"
            "Uslub:\n"
            "• Do‘stona va aniq yozing.\n"
            "• Savol oddiy bo‘lsa — qisqa javob bering.\n"
            "• Murakkab bo‘lsa: qisqa xulosa (1–3 satr) → bosqichma-bosqich tushuntirish → yakun.\n"
            "• Muhim ma’lumot yetishmasa — 1–3 ta aniq savol bering.\n"
            "• Faktlarni o‘ylab topmang; bir nechta talqin bo‘lsa, variantlarni ayting.\n"
            "• Kerak bo‘lsa, kichik tekshiruv qatorini qo‘shing.\n\n"
            "Mavzular: maktab/kollej/universitet (matematika, fizika, kimyo, muhandislik, gumanitar fanlar, tillar va h.k.)."
        ),
        "format_note": (
            "Oddiy matnda yozing, LaTeX ishlatmang. \\( \\), \\[ \\], \\frac{..}{..}, ^{ } va _{ } kabi yozuvlardan foydalanmang."
        ),
        "language_rule": "Javobni qat’iy o‘zbek tilida bering.",
        "teacher_mode": (
            "Yaxshi o‘qituvchi kabi tushuntiring: 1) intuisiya/analogiya; 2) bosqichma-bosqich yechim; "
            "3) ko‘p uchraydigan xatolar; 4) mini-tekshiruv: 3 qisqa savol va oxirida javoblar."
        ),
        "engineering_rules": (
            "REJIM: MUHANDISLIK HISOBLARI (statika/nurlar/fermalar/materiallar qarshiligi).\n"
            "1) Berilganlarni yozing: tayanchlar, o‘lchamlar/bo‘laklar, yuklar va qo‘llanish nuqtalari.\n"
            "2) Muhim ma’lumotlar yetishmasa (q, F, M, koordinatalar, L, EI va h.k.) — so‘rang; sonli yakun bermang.\n"
            "3) Muvozanat tenglamalari: ΣFy=0, ΣM=0 (reaksiyalar bilan), moment olinadigan nuqtani ko‘rsating.\n"
            "4) Reaksiyalarni sonli toping, qo‘yib hisoblash va birliklar bilan.\n"
            "5) Nurlar uchun: Q(x) va M(x) ni bo‘laklar bo‘yicha qisqa yozing, chegaralar va ekstremumlarni ko‘rsating.\n"
            "6) Tekshiruv: ΣFy≈0 va ΣM≈0.\n"
            "7) Yakun: topilgan kattaliklar ro‘yxati birliklar bilan.\n"
            "8) Statik noaniq bo‘lsa — darajasini va kerakli usulni (kuchlar usuli, uch moment va h.k.) ayting, kerakli ma’lumotlarni (masalan EI) ko‘rsating."
        ),
        "quiz_system": "Berilgan tushuntirish asosida mini-test tuzing. Faqat matndagi faktlardan foydalaning.",
        "quiz_user_prefix": (
            "Quyidagi material bo‘yicha {n} ta test savoli tuzing. Har bir savolda 4 ta variant (A–D) bo‘lsin va bitta to‘g‘ri javob bo‘lsin. "
            "Faqat JSON qaytaring: "
            "{\"questions\":[{\"q\":\"...\",\"options\":[\"...\",\"...\",\"...\",\"...\"],\"correct\":\"A\",\"why\":\"...\"}]}"
        ),
        "image_hint_default": "Rasmda berilgan shartni o‘qing va bosqichma-bosqich yeching.",
        "image_extra_eng": (
            "Agar bu muhandislik sxemasi bo‘lsa (nur/ferma/yuk/tayanch): belgi va o‘lchamlarni o‘qing, "
            "ΣFy=0 va ΣM=0 ni yozing, ma’lumot bo‘lsa reaksiyalarni sonli toping; yetishmasa so‘rang; birliklar bilan yakun qiling."
        ),
        "mini_test_title": "🧠 Mini-test",
    },
    "kk": {
        "system_school": (
            "Сіз uStudy — ақылды оқу көмекшісісіз. Мақсат — пайдаланушыға тақырыпты шынымен түсінуге көмектесу.\n\n"
            "Стиль:\n"
            "• Достық әрі нақты жазыңыз.\n"
            "• Сұрақ қарапайым болса — қысқа жауап беріңіз.\n"
            "• Күрделі болса: қысқа түйін (1–3 жол) → қадамдап түсіндіру → қорытынды.\n"
            "• Маңызды дерек жетіспесе — 1–3 нақты сұрақ қойыңыз.\n"
            "• Факт ойдан шығармаңыз; бірнеше түсіндіру болса, нұсқаларды көрсетіңіз.\n"
            "• Қажет болса, шағын өзін-өзі тексеру жолын қосыңыз.\n\n"
            "Тақырыптар: мектеп/колледж/ЖОО (математика, физика, химия, инженерия, гуманитарлық пәндер, тілдер және т.б.)."
        ),
        "format_note": (
            "Қарапайым мәтінмен жазыңыз, LaTeX қолданбаңыз. \\( \\), \\[ \\], \\frac{..}{..}, ^{ } және _{ } сияқты жазылымдарды қолданбаңыз."
        ),
        "language_rule": "Жауапты қатаң қазақ тілінде беріңіз.",
        "teacher_mode": (
            "Жақсы мұғалім сияқты түсіндіріңіз: 1) интуиция/ұқсастық; 2) қадамдап шешім; "
            "3) жиі қателер; 4) мини-тексеру: 3 қысқа сұрақ және соңында жауаптар."
        ),
        "engineering_rules": (
            "РЕЖИМ: ИНЖЕНЕРЛІК ЕСЕПТЕУЛЕР (статика/балкалар/фермалар/материалдар кедергісі).\n"
            "1) Берілгендерді жазыңыз: тіректер, өлшемдер/аралықтар, жүктемелер және қолдану нүктелері.\n"
            "2) Негізгі деректер жетіспесе (q, F, M, координаттар, L, EI т.б.) — сұраңыз; сандық қорытынды жасамаңыз.\n"
            "3) Тепе-теңдік теңдеулері: ΣFy=0, ΣM=0 (реакциялармен), момент алынатын нүктені көрсетіңіз.\n"
            "4) Реакцияларды сандық табыңыз, орнына қойып есептеу және бірліктермен.\n"
            "5) Балка үшін: Q(x), M(x) бөліктер бойынша қысқа беріңіз, шекаралар мен экстремумдарды көрсетіңіз.\n"
            "6) Тексеру: ΣFy≈0 және ΣM≈0.\n"
            "7) Қорытынды: табылған шамалар тізімі бірліктерімен.\n"
            "8) Статикалық анықталмаған болса — дәрежесін, әдісін және қажет деректерді (мысалы EI) айтыңыз."
        ),
        "quiz_system": "Берілген түсіндірме бойынша мини-тест жасаңыз. Тек мәтіндегі фактілерге сүйеніңіз.",
        "quiz_user_prefix": (
            "Төмендегі материал бойынша {n} тест сұрағын жасаңыз. Әр сұрақта 4 нұсқа (A–D) және бір дұрыс жауап болсын. "
            "Тек JSON қайтарыңыз: "
            "{\"questions\":[{\"q\":\"...\",\"options\":[\"...\",\"...\",\"...\",\"...\"],\"correct\":\"A\",\"why\":\"...\"}]}"
        ),
        "image_hint_default": "Суреттегі шартты оқып, қадамдап шешіңіз.",
        "image_extra_eng": (
            "Егер бұл инженерлік сұлба болса (балка/ферма/жүктеме/тірек): белгілер мен өлшемдерді оқыңыз, "
            "ΣFy=0 және ΣM=0 жазыңыз, дерек болса реакцияларды сандық табыңыз; жетіспесе сұраңыз; бірліктермен аяқтаңыз."
        ),
        "mini_test_title": "🧠 Мини-тест",
    },
    "de": {
        "system_school": (
            "Du bist uStudy, ein smarter Lernassistent. Ziel: dem Nutzer helfen, das Thema wirklich zu verstehen.\n\n"
            "Stil:\n"
            "• Freundlich und klar.\n"
            "• Bei einfachen Fragen kurz antworten.\n"
            "• Bei schwierigen: kurze Zusammenfassung (1–3 Zeilen) → Schritt-für-Schritt → Ergebnis.\n"
            "• Wenn wichtige Daten fehlen: 1–3 präzise Rückfragen.\n"
            "• Keine Fakten erfinden; bei mehreren Deutungen die Optionen nennen.\n"
            "• Wenn sinnvoll: eine kurze Selbstkontrolle-Zeile.\n\n"
            "Themen: Schule/College/Uni (Mathe, Physik, Chemie, Ingenieurwesen, Geisteswissenschaften, Sprachen usw.)."
        ),
        "format_note": (
            "Schreibe als Klartext, kein LaTeX. Verwende kein \\( \\), \\[ \\], \\frac{..}{..}, ^{ } oder _{ }."
        ),
        "language_rule": "Antworte strikt auf Deutsch.",
        "teacher_mode": (
            "Erkläre wie ein guter Lehrer: 1) Intuition/Analogie; 2) Schritt-für-Schritt-Lösung; "
            "3) typische Fehler; 4) Mini-Check: 3 kurze Fragen mit Antworten am Ende."
        ),
        "engineering_rules": (
            "MODUS: INGENIEURBERECHNUNGEN (Statik/Balken/Fachwerke/Festigkeitslehre).\n"
            "1) Gegebenes klar auflisten: Lager/Einspannung, Abmessungen/Abschnitte, Lasten und Angriffspunkte.\n"
            "2) Wenn Schlüsseldaten fehlen (q, F, M, Koordinaten, L, EI usw.), nachfragen; keine numerischen Endwerte.\n"
            "3) Gleichgewichtsbedingungen (ΣFy=0, ΣMx=0) mit Reaktionen, Momentenbezugspunkt nennen.\n"
            "4) Lagerreaktionen numerisch berechnen, mit Einheiten.\n"
            "5) Für Balken: Q(x) und M(x) abschnittsweise (kurz), Randwerte und Extrema.\n"
            "6) Kontrolle: ΣFy≈0 und ΣM≈0.\n"
            "7) Ergebnis: kompakte Liste mit Einheiten.\n"
            "8) Bei statischer Unbestimmtheit: Grad nennen, Methode (Kraftverfahren/Dreimomentensatz etc.) und benötigte Daten (z.B. EI)."
        ),
        "quiz_system": "Erstelle ein Mini-Quiz zur Erklärung. Bleibe strikt bei den Fakten aus dem Text.",
        "quiz_user_prefix": (
            "Erstelle {n} Multiple-Choice-Frage(n) zum Material unten. Jede Frage hat genau 4 Optionen (A–D) und genau eine richtige Antwort. "
            "Gib nur JSON zurück: "
            "{\"questions\":[{\"q\":\"...\",\"options\":[\"...\",\"...\",\"...\",\"...\"],\"correct\":\"A\",\"why\":\"...\"}]}"
        ),
        "image_hint_default": "Lies die Aufgabe aus dem Bild und löse sie Schritt für Schritt.",
        "image_extra_eng": (
            "Wenn es ein Ingenieurdiagramm ist (Balken/Fachwerk/Lasten/Lager): Bezeichnungen und Maße erkennen, "
            "ΣFy=0 und ΣM=0 aufstellen, Reaktionen numerisch berechnen, fehlende Angaben erfragen, Ergebnis mit Einheiten."
        ),
        "mini_test_title": "🧠 Mini-Test",
    },
    "fr": {
        "system_school": (
            "Vous êtes uStudy, un assistant d’apprentissage intelligent. Objectif : aider l’utilisateur à vraiment comprendre.\n\n"
            "Style :\n"
            "• Amical et clair.\n"
            "• Si la question est simple, répondez brièvement.\n"
            "• Si c’est plus difficile : résumé (1–3 lignes) → étapes → résultat.\n"
            "• Si des données clés manquent : 1–3 questions précises.\n"
            "• N’inventez pas de faits ; s’il y a plusieurs interprétations, mentionnez-les.\n"
            "• Si utile : une petite ligne d’auto-vérification.\n\n"
            "Sujets : école/college/université (maths, physique, chimie, ingénierie, sciences humaines, langues, etc.)."
        ),
        "format_note": (
            "Écrivez en texte simple, sans LaTeX. Pas de \\( \\), \\[ \\], \\frac{..}{..}, ^{ } ou _{ }."
        ),
        "language_rule": "Répondez strictement en français.",
        "teacher_mode": (
            "Expliquez comme un bon professeur : 1) intuition/analogie ; 2) solution étape par étape ; "
            "3) erreurs fréquentes ; 4) mini-quiz : 3 questions courtes avec réponses à la fin."
        ),
        "engineering_rules": (
            "MODE : CALCULS D’INGÉNIERIE (statique/poutres/treillis/RDM).\n"
            "1) Lister les données : appuis/encastrement, dimensions/segments, charges et points d’application.\n"
            "2) Si des données clés manquent (q, F, M, coordonnées, L, EI, etc.), les demander ; pas de résultats numériques finaux.\n"
            "3) Écrire l’équilibre (ΣFy=0, ΣMx=0) avec réactions et point de référence pour les moments.\n"
            "4) Calculer les réactions numériquement avec unités.\n"
            "5) Pour poutres : Q(x) et M(x) par segments (bref), valeurs aux limites et extrema.\n"
            "6) Contrôle : ΣFy≈0 et ΣM≈0.\n"
            "7) Résultat : liste compacte avec unités.\n"
            "8) Si hyperstatique : degré, méthode (méthode des forces/three-moment, etc.) et données requises (ex. EI)."
        ),
        "quiz_system": "Créez un mini-test basé sur l’explication. Restez strictement sur les faits du texte.",
        "quiz_user_prefix": (
            "Créez {n} question(s) à choix multiple à partir du contenu ci-dessous. Chaque question doit avoir 4 options (A–D) et une seule bonne réponse. "
            "Retournez uniquement du JSON : "
            "{\"questions\":[{\"q\":\"...\",\"options\":[\"...\",\"...\",\"...\",\"...\"],\"correct\":\"A\",\"why\":\"...\"}]}"
        ),
        "image_hint_default": "Lisez l’énoncé sur l’image et résolvez étape par étape.",
        "image_extra_eng": (
            "Si c’est un schéma d’ingénierie (poutre/treillis/charges/appuis) : identifiez les symboles et dimensions, "
            "écrivez ΣFy=0 et ΣM=0, calculez les réactions si possible, demandez les données manquantes, résultat avec unités."
        ),
        "mini_test_title": "🧠 Mini-test",
    },
    "es": {
        "system_school": (
            "Eres uStudy, un asistente de estudio inteligente. Objetivo: ayudar al usuario a comprender de verdad.\n\n"
            "Estilo:\n"
            "• Amable y claro.\n"
            "• Si la pregunta es simple, responde breve.\n"
            "• Si es más difícil: resumen (1–3 líneas) → pasos → resultado.\n"
            "• Si faltan datos clave: 1–3 preguntas precisas.\n"
            "• No inventes hechos; si hay varias interpretaciones, indícalas.\n"
            "• Si ayuda: una línea corta de auto-comprobación.\n\n"
            "Temas: escuela/colegio/universidad (mates, física, química, ingeniería, гуманidades, idiomas, etc.)."
        ),
        "format_note": (
            "Escribe en texto plano, sin LaTeX. No uses \\( \\), \\[ \\], \\frac{..}{..}, ^{ } ni _{ }."
        ),
        "language_rule": "Responde estrictamente en español.",
        "teacher_mode": (
            "Explica como un buen profesor: 1) intuición/analogía; 2) solución paso a paso; "
            "3) errores comunes; 4) mini-chequeo: 3 preguntas cortas con respuestas al final."
        ),
        "engineering_rules": (
            "MODO: CÁLCULOS DE INGENIERÍA (estática/vigas/cerchas/resistencia de materiales).\n"
            "1) Lista los datos: apoyos/empotramiento, dimensiones/tramos, cargas y puntos de aplicación.\n"
            "2) Si faltan datos clave (q, F, M, coordenadas, L, EI, etc.), pregúntalos; no des finales numéricos.\n"
            "3) Escribe equilibrio (ΣFy=0, ΣMx=0) con reacciones y punto de referencia para momentos.\n"
            "4) Calcula reacciones numéricamente con unidades.\n"
            "5) Para vigas: Q(x) y M(x) por tramos (breve), valores en límites y extremos.\n"
            "6) Control: ΣFy≈0 y ΣM≈0.\n"
            "7) Resultado: lista compacta con unidades.\n"
            "8) Si es hiperestática: grado, método y datos necesarios (p.ej. EI)."
        ),
        "quiz_system": "Crea un mini-test basado en la explicación. Usa solo hechos del texto.",
        "quiz_user_prefix": (
            "Crea {n} pregunta(s) tipo test a partir del material de abajo. Cada pregunta debe tener 4 opciones (A–D) y una sola correcta. "
            "Devuelve solo JSON: "
            "{\"questions\":[{\"q\":\"...\",\"options\":[\"...\",\"...\",\"...\",\"...\"],\"correct\":\"A\",\"why\":\"...\"}]}"
        ),
        "image_hint_default": "Lee el enunciado de la imagen y resuélvelo paso a paso.",
        "image_extra_eng": (
            "Si es un esquema de ingeniería (viga/cercha/cargas/apoyos): identifica símbolos y dimensiones, "
            "escribe ΣFy=0 y ΣM=0, calcula reacciones si hay datos, pregunta lo que falte, final con unidades."
        ),
        "mini_test_title": "🧠 Mini-test",
    },
    "tr": {
        "system_school": (
            "Sen uStudy’sin, akıllı bir öğrenme asistanısın. Amaç: kullanıcının konuyu gerçekten anlamasını sağlamak.\n\n"
            "Tarz:\n"
            "• Samimi ve net yaz.\n"
            "• Soru basitse kısa cevap ver.\n"
            "• Zorsa: kısa özet (1–3 satır) → adım adım çözüm → sonuç.\n"
            "• Eksik veri varsa: 1–3 net soru sor.\n"
            "• Bilgi uydurma; birden fazla yorum varsa belirt.\n"
            "• Gerekirse kısa bir kontrol satırı ekle.\n\n"
            "Konular: okul/kolej/üniversite (matematik, fizik, kimya, mühendislik, beşeri bilimler, diller vb.)."
        ),
        "format_note": (
            "Düz metin yaz, LaTeX kullanma. \\( \\), \\[ \\], \\frac{..}{..}, ^{ } ve _{ } kullanma."
        ),
        "language_rule": "Cevabı kesinlikle Türkçe ver.",
        "teacher_mode": (
            "İyi bir öğretmen gibi anlat: 1) sezgi/benzetme; 2) adım adım çözüm; "
            "3) yaygın hatalar; 4) mini-kontrol: 3 kısa soru ve sonunda cevaplar."
        ),
        "engineering_rules": (
            "MOD: MÜHENDİSLİK HESAPLARI (statik/kirişler/kafes sistemler/mukavemet).\n"
            "1) Verileri yaz: mesnetler, boyutlar/parçalar, yükler ve uygulama noktaları.\n"
            "2) Ana veriler eksikse (q, F, M, koordinat, L, EI vb.) sor; sayısal sonuç verme.\n"
            "3) Denge denklemleri: ΣFy=0, ΣM=0 (tepkilerle), moment referans noktasını belirt.\n"
            "4) Tepkileri sayısal hesapla, birimleriyle.\n"
            "5) Kiriş için: Q(x) ve M(x) bölgelere göre (kısa), sınır değerleri ve ekstremumlar.\n"
            "6) Kontrol: ΣFy≈0 ve ΣM≈0.\n"
            "7) Sonuç: birimleriyle kompakt liste.\n"
            "8) Statikçe belirsizse: derece, yöntem ve gerekli veriler (örn. EI)."
        ),
        "quiz_system": "Verilen açıklamaya göre mini test oluştur. Sadece metindeki gerçeklere bağlı kal.",
        "quiz_user_prefix": (
            "Aşağıdaki materyale göre {n} çoktan seçmeli soru oluştur. Her soruda 4 seçenek (A–D) ve tek doğru cevap olsun. "
            "Sadece JSON döndür: "
            "{\"questions\":[{\"q\":\"...\",\"options\":[\"...\",\"...\",\"...\",\"...\"],\"correct\":\"A\",\"why\":\"...\"}]}"
        ),
        "image_hint_default": "Görseldeki soruyu oku ve adım adım çöz.",
        "image_extra_eng": (
            "Eğer bu bir mühendislik şemasıysa (kiriş/kafes/yük/mesnet): sembolleri ve ölçüleri tanı, "
            "ΣFy=0 ve ΣM=0 yaz, veri varsa tepkileri sayısal bul; eksikleri sor; birimlerle bitir."
        ),
        "mini_test_title": "🧠 Mini test",
    },
    "ar": {
        "system_school": (
            "أنت uStudy، مساعد تعلّم ذكي. الهدف: مساعدة المستخدم على فهم الموضوع فعلاً.\n\n"
            "الأسلوب:\n"
            "• كن ودودًا وواضحًا.\n"
            "• إذا كان السؤال بسيطًا فأجب بإيجاز.\n"
            "• إذا كان أصعب: ملخص قصير (1–3 سطور) → شرح خطوة بخطوة → النتيجة.\n"
            "• إذا كانت بيانات مهمة ناقصة: اسأل 1–3 أسئلة دقيقة.\n"
            "• لا تخترع حقائق؛ إذا وُجدت تفسيرات متعددة فاذكرها.\n"
            "• عند الحاجة أضف سطر تحقق بسيط.\n\n"
            "الموضوعات: المدرسة/الكلية/الجامعة (رياضيات، فيزياء، كيمياء، هندسة، علوم إنسانية، لغات، إلخ)."
        ),
        "format_note": (
            "اكتب كنص عادي بدون LaTeX. لا تستخدم \\( \\)، \\[ \\]، \\frac{..}{..}، أو ^{ } و _{ }."
        ),
        "language_rule": "أجب باللغة العربية فقط.",
        "teacher_mode": (
            "اشرح كمدرّس ممتاز: 1) حدس/تشبيه؛ 2) حل خطوة بخطوة؛ "
            "3) أخطاء شائعة؛ 4) تحقق صغير: 3 أسئلة قصيرة مع الإجابات في النهاية."
        ),
        "engineering_rules": (
            "وضع: حسابات هندسية (استاتيكا/كمرات/جمالونات/مقاومة مواد).\n"
            "1) اذكر المعطيات: المساند/التثبيت، الأبعاد/المقاطع، الأحمال ونقاط تأثيرها.\n"
            "2) إذا كانت بيانات أساسية ناقصة (q، F، M، الإحداثيات، L، EI...) فاطلبها ولا تعطِ نتائج رقمية نهائية.\n"
            "3) اكتب معادلات الاتزان (ΣFy=0، ΣM=0) مع ردود الأفعال ونقطة أخذ العزوم.\n"
            "4) احسب ردود الأفعال رقميًا مع الوحدات.\n"
            "5) للكمرات: عرّف Q(x) و M(x) على المقاطع (باختصار) واذكر القيم الحدّية والعظمى.\n"
            "6) تحقق: ΣFy≈0 و ΣM≈0.\n"
            "7) النتيجة: قائمة مختصرة بالقيم مع الوحدات.\n"
            "8) إذا كان النظام غير محدد استاتيكيًا: اذكر الدرجة والطريقة المطلوبة والبيانات اللازمة (مثل EI)."
        ),
        "quiz_system": "أنشئ اختبارًا قصيرًا بناءً على الشرح. التزم فقط بالحقائق الموجودة في النص.",
        "quiz_user_prefix": (
            "أنشئ {n} سؤال/أسئلة اختيار من متعدد من المادة أدناه. لكل سؤال 4 خيارات (A–D) وإجابة صحيحة واحدة. "
            "أعد فقط JSON: "
            "{\"questions\":[{\"q\":\"...\",\"options\":[\"...\",\"...\",\"...\",\"...\"],\"correct\":\"A\",\"why\":\"...\"}]}"
        ),
        "image_hint_default": "اقرأ المسألة من الصورة وحلّها خطوة بخطوة.",
        "image_extra_eng": (
            "إذا كان هذا مخططًا هندسيًا (كمرة/جملون/أحمال/مساند): حدّد الرموز والأبعاد، "
            "اكتب ΣFy=0 و ΣM=0، احسب ردود الأفعال إن توفرت البيانات؛ وإن نقصت فاسأل عنها؛ وأنهِ بالوحدات."
        ),
        "mini_test_title": "🧠 اختبار قصير",
    },
    "hi": {
        "system_school": (
            "आप uStudy हैं, एक स्मार्ट लर्निंग असिस्टेंट। लक्ष्य: यूज़र को विषय सच में समझने में मदद करना।\n\n"
            "स्टाइल:\n"
            "• दोस्ताना और साफ़ भाषा में लिखें।\n"
            "• सवाल आसान हो तो छोटा जवाब दें।\n"
            "• मुश्किल हो तो: छोटा सार (1–3 पंक्तियाँ) → स्टेप-बाय-स्टेप → अंतिम परिणाम।\n"
            "• जरूरी डेटा न हो तो 1–3 सटीक सवाल पूछें।\n"
            "• तथ्य न गढ़ें; अगर कई व्याख्याएँ हों तो विकल्प बताएं।\n"
            "• जरूरत हो तो एक छोटी self-check लाइन जोड़ें।\n\n"
            "विषय: स्कूल/कॉलेज/यूनिवर्सिटी (गणित, भौतिकी, रसायन, इंजीनियरिंग, मानविकी, भाषाएँ आदि)।"
        ),
        "format_note": (
            "सादा टेक्स्ट में लिखें, LaTeX न इस्तेमाल करें। \\( \\), \\[ \\], \\frac{..}{..}, ^{ } और _{ } का उपयोग न करें।"
        ),
        "language_rule": "उत्तर केवल हिन्दी में दें।",
        "teacher_mode": (
            "अच्छे शिक्षक की तरह समझाएँ: 1) intuition/उदाहरण; 2) स्टेप-बाय-स्टेप हल; "
            "3) आम गलतियाँ; 4) mini-check: 3 छोटे प्रश्न और अंत में उत्तर।"
        ),
        "engineering_rules": (
            "मोड: इंजीनियरिंग कैलकुलेशन (statics/beams/trusses/strength of materials).\n"
            "1) दिए गए डेटा लिखें: supports/constraints, dimensions/segments, loads और application points.\n"
            "2) key डेटा missing हो (q, F, M, coordinates, L, EI आदि) तो पूछें; numeric final न दें.\n"
            "3) equilibrium equations लिखें (ΣFy=0, ΣM=0) reactions के साथ और moment reference point बताएं.\n"
            "4) reactions को numerically निकालें, units के साथ.\n"
            "5) beams के लिए: Q(x) और M(x) segments के हिसाब से (संक्षेप में), boundaries और extrema बताएं.\n"
            "6) check: ΣFy≈0 और ΣM≈0.\n"
            "7) final: results की compact list units के साथ.\n"
            "8) statically indeterminate हो तो degree, method और required data (जैसे EI) बताएं."
        ),
        "quiz_system": "दिए गए explanation के आधार पर mini-quiz बनाएं। केवल टेक्स्ट के facts पर टिके रहें।",
        "quiz_user_prefix": (
            "नीचे दिए गए material से {n} multiple-choice प्रश्न बनाएं। हर प्रश्न में 4 options (A–D) और 1 सही उत्तर हो। "
            "सिर्फ JSON लौटाएं: "
            "{\"questions\":[{\"q\":\"...\",\"options\":[\"...\",\"...\",\"...\",\"...\"],\"correct\":\"A\",\"why\":\"...\"}]}"
        ),
        "image_hint_default": "छवि में दिया गया प्रश्न पढ़ें और step-by-step हल करें।",
        "image_extra_eng": (
            "अगर यह engineering diagram है (beam/truss/loads/supports): labels और dimensions पहचानें, "
            "ΣFy=0 और ΣM=0 लिखें, data हो तो reactions numerically निकालें; नहीं हो तो missing data पूछें; units के साथ खत्म करें।"
        ),
        "mini_test_title": "🧠 Mini-quiz",
    },
}

AnswerTemplate = Literal["default", "conspect", "ege", "code_skeleton", "essay_outline"]

TEMPLATES: Dict[AnswerTemplate, Dict[Lang, str]] = {
    "default": {k: "" for k in PROMPTS.keys()},
    "conspect": {
        "ru": "Сделай конспект: Введение → определения/формулы → ключевые идеи → 2 примера → итог. Без воды.",
        "en": "Make a study note: intro → definitions/formulas → key ideas → 2 examples → conclusion. No fluff.",
        "uz": "Konspekt tuz: kirish → ta’riflar/formulalar → asosiy g‘oyalar → 2 ta misol → yakun. Suvsiz.",
        "kk": "Конспект жаса: кіріспе → анықтамалар/формулалар → негізгі идеялар → 2 мысал → қорытынды. Артық сөзсіз.",
        "de": "Erstelle ein Kurzskript: Einleitung → Definitionen/Formeln → Kernideen → 2 Beispiele → Fazit. Ohne Fülltext.",
        "fr": "Fais une fiche: intro → définitions/formules → idées clés → 2 exemples → conclusion. Sans blabla.",
        "es": "Haz un resumen-apunte: intro → definiciones/fórmulas → ideas clave → 2 ejemplos → conclusión. Sin relleno.",
        "tr": "Ders özeti hazırla: giriş → tanımlar/formüller → ana fikirler → 2 örnek → sonuç. Gereksiz yok.",
        "ar": "اكتب ملخصًا دراسيًا: مقدمة → تعريفات/صيغ → أفكار رئيسية → مثالان → خلاصة. بدون حشو.",
        "hi": "एक कॉन्सेप्ट नोट बनाओ: परिचय → परिभाषाएँ/सूत्र → मुख्य विचार → 2 उदाहरण → निष्कर्ष। बिना फ़ालतू।",
    },
    "ege": {
        "ru": "Разбор в стиле экзамена: что дано → что найти → решение по шагам → проверка → ответ. Без LaTeX.",
        "en": "Exam-style: given → find → step-by-step → check → answer. No LaTeX.",
        "uz": "Imtihon uslubida: berilgan → topish → bosqichma-bosqich → tekshiruv → javob. LaTeX yo‘q.",
        "kk": "Емтихан стилі: берілген → табу → қадамдап → тексеру → жауап. LaTeX жоқ.",
        "de": "Prüfungsstil: gegeben → gesucht → Schritte → Kontrolle → Antwort. Kein LaTeX.",
        "fr": "Style examen : données → demandé → étapes → vérification → réponse. Sans LaTeX.",
        "es": "Estilo examen: datos → se pide → pasos → verificación → respuesta. Sin LaTeX.",
        "tr": "Sınav tarzı: verilen → istenen → adımlar → kontrol → cevap. LaTeX yok.",
        "ar": "أسلوب امتحان: المعطيات → المطلوب → خطوات الحل → تحقق → الجواب. بدون LaTeX.",
        "hi": "एग्ज़ाम स्टाइल: दिया गया → क्या निकालना है → स्टेप्स → चेक → उत्तर। LaTeX नहीं।",
    },
    "code_skeleton": {
        "ru": "Дай каркас кода: структура, функции/классы, минимальные примеры запуска. Без комментариев в коде.",
        "en": "Provide a code skeleton: structure, functions/classes, minimal run examples. No comments in code.",
        "uz": "Kod skeleti: tuzilma, funksiyalar/klasslar, minimal ishga tushirish misoli. Kodda kommentariyasiz.",
        "kk": "Код қаңқасы: құрылым, функция/класстар, минималды іске қосу үлгісі. Кодта комментарийсіз.",
        "de": "Code-Gerüst: Struktur, Funktionen/Klassen, minimale Startbeispiele. Keine Kommentare im Code.",
        "fr": "Squelette de code: structure, fonctions/classes, exemple minimal d’exécution. Sans commentaires dans le code.",
        "es": "Esqueleto de código: estructura, funciones/clases, ejemplo mínimo de ejecución. Sin comentarios en el código.",
        "tr": "Kod iskeleti: yapı, fonksiyonlar/sınıflar, minimal çalıştırma örneği. Kodda yorum yok.",
        "ar": "هيكل كود: بنية، دوال/كلاسات، مثال تشغيل بسيط. بدون تعليقات داخل الكود.",
        "hi": "कोड स्केलेटन: स्ट्रक्चर, functions/classes, minimal run example. कोड में comments नहीं।",
    },
    "essay_outline": {
        "ru": "Сделай план эссе/реферата: тезисы, аргументы, структура разделов, что почитать (в общих словах).",
        "en": "Provide an essay/report outline: тезes, arguments, section structure, what to read (generally).",
        "uz": "Esse/referat rejasi: tezislar, argumentlar, bo‘limlar tuzilmasi, nimalarni o‘qish (umumiy).",
        "kk": "Эссе/реферат жоспары: тезистер, дәлелдер, бөлім құрылымы, не оқу керек (жалпы).",
        "de": "Essay/Referat-Gliederung: Thesen, Argumente, Abschnittsstruktur, Lesetipps (allgemein).",
        "fr": "Plan d’essai/rapport: thèses, arguments, structure, lectures conseillées (général).",
        "es": "Plan de ensayo/informe: tesis, argumentos, estructura, lecturas (general).",
        "tr": "Deneme/rapor planı: tezler, argümanlar, bölüm yapısı, genel okuma önerileri.",
        "ar": "خطة مقال/بحث: أطروحات، حجج، هيكل الأقسام، قراءات مقترحة بشكل عام.",
        "hi": "निबंध/रिपोर्ट आउटलाइन: थीसिस, तर्क, सेक्शन स्ट्रक्चर, क्या पढ़ें (जनरल)।",
    },
}

ENGINEERING_KEYWORDS = {
    "балка", "ферма", "опора", "шарнир", "защемление", "реакция", "момент", "изгибающий", "поперечная сила", "диаграмма", "сопромат",
    "beam", "truss", "support", "hinge", "fixed support", "reaction", "bending moment", "shear force", "diagram", "statics",
    "kiriş", "kafes", "mesnet", "tepki", "moment", "kesme kuvveti", "eğilme momenti",
    "poutre", "treillis", "appui", "réaction", "moment fléchissant", "effort tranchant",
    "viga", "cercha", "apoyo", "reacción", "momento flector", "cortante",
    "balken", "fachwerk", "lager", "reaktion", "biegemoment", "querkraft",
    "كمرة", "جملون", "مسند", "رد فعل", "عزم", "قص", "انحناء",
}
ENGINEERING_UNIT_HINTS = {"kn", "kn/m", "n/m", "knm", "kn·m", "nm", "n·m", "ei", "mpa", "gpa"}

def _needs_engineering_mode(text: str) -> bool:
    t = (text or "").lower()
    if any(k in t for k in ENGINEERING_KEYWORDS):
        return True
    compact = t.replace(" ", "")
    return any(u in compact for u in ENGINEERING_UNIT_HINTS)

def style_to_template(style: Optional[str]) -> AnswerTemplate:
    s = (style or "").strip().lower()
    if s in {"conspect", "outline"}:
        return "conspect"
    if s in {"ege", "exam"}:
        return "ege"
    if s in {"code", "code_skeleton"}:
        return "code_skeleton"
    if s in {"essay", "essay_outline", "report"}:
        return "essay_outline"
    return "default"

def _compact_history(history: List[Dict[str, str]], max_items: int = 12) -> List[Dict[str, str]]:
    if not history:
        return []
    cleaned: List[Dict[str, str]] = []
    for m in history:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = (m.get("content") or "").strip()
        if not content:
            continue
        cleaned.append({"role": role, "content": content})
    return cleaned[-max_items:]

def _prompt_pack(lang: Lang) -> Dict[str, str]:
    return PROMPTS.get(lang) or PROMPTS[DEFAULT_LANG]

def _build_messages(
    user_text: str,
    history: List[Dict[str, str]],
    *,
    lang: Optional[str] = None,
    template: AnswerTemplate = "default",
    teacher_mode: bool = False,
) -> List[Dict[str, Any]]:
    L = _norm_lang(lang)
    P = _prompt_pack(L)

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": P["system_school"]},
        {"role": "system", "content": P["format_note"]},
        {"role": "system", "content": P["language_rule"]},
    ]

    if _needs_engineering_mode(user_text):
        messages.append({"role": "system", "content": P["engineering_rules"]})

    tpl = (TEMPLATES.get(template) or {}).get(L, "")
    if tpl:
        messages.append({"role": "system", "content": tpl})

    if teacher_mode:
        messages.append({"role": "system", "content": P["teacher_mode"]})

    if history:
        messages.extend(_compact_history(history))
    messages.append({"role": "user", "content": user_text})
    return messages

async def _chat_create(**kwargs: Any):
    return await client.chat.completions.create(**kwargs)

async def stream_chat(
    messages: List[Dict[str, Any]],
    *,
    temperature: float = 0.4,
    priority: bool = False,
) -> AsyncIterator[str]:
    kwargs: Dict[str, Any] = {
        "model": TEXT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    if priority:
        kwargs["extra_headers"] = {"X-Queue": "priority", "X-Tier": "pro"}

    try:
        stream = await _chat_create(**kwargs)
        async for chunk in stream:
            if not getattr(chunk, "choices", None):
                continue
            delta = getattr(chunk.choices[0], "delta", None)
            content = getattr(delta, "content", None) if delta is not None else None
            if content:
                yield content
        return
    except Exception:
        pass

    resp = await _chat_create(
        model=TEXT_MODEL,
        messages=messages,
        temperature=temperature,
    )
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        return
    for i in range(0, len(text), 220):
        yield text[i:i + 220]

async def stream_response_text(
    user_text: str,
    history: List[Dict[str, str]],
    *,
    lang: Optional[str] = None,
    template: AnswerTemplate = "default",
    teacher_mode: bool = False,
    priority: bool = False,
) -> AsyncIterator[str]:
    temp = 0.18 if _needs_engineering_mode(user_text) else 0.45
    messages = _build_messages(
        user_text,
        history,
        lang=lang,
        template=template,
        teacher_mode=teacher_mode,
    )
    async for delta in stream_chat(messages, temperature=temp, priority=priority):
        yield delta

async def generate_text(
    user_text: str,
    history: List[Dict[str, str]],
    *,
    lang: Optional[str] = None,
    template: AnswerTemplate = "default",
    teacher_mode: bool = False,
    temperature: Optional[float] = None,
    priority: bool = False,
) -> str:
    if temperature is None:
        temperature = 0.18 if _needs_engineering_mode(user_text) else 0.45

    messages = _build_messages(
        user_text,
        history,
        lang=lang,
        template=template,
        teacher_mode=teacher_mode,
    )

    kwargs: Dict[str, Any] = {
        "model": TEXT_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if priority:
        kwargs["extra_headers"] = {"X-Queue": "priority", "X-Tier": "pro"}

    resp = await _chat_create(**kwargs)
    return (resp.choices[0].message.content or "").strip()

async def teacher_explain(
    user_text: str,
    history: List[Dict[str, str]],
    *,
    lang: Optional[str] = None,
    priority: bool = False,
) -> str:
    return await generate_text(
        user_text,
        history,
        lang=lang,
        teacher_mode=True,
        temperature=0.22,
        priority=priority,
    )

async def generate_by_template(
    user_text: str,
    history: List[Dict[str, str]],
    template: AnswerTemplate,
    *,
    lang: Optional[str] = None,
    priority: bool = False,
) -> str:
    return await generate_text(
        user_text,
        history,
        lang=lang,
        template=template,
        teacher_mode=False,
        priority=priority,
    )

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_FIRST_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)

def _safe_load_json(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    t = text.strip()

    m = _JSON_BLOCK_RE.search(t)
    if not m:
        m = _FIRST_OBJ_RE.search(t)
    if not m:
        return {}

    s = (m.group(1) if m.lastindex else m.group(0)).strip()
    s = re.sub(r"//.*?$", "", s, flags=re.MULTILINE)
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)
    s = re.sub(r",\s*([}\]])", r"\1", s)

    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        s2 = "".join(ch for ch in s if ord(ch) >= 32)
        try:
            obj2 = json.loads(s2)
            return obj2 if isinstance(obj2, dict) else {}
        except Exception:
            return {}

async def quiz_from_answer(
    answer_text: str,
    *,
    lang: Optional[str] = None,
    n_questions: int = 4,
) -> Tuple[str, Dict[str, Any]]:
    L = _norm_lang(lang)
    P = _prompt_pack(L)

    user = (
        P["quiz_user_prefix"].format(n=n_questions)
        + "\n\n=== SOURCE ===\n"
        + (answer_text or "")
    )

    resp = await _chat_create(
        model=TEXT_MODEL,
        messages=[
            {"role": "system", "content": P["quiz_system"]},
            {"role": "system", "content": P["language_rule"]},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    raw = (resp.choices[0].message.content or "").strip()

    data = _safe_load_json(raw)
    questions = data.get("questions") or []
    fixed: List[Dict[str, Any]] = []

    for item in questions:
        if not isinstance(item, dict):
            continue
        qtext = str(item.get("q", "")).strip()
        opts = list(item.get("options") or [])
        opts = [str(x).strip() for x in opts][:4]
        while len(opts) < 4:
            opts.append("—")
        corr = str(item.get("correct", "A")).strip().upper()[:1]
        if corr not in {"A", "B", "C", "D"}:
            corr = "A"
        why = str(item.get("why", "")).strip()
        if qtext:
            fixed.append({"q": qtext, "options": opts, "correct": corr, "why": why})

    payload = {"questions": fixed}

    ABCD = ["A", "B", "C", "D"]
    lines: List[str] = [P["mini_test_title"]]
    total = len(fixed)

    for i, q in enumerate(fixed, 1):
        lines.append(f"\n{i}/{total}: {q['q']}")
        for j, label in enumerate(ABCD):
            lines.append(f"{label}) {q['options'][j]}")

    return "\n".join(lines).strip(), payload

async def solve_from_image(
    image_bytes: bytes,
    hint: str,
    history: List[Dict[str, str]],
    *,
    lang: Optional[str] = None,
) -> str:
    L = _norm_lang(lang)
    P = _prompt_pack(L)

    data_url = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode("utf-8")
    text_hint = (hint or P["image_hint_default"]).strip()
    extra = P["image_extra_eng"]

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": P["system_school"]},
        {"role": "system", "content": P["format_note"]},
        {"role": "system", "content": P["language_rule"]},
        {"role": "system", "content": P["engineering_rules"]},
    ]

    if history:
        messages.extend(_compact_history(history))

    messages.append(
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"{text_hint}\n\n{extra}"},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    )

    resp = await _chat_create(
        model=VISION_MODEL,
        messages=messages,
        temperature=0.18,
    )
    return (resp.choices[0].message.content or "").strip()
