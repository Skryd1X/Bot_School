from . import pick_lang

_FAQ: dict[str, str] = {
    "ru": (
        "<b>FAQ</b>\n\n"
        "<b>1) Что умеет бот?</b>\n"
        "Разбирает задачи по шагам, объясняет теорию, помогает с текстами, кодом, фото-задачами.\n\n"
        "<b>2) Почему ответ иногда неточный?</b>\n"
        "Иногда в условии не хватает данных или фото нечитабельное. Пришлите более чёткое фото или уточните числа.\n\n"
        "<b>3) Как поменять язык?</b>\n"
        "⚙️ Настройки → 🌐 Язык бота.\n\n"
        "<b>4) Как включить режим Учителя?</b>\n"
        "В PRO: ⚙️ Настройки → 👩‍🏫 Включить режим Учителя.\n\n"
        "<b>5) Что даёт PRO?</b>\n"
        "Приоритет, больше лимитов, озвучка, PDF, мини-тест и режим Учителя.\n\n"
        "<b>6) Сохраняются ли мои сообщения?</b>\n"
        "Хранится минимальный контекст для диалога и улучшения качества. Не отправляйте секретные данные.\n\n"
        "<b>7) Как работает бонус за друзей?</b>\n"
        "Приглашайте по ссылке. За каждые N покупок по вашей ссылке начисляется месяц PRO.\n\n"
        "<b>8) Куда писать по оплатам?</b>\n"
        "Если есть чек/платёж и что-то не активировалось — пришлите дату и Telegram ID, разберёмся."
    ),
    "en": (
        "<b>FAQ</b>\n\n"
        "<b>1) What can the bot do?</b>\n"
        "Step-by-step solutions, theory explanations, essays/outlines, code help, photo tasks.\n\n"
        "<b>2) Why can an answer be inaccurate?</b>\n"
        "Sometimes the task is missing data or the photo is unclear. Send a clearer photo or add the numbers.\n\n"
        "<b>3) How do I change language?</b>\n"
        "⚙️ Settings → 🌐 Bot language.\n\n"
        "<b>4) How to enable Teacher mode?</b>\n"
        "In PRO: ⚙️ Settings → 👩‍🏫 Enable Teacher mode.\n\n"
        "<b>5) What does PRO include?</b>\n"
        "Priority, higher limits, voice, PDF export, mini-quiz, Teacher mode.\n\n"
        "<b>6) Are my messages stored?</b>\n"
        "Only minimal context is stored to keep the dialog consistent. Don’t send secrets.\n\n"
        "<b>7) How does referral bonus work?</b>\n"
        "Invite via your link. Every N paid referrals grants +1 month PRO.\n\n"
        "<b>8) Payment issues?</b>\n"
        "If payment was made but not activated, send the date/time and your Telegram ID."
    ),
    "uz": (
        "<b>FAQ</b>\n\n"
        "<b>1) Bot nimalarni qila oladi?</b>\n"
        "Masalalarni qadam-baqadam yechadi, nazariyani tushuntiradi, matn/kodga yordam beradi, rasmli masalalarni ham.\n\n"
        "<b>2) Nega ba’zan xato bo‘lishi mumkin?</b>\n"
        "Ba’zan shartda ma’lumot yetishmaydi yoki rasm noaniq. Yaxshiroq foto yuboring yoki sonlarni yozing.\n\n"
        "<b>3) Tilni qanday o‘zgartiraman?</b>\n"
        "⚙️ Sozlamalar → 🌐 Bot tili.\n\n"
        "<b>4) O‘qituvchi rejimi?</b>\n"
        "PRO’da: ⚙️ Sozlamalar → 👩‍🏫 O‘qituvchi rejimi.\n\n"
        "<b>5) PRO nimani beradi?</b>\n"
        "Prioritet, ko‘proq limit, ovoz, PDF, mini-test va O‘qituvchi.\n\n"
        "<b>6) Xabarlar saqlanadimi?</b>\n"
        "Faqat dialog uchun minimal kontekst saqlanadi. Maxfiy ma’lumot yubormang.\n\n"
        "<b>7) Referal bonus qanday ishlaydi?</b>\n"
        "Havola orqali taklif qiling. Har N ta to‘lovdan so‘ng +1 oy PRO.\n\n"
        "<b>8) To‘lov muammosi bo‘lsa?</b>\n"
        "To‘lov bo‘lib, aktiv bo‘lmasa — sana/vaqt va Telegram ID yuboring."
    ),
    "kk": (
        "<b>FAQ</b>\n\n"
        "<b>1) Бот не істей алады?</b>\n"
        "Есепті қадам-қадам шығарады, теорияны түсіндіреді, мәтін/кодқа көмектеседі, фото-есептерді оқиды.\n\n"
        "<b>2) Неге кейде жауап дәл емес?</b>\n"
        "Кейде шартта дерек жетіспейді немесе фото анық емес. Анығырақ фото жіберіңіз не сандарды жазыңыз.\n\n"
        "<b>3) Тілді қалай ауыстырам?</b>\n"
        "⚙️ Баптаулар → 🌐 Бот тілі.\n\n"
        "<b>4) Мұғалім режимі?</b>\n"
        "PRO: ⚙️ Баптаулар → 👩‍🏫 Мұғалім режимі.\n\n"
        "<b>5) PRO не береді?</b>\n"
        "Приоритет, жоғары лимит, дауыс, PDF, мини-тест және Мұғалім.\n\n"
        "<b>6) Хабарлар сақтала ма?</b>\n"
        "Тек диалогқа қажет минималды контекст сақталады. Құпия дерек жібермеңіз.\n\n"
        "<b>7) Дос бонусы қалай?</b>\n"
        "Сілтемемен шақырыңыз. Әр N төлемнен кейін +1 ай PRO.\n\n"
        "<b>8) Төлем мәселе болса?</b>\n"
        "Төлем өтті, бірақ іске қосылмаса — уақыт/күні және Telegram ID жіберіңіз."
    ),
    "de": (
        "<b>FAQ</b>\n\n"
        "<b>1) Was kann der Bot?</b>\n"
        "Schritt-für-Schritt-Lösungen, Theorie, Texte, Code, Foto-Aufgaben.\n\n"
        "<b>2) Warum ist eine Antwort manchmal ungenau?</b>\n"
        "Manchmal fehlen Daten oder das Foto ist unleserlich. Senden Sie ein klareres Foto oder Werte.\n\n"
        "<b>3) Sprache ändern?</b>\n"
        "⚙️ Einstellungen → 🌐 Bot-Sprache.\n\n"
        "<b>4) Lehrer-Modus?</b>\n"
        "In PRO: ⚙️ Einstellungen → 👩‍🏫 Lehrer-Modus.\n\n"
        "<b>5) Was bringt PRO?</b>\n"
        "Priorität, höhere Limits, Audio, PDF, Mini-Quiz, Lehrer-Modus.\n\n"
        "<b>6) Werden Nachrichten gespeichert?</b>\n"
        "Nur minimaler Kontext für konsistente Antworten. Keine Geheimnisse senden.\n\n"
        "<b>7) Referral-Bonus?</b>\n"
        "Per Link einladen. Jede N-te bezahlte Empfehlung = +1 Monat PRO.\n\n"
        "<b>8) Zahlungsprobleme?</b>\n"
        "Wenn bezahlt, aber nicht aktiviert: Datum/Uhrzeit + Telegram-ID senden."
    ),
    "fr": (
        "<b>FAQ</b>\n\n"
        "<b>1) Que peut faire le bot ?</b>\n"
        "Solutions étape par étape, explications, textes, code, exercices en photo.\n\n"
        "<b>2) Pourquoi une réponse peut être imprécise ?</b>\n"
        "Données manquantes ou photo floue. Envoyez une photo plus nette ou précisez les valeurs.\n\n"
        "<b>3) Changer la langue ?</b>\n"
        "⚙️ Paramètres → 🌐 Langue du bot.\n\n"
        "<b>4) Mode Prof ?</b>\n"
        "PRO: ⚙️ Paramètres → 👩‍🏫 Mode Prof.\n\n"
        "<b>5) PRO inclut quoi ?</b>\n"
        "Priorité, limites plus hautes, voix, PDF, mini-quiz, mode Prof.\n\n"
        "<b>6) Les messages sont-ils stockés ?</b>\n"
        "Contexte minimal pour la cohérence. N’envoyez pas d’infos sensibles.\n\n"
        "<b>7) Bonus parrainage ?</b>\n"
        "Invitez via votre lien. Chaque N achats = +1 mois PRO.\n\n"
        "<b>8) Problème de paiement ?</b>\n"
        "Paiement effectué mais non activé : envoyez date/heure et votre Telegram ID."
    ),
    "es": (
        "<b>FAQ</b>\n\n"
        "<b>1) ¿Qué puede hacer el bot?</b>\n"
        "Soluciones paso a paso, teoría, textos, ayuda con código y ejercicios por foto.\n\n"
        "<b>2) ¿Por qué a veces falla?</b>\n"
        "Puede faltar información o la foto ser borrosa. Envía una imagen más clara o añade los datos.\n\n"
        "<b>3) ¿Cómo cambio el idioma?</b>\n"
        "⚙️ Ajustes → 🌐 Idioma del bot.\n\n"
        "<b>4) ¿Modo Profesor?</b>\n"
        "En PRO: ⚙️ Ajustes → 👩‍🏫 Modo Profesor.\n\n"
        "<b>5) ¿Qué incluye PRO?</b>\n"
        "Prioridad, más límites, voz, PDF, mini-test y modo Profesor.\n\n"
        "<b>6) ¿Se guardan mensajes?</b>\n"
        "Solo contexto mínimo para coherencia. No envíes información sensible.\n\n"
        "<b>7) ¿Bonus por referidos?</b>\n"
        "Invita con tu enlace. Cada N compras = +1 mes de PRO.\n\n"
        "<b>8) ¿Problemas de pago?</b>\n"
        "Si pagaste y no se activó: envía fecha/hora y tu Telegram ID."
    ),
    "tr": (
        "<b>SSS</b>\n\n"
        "<b>1) Bot neler yapar?</b>\n"
        "Adım adım çözüm, konu anlatımı, metin, kod desteği ve fotoğraftan soru çözümü.\n\n"
        "<b>2) Neden bazen yanlış olabilir?</b>\n"
        "Veri eksik olabilir ya da fotoğraf net değildir. Daha net foto gönder veya değerleri yaz.\n\n"
        "<b>3) Dil nasıl değiştirilir?</b>\n"
        "⚙️ Ayarlar → 🌐 Bot dili.\n\n"
        "<b>4) Öğretmen modu?</b>\n"
        "PRO: ⚙️ Ayarlar → 👩‍🏫 Öğretmen modu.\n\n"
        "<b>5) PRO ne sağlar?</b>\n"
        "Öncelik, daha yüksek limit, ses, PDF, mini test ve öğretmen modu.\n\n"
        "<b>6) Mesajlar saklanıyor mu?</b>\n"
        "Sadece minimal bağlam tutulur. Gizli bilgi göndermeyin.\n\n"
        "<b>7) Referans bonusu?</b>\n"
        "Linkinizle davet edin. Her N satın alma = +1 ay PRO.\n\n"
        "<b>8) Ödeme sorunu?</b>\n"
        "Ödeme yapıldı ama aktif değilse: tarih/saat ve Telegram ID gönderin."
    ),
    "ar": (
        "<b>الأسئلة الشائعة</b>\n\n"
        "<b>1) ماذا يفعل البوت؟</b>\n"
        "حلول خطوة بخطوة، شرح، مساعدة في النصوص والبرمجة، وحل المسائل من الصور.\n\n"
        "<b>2) لماذا قد يكون الرد غير دقيق؟</b>\n"
        "قد تنقص بيانات أو تكون الصورة غير واضحة. أرسل صورة أوضح أو اكتب القيم.\n\n"
        "<b>3) تغيير اللغة؟</b>\n"
        "⚙️ الإعدادات → 🌐 لغة البوت.\n\n"
        "<b>4) وضع المعلّم؟</b>\n"
        "ضمن PRO: ⚙️ الإعدادات → 👩‍🏫 وضع المعلّم.\n\n"
        "<b>5) ماذا يقدم PRO؟</b>\n"
        "أولوية، حدود أعلى، صوت، PDF، اختبار قصير، ووضع المعلّم.\n\n"
        "<b>6) هل يتم حفظ الرسائل؟</b>\n"
        "يُحفظ حدّ أدنى من السياق فقط. لا ترسل معلومات حساسة.\n\n"
        "<b>7) كيف يعمل бонус الأصدقاء؟</b>\n"
        "ادعُ عبر رابطك. كل N مشتريات مدفوعة = شهر PRO مجاني.\n\n"
        "<b>8) مشاكل الدفع؟</b>\n"
        "إذا دفعت ولم يتفعّل: أرسل التاريخ/الوقت ومعرّف Telegram."
    ),
    "hi": (
        "<b>FAQ</b>\n\n"
        "<b>1) बॉट क्या कर सकता है?</b>\n"
        "स्टेप-बाय-स्टेप समाधान, थ्योरी समझाना, टेक्स्ट/कोड मदद, फोटो से प्रश्न हल।\n\n"
        "<b>2) कभी गलत क्यों हो सकता है?</b>\n"
        "कभी डेटा कम होता है या फोटो साफ नहीं होता। साफ फोटो भेजें या मान लिखें।\n\n"
        "<b>3) भाषा कैसे बदलें?</b>\n"
        "⚙️ सेटिंग्स → 🌐 बॉट भाषा।\n\n"
        "<b>4) टीचर मोड?</b>\n"
        "PRO में: ⚙️ सेटिंग्स → 👩‍🏫 टीचर मोड।\n\n"
        "<b>5) PRO में क्या मिलता है?</b>\n"
        "प्राथमिकता, अधिक लिमिट, वॉयस, PDF, मिनी-टेस्ट, टीचर मोड।\n\n"
        "<b>6) क्या संदेश सेव होते हैं?</b>\n"
        "केवल न्यूनतम संदर्भ रखा जाता है। संवेदनशील जानकारी न भेजें।\n\n"
        "<b>7) रेफरल बोनस?</b>\n"
        "अपने लिंक से आमंत्रित करें। हर N खरीद पर +1 महीना PRO।\n\n"
        "<b>8) पेमेंट समस्या?</b>\n"
        "पेमेंट हो गया पर एक्टिव नहीं: तारीख/समय और Telegram ID भेजें।"
    ),
}

def get_faq(lang: str | None) -> str:
    return pick_lang(lang, _FAQ)
