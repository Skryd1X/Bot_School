from . import pick_lang

_STRINGS: dict[str, dict[str, str]] = {
    "choose_section": {
        "ru": "Выберите раздел:",
        "en": "Choose a section:",
        "uz": "Bo‘limni tanlang:",
        "kk": "Бөлімді таңдаңыз:",
        "de": "Wählen Sie einen Abschnitt:",
        "fr": "Choisissez une section :",
        "es": "Elige una sección:",
        "tr": "Bir bölüm seçin:",
        "ar": "اختر قسمًا:",
        "hi": "एक अनुभाग चुनें:",
    },
    "choose_language": {
        "ru": "🌐 Выберите язык бота (интерфейс + ответы).",
        "en": "🌐 Choose the bot language (interface + answers).",
        "uz": "🌐 Bot tilini tanlang (interfeys + javoblar).",
        "kk": "🌐 Бот тілін таңдаңыз (интерфейс + жауаптар).",
        "de": "🌐 Wählen Sie die Sprache des Bots (UI + Antworten).",
        "fr": "🌐 Choisissez la langue du bot (interface + réponses).",
        "es": "🌐 Elige el idioma del bot (interfaz + respuestas).",
        "tr": "🌐 Bot dilini seçin (arayüz + yanıtlar).",
        "ar": "🌐 اختر لغة البوت (الواجهة + الردود).",
        "hi": "🌐 बॉट की भाषा चुनें (इंटरफ़ेस + उत्तर)।",
    },
    "language_saved": {
        "ru": "✅ Язык сохранён: {title}.",
        "en": "✅ Language saved: {title}.",
        "uz": "✅ Til saqlandi: {title}.",
        "kk": "✅ Тіл сақталды: {title}.",
        "de": "✅ Sprache gespeichert: {title}.",
        "fr": "✅ Langue enregistrée : {title}.",
        "es": "✅ Idioma guardado: {title}.",
        "tr": "✅ Dil kaydedildi: {title}.",
        "ar": "✅ تم حفظ اللغة: {title}.",
        "hi": "✅ भाषा सहेजी गई: {title}।",
    },

    "ready": {
        "ru": "Готово.",
        "en": "Done.",
        "uz": "Tayyor.",
        "kk": "Дайын.",
        "de": "Fertig.",
        "fr": "C’est fait.",
        "es": "Listo.",
        "tr": "Tamam.",
        "ar": "تمّ.",
        "hi": "हो गया।",
    },

    "choose_package": {
        "ru": "Выберите пакет:",
        "en": "Choose a plan:",
        "uz": "Tarifni tanlang:",
        "kk": "Тарифті таңдаңыз:",
        "de": "Wählen Sie einen Tarif:",
        "fr": "Choisissez une offre :",
        "es": "Elige un plan:",
        "tr": "Bir paket seçin:",
        "ar": "اختر باقة:",
        "hi": "एक प्लान चुनें:",
    },
    "available_packages": {
        "ru": "Доступные пакеты:",
        "en": "Available plans:",
        "uz": "Mavjud tariflar:",
        "kk": "Қолжетімді тарифтер:",
        "de": "Verfügbare Tarife:",
        "fr": "Offres disponibles :",
        "es": "Planes disponibles:",
        "tr": "Mevcut paketler:",
        "ar": "الباقات المتاحة:",
        "hi": "उपलब्ध प्लान:",
    },
    "upgrade_hint": {
        "ru": "⬆️ Доступно обновление до PRO для безлимита и приоритета.",
        "en": "⬆️ You can upgrade to PRO for unlimited use and priority.",
        "uz": "⬆️ PRO’ga o‘tsangiz: cheksiz va prioritet.",
        "kk": "⬆️ PRO: шектеусіз және приоритет.",
        "de": "⬆️ Upgrade auf PRO: unbegrenzt + Priorität.",
        "fr": "⬆️ Passez en PRO : illimité + priorité.",
        "es": "⬆️ Mejora a PRO: ilimitado + prioridad.",
        "tr": "⬆️ PRO’ya geç: limitsiz + öncelik.",
        "ar": "⬆️ الترقية إلى PRO: بلا حدود + أولوية.",
        "hi": "⬆️ PRO पर जाएँ: अनलिमिटेड + प्राथमिकता।",
    },

    "wait_prev": {
        "ru": "⏳ Ответ генерируется... дождитесь окончания предыдущего запроса!",
        "en": "⏳ I’m generating a reply… please wait for the previous request to finish!",
        "uz": "⏳ Javob tayyorlayapman… avvalgi so‘rov tugashini kuting!",
        "kk": "⏳ Жауап дайындалып жатыр… алдыңғы сұрау біткенін күтіңіз!",
        "de": "⏳ Antwort wird erstellt… bitte warten Sie auf die vorherige Anfrage!",
        "fr": "⏳ Je génère la réponse… attendez la fin de la demande précédente !",
        "es": "⏳ Generando… espera a que termine la solicitud anterior.",
        "tr": "⏳ Yanıt hazırlanıyor… önceki isteğin bitmesini bekleyin!",
        "ar": "⏳ جارٍ إعداد الرد… الرجاء انتظار انتهاء الطلب السابق!",
        "hi": "⏳ उत्तर बनाया जा रहा है… कृपया पिछले अनुरोध के पूरा होने तक प्रतीक्षा करें!",
    },
    "thinking": {
        "ru": "Думаю…",
        "en": "Thinking…",
        "uz": "O‘ylayapman…",
        "kk": "Ойланудамын…",
        "de": "Ich denke nach…",
        "fr": "Je réfléchis…",
        "es": "Pensando…",
        "tr": "Düşünüyorum…",
        "ar": "أفكّر…",
        "hi": "सोच रहा हूँ…",
    },
    "photo_thinking": {
        "ru": "Распознаю задачу с фото…",
        "en": "Reading the task from the photo…",
        "uz": "Rasmdan masalani o‘qiyapman…",
        "kk": "Фотодан есепті оқып жатырмын…",
        "de": "Ich lese die Aufgabe aus dem Foto…",
        "fr": "Je lis l’exercice depuis la photo…",
        "es": "Leyendo el ejercicio de la foto…",
        "tr": "Fotoğraftaki soruyu okuyorum…",
        "ar": "أقرأ المسألة من الصورة…",
        "hi": "फोटो से प्रश्न पढ़ रहा हूँ…",
    },

    "cooldown_start": {
        "ru": "🕒 Включен медленный режим (антиспам): {s} сек",
        "en": "🕒 Slow mode is on (anti-spam): {s}s",
        "uz": "🕒 Sekin rejim (anti-spam): {s} soniya",
        "kk": "🕒 Баяу режим (антиспам): {s} с",
        "de": "🕒 Slow-Mode (Anti-Spam): {s}s",
        "fr": "🕒 Mode lent (anti-spam) : {s}s",
        "es": "🕒 Modo lento (anti-spam): {s}s",
        "tr": "🕒 Yavaş mod (anti-spam): {s} sn",
        "ar": "🕒 وضع بطيء (مكافحة السبام): {s}ث",
        "hi": "🕒 स्लो मोड (एंटी-स्पैम): {s} सेकंड",
    },
    "cooldown_tick": {
        "ru": "🕒 Медленный режим: {s} сек",
        "en": "🕒 Slow mode: {s}s",
        "uz": "🕒 Sekin rejim: {s} soniya",
        "kk": "🕒 Баяу режим: {s} с",
        "de": "🕒 Slow-Mode: {s}s",
        "fr": "🕒 Mode lent : {s}s",
        "es": "🕒 Modo lento: {s}s",
        "tr": "🕒 Yavaş mod: {s} sn",
        "ar": "🕒 وضع بطيء: {s}ث",
        "hi": "🕒 स्लो मोड: {s} सेकंड",
    },

    "empty_answer": {
        "ru": "Пустой ответ 😕",
        "en": "Empty answer 😕",
        "uz": "Javob bo‘sh 😕",
        "kk": "Жауап бос 😕",
        "de": "Leere Antwort 😕",
        "fr": "Réponse vide 😕",
        "es": "Respuesta vacía 😕",
        "tr": "Boş yanıt 😕",
        "ar": "ردّ فارغ 😕",
        "hi": "खाली उत्तर 😕",
    },
    "actions_with_answer": {
        "ru": "Действия с ответом:",
        "en": "Actions:",
        "uz": "Javob bilan amallar:",
        "kk": "Жауап әрекеттері:",
        "de": "Aktionen:",
        "fr": "Actions :",
        "es": "Acciones:",
        "tr": "İşlemler:",
        "ar": "إجراءات:",
        "hi": "कार्रवाइयाँ:",
    },

    "pro_badge": {
        "ru": "⚡ PRO-приоритет",
        "en": "⚡ PRO priority",
        "uz": "⚡ PRO prioritet",
        "kk": "⚡ PRO приоритет",
        "de": "⚡ PRO-Priorität",
        "fr": "⚡ Priorité PRO",
        "es": "⚡ Prioridad PRO",
        "tr": "⚡ PRO öncelik",
        "ar": "⚡ أولوية PRO",
        "hi": "⚡ PRO प्राथमिकता",
    },

    "subs_only_pro": {
        "ru": "Доступно только в PRO.",
        "en": "Available in PRO only.",
        "uz": "Faqat PRO’da mavjud.",
        "kk": "Тек PRO-да қолжетімді.",
        "de": "Nur in PRO verfügbar.",
        "fr": "Disponible uniquement en PRO.",
        "es": "Disponible solo en PRO.",
        "tr": "Sadece PRO’da.",
        "ar": "متاح فقط في PRO.",
        "hi": "केवल PRO में उपलब्ध।",
    },
    "need_pro_voice": {
        "ru": "🎙 Авто-озвучка доступна только в PRO.",
        "en": "🎙 Auto voice is available in PRO only.",
        "uz": "🎙 Auto-ovoz faqat PRO’da.",
        "kk": "🎙 Авто-дауыс тек PRO-да.",
        "de": "🎙 Auto-Audio nur in PRO.",
        "fr": "🎙 Auto-voix uniquement en PRO.",
        "es": "🎙 Voz automática solo en PRO.",
        "tr": "🎙 Otomatik ses sadece PRO’da.",
        "ar": "🎙 الصوت التلقائي متاح فقط في PRO.",
        "hi": "🎙 ऑटो-आवाज़ केवल PRO में।",
    },
    "need_pro_teacher": {
        "ru": "👩‍🏫 Режим Учителя доступен только в PRO.",
        "en": "👩‍🏫 Teacher mode is available in PRO only.",
        "uz": "👩‍🏫 O‘qituvchi rejimi faqat PRO’da.",
        "kk": "👩‍🏫 Мұғалім режимі тек PRO-да.",
        "de": "👩‍🏫 Lehrer-Modus nur in PRO.",
        "fr": "👩‍🏫 Mode Prof uniquement en PRO.",
        "es": "👩‍🏫 Modo Profesor solo en PRO.",
        "tr": "👩‍🏫 Öğretmen modu sadece PRO’da.",
        "ar": "👩‍🏫 وضع المعلّم متاح فقط في PRO.",
        "hi": "👩‍🏫 टीचर मोड केवल PRO में।",
    },

    "teacher_on": {
        "ru": "👩‍🏫 Режим Учителя: ВКЛ.",
        "en": "👩‍🏫 Teacher mode: ON.",
        "uz": "👩‍🏫 O‘qituvchi rejimi: ON.",
        "kk": "👩‍🏫 Мұғалім режимі: ҚОСУЛЫ.",
        "de": "👩‍🏫 Lehrer-Modus: AN.",
        "fr": "👩‍🏫 Mode Prof : ON.",
        "es": "👩‍🏫 Modo Profesor: ON.",
        "tr": "👩‍🏫 Öğretmen modu: AÇIK.",
        "ar": "👩‍🏫 وضع المعلّم: تشغيل.",
        "hi": "👩‍🏫 टीचर मोड: ON।",
    },
    "teacher_off": {
        "ru": "👩‍🏫 Режим Учителя: ВЫКЛ.",
        "en": "👩‍🏫 Teacher mode: OFF.",
        "uz": "👩‍🏫 O‘qituvchi rejimi: OFF.",
        "kk": "👩‍🏫 Мұғалім режимі: ӨШІРУЛІ.",
        "de": "👩‍🏫 Lehrer-Modus: AUS.",
        "fr": "👩‍🏫 Mode Prof : OFF.",
        "es": "👩‍🏫 Modo Profesor: OFF.",
        "tr": "👩‍🏫 Öğretmen modu: KAPALI.",
        "ar": "👩‍🏫 وضع المعلّم: إيقاف.",
        "hi": "👩‍🏫 टीचर मोड: OFF।",
    },

    "voice_on": {
        "ru": "🔔 Авто-озвучка: ВКЛ.",
        "en": "🔔 Auto voice: ON.",
        "uz": "🔔 Auto-ovoz: ON.",
        "kk": "🔔 Авто-дауыс: ҚОСУЛЫ.",
        "de": "🔔 Auto-Audio: AN.",
        "fr": "🔔 Auto-voix : ON.",
        "es": "🔔 Voz automática: ON.",
        "tr": "🔔 Otomatik ses: AÇIK.",
        "ar": "🔔 الصوت التلقائي: تشغيل.",
        "hi": "🔔 ऑटो-आवाज़: ON।",
    },
    "voice_off": {
        "ru": "🔕 Авто-озвучка: ВЫКЛ.",
        "en": "🔕 Auto voice: OFF.",
        "uz": "🔕 Auto-ovoz: OFF.",
        "kk": "🔕 Авто-дауыс: ӨШІРУЛІ.",
        "de": "🔕 Auto-Audio: AUS.",
        "fr": "🔕 Auto-voix : OFF.",
        "es": "🔕 Voz automática: OFF.",
        "tr": "🔕 Otomatik ses: KAPALI.",
        "ar": "🔕 الصوت التلقائي: إيقاف.",
        "hi": "🔕 ऑटो-आवाज़: OFF।",
    },

    "ctx_cleared": {
        "ru": "🧹 Контекст очищен",
        "en": "🧹 Context cleared",
        "uz": "🧹 Kontekst tozalandi",
        "kk": "🧹 Контекст тазаланды",
        "de": "🧹 Kontext gelöscht",
        "fr": "🧹 Contexte réinitialisé",
        "es": "🧹 Contexto reiniciado",
        "tr": "🧹 Bağlam temizlendi",
        "ar": "🧹 تم مسح السياق",
        "hi": "🧹 संदर्भ साफ़ किया गया",
    },

    "bookmark_saved": {
        "ru": "🔖 Сохранено в закладки. Достанешь через /bookmark или /forget для удаления.",
        "en": "🔖 Saved. Use /bookmark to view or /forget to remove the last one.",
        "uz": "🔖 Saqlandi. Ko‘rish: /bookmark, o‘chirish: /forget.",
        "kk": "🔖 Сақталды. Көру: /bookmark, өшіру: /forget.",
        "de": "🔖 Gespeichert. /bookmark ansehen, /forget löschen.",
        "fr": "🔖 Enregistré. Voir: /bookmark, supprimer: /forget.",
        "es": "🔖 Guardado. Ver: /bookmark, borrar: /forget.",
        "tr": "🔖 Kaydedildi. Gör: /bookmark, sil: /forget.",
        "ar": "🔖 تم الحفظ. عرض: /bookmark، حذف: /forget.",
        "hi": "🔖 सहेजा गया। देखें: /bookmark, हटाएँ: /forget।",
    },
    "bookmark_none": {
        "ru": "Закладок пока нет.",
        "en": "No bookmarks yet.",
        "uz": "Hozircha zakladka yo‘q.",
        "kk": "Әзірге бетбелгі жоқ.",
        "de": "Noch keine Lesezeichen.",
        "fr": "Aucun marque-page pour l’instant.",
        "es": "Aún no hay marcadores.",
        "tr": "Henüz yer imi yok.",
        "ar": "لا توجد علامات بعد.",
        "hi": "अभी कोई बुकमार्क नहीं।",
    },
    "bookmark_deleted": {
        "ru": "🗑 Удалил последнюю закладку.",
        "en": "🗑 Deleted the last bookmark.",
        "uz": "🗑 Oxirgi zakladka o‘chirildi.",
        "kk": "🗑 Соңғы бетбелгі өшірілді.",
        "de": "🗑 Letztes Lesezeichen gelöscht.",
        "fr": "🗑 Dernier marque-page supprimé.",
        "es": "🗑 Último marcador eliminado.",
        "tr": "🗑 Son yer imi silindi.",
        "ar": "🗑 تم حذف آخر علامة.",
        "hi": "🗑 आख़िरी बुकमार्क हटाया गया।",
    },
    "bookmark_not_found": {
        "ru": "Закладок не найдено.",
        "en": "No bookmarks found.",
        "uz": "Zakladkalar topilmadi.",
        "kk": "Бетбелгі табылмады.",
        "de": "Keine Lesezeichen gefunden.",
        "fr": "Aucun marque-page trouvé.",
        "es": "No se encontraron marcadores.",
        "tr": "Yer imi bulunamadı.",
        "ar": "لم يتم العثور على علامات.",
        "hi": "कोई बुकमार्क नहीं मिला।",
    },
    "no_last_answer": {
        "ru": "Нет последнего ответа для закладки.",
        "en": "No last answer to bookmark.",
        "uz": "Zakladka uchun oxirgi javob yo‘q.",
        "kk": "Бетбелгіге соңғы жауап жоқ.",
        "de": "Keine letzte Antwort zum Speichern.",
        "fr": "Aucune dernière réponse à enregistrer.",
        "es": "No hay respuesta reciente para guardar.",
        "tr": "Kaydetmek için son yanıt yok.",
        "ar": "لا يوجد رد أخير للحفظ.",
        "hi": "सहेजने के लिए कोई अंतिम उत्तर नहीं।",
    },

    "no_text_for_tts": {
        "ru": "Нет текста для озвучки",
        "en": "No text to voice",
        "uz": "Ovoz berish uchun matn yo‘q",
        "kk": "Дауысқа мәтін жоқ",
        "de": "Kein Text für Audio",
        "fr": "Aucun texte à lire",
        "es": "No hay texto para voz",
        "tr": "Ses için metin yok",
        "ar": "لا يوجد نص للصوت",
        "hi": "आवाज़ के लिए टेक्स्ट नहीं",
    },
    "tts_doing": {
        "ru": "Озвучиваю…",
        "en": "Voicing…",
        "uz": "Ovozlayapman…",
        "kk": "Дауыс шығарып жатырмын…",
        "de": "Ich spreche…",
        "fr": "Je génère la voix…",
        "es": "Generando voz…",
        "tr": "Ses oluşturuyorum…",
        "ar": "جارٍ إنشاء الصوت…",
        "hi": "आवाज़ बना रहा हूँ…",
    },

    "exporting": {
        "ru": "Уже экспортирую…",
        "en": "Export is already running…",
        "uz": "Eksport ketmoqda…",
        "kk": "Экспорт жүріп жатыр…",
        "de": "Export läuft bereits…",
        "fr": "Export déjà en cours…",
        "es": "La exportación ya está en curso…",
        "tr": "Dışa aktarım sürüyor…",
        "ar": "التصدير قيد التنفيذ…",
        "hi": "एक्सपोर्ट चल रहा है…",
    },
    "no_text_for_export": {
        "ru": "Нет текста для экспорта",
        "en": "No text to export",
        "uz": "Eksport uchun matn yo‘q",
        "kk": "Экспортқа мәтін жоқ",
        "de": "Kein Text zum Exportieren",
        "fr": "Aucun texte à exporter",
        "es": "No hay texto para exportar",
        "tr": "Dışa aktarmak için metin yok",
        "ar": "لا يوجد نص للتصدير",
        "hi": "एक्सपोर्ट के लिए टेक्स्ट नहीं",
    },

    "pdf_caption": {
        "ru": "📄 Экспортировано в PDF",
        "en": "📄 Exported to PDF",
        "uz": "📄 PDF’ga eksport qilindi",
        "kk": "📄 PDF-ке экспортталды",
        "de": "📄 Als PDF exportiert",
        "fr": "📄 Exporté en PDF",
        "es": "📄 Exportado a PDF",
        "tr": "📄 PDF’ye aktarıldı",
        "ar": "📄 تم التصدير إلى PDF",
        "hi": "📄 PDF में एक्सपोर्ट किया गया",
    },
    "pdf_title": {
        "ru": "Разбор задачи",
        "en": "Solution",
        "uz": "Masala yechimi",
        "kk": "Есеп шешімі",
        "de": "Lösung",
        "fr": "Solution",
        "es": "Solución",
        "tr": "Çözüm",
        "ar": "الحل",
        "hi": "समाधान",
    },
    "pdf_filename": {
        "ru": "razbor.pdf",
        "en": "solution.pdf",
        "uz": "yechim.pdf",
        "kk": "sheshim.pdf",
        "de": "loesung.pdf",
        "fr": "solution.pdf",
        "es": "solucion.pdf",
        "tr": "cozum.pdf",
        "ar": "حل.pdf",
        "hi": "samadhan.pdf",
    },

    "quiz_building": {
        "ru": "Готовлю мини-тест…",
        "en": "Building a mini-quiz…",
        "uz": "Mini-test tayyorlayapman…",
        "kk": "Мини-тест дайындап жатырмын…",
        "de": "Mini-Quiz wird erstellt…",
        "fr": "Je prépare un mini-quiz…",
        "es": "Preparando mini-test…",
        "tr": "Mini test hazırlanıyor…",
        "ar": "أجهز اختبارًا صغيرًا…",
        "hi": "मिनी टेस्ट बना रहा हूँ…",
    },
    "quiz_need_answer": {
        "ru": "Сначала получи разбор/ответ, потом сделаю тест.",
        "en": "Get an explanation first, then I’ll make a quiz.",
        "uz": "Avval javob/yechim oling, keyin test qilaman.",
        "kk": "Алдымен жауап/шешім алыңыз, кейін тест жасаймын.",
        "de": "Erst Lösung, dann Quiz.",
        "fr": "D’abord la solution, ensuite le quiz.",
        "es": "Primero la explicación, luego el test.",
        "tr": "Önce açıklama, sonra test.",
        "ar": "أولاً احصل على الشرح ثم الاختبار.",
        "hi": "पहले समाधान, फिर टेस्ट।",
    },
    "quiz_done": {
        "ru": "Готово! Хочешь ещё раз — жми «🧠 Проверить себя».",
        "en": "Done! Want another one — tap “🧠 Check yourself”.",
        "uz": "Tayyor! Yana istasangiz — «🧠 O‘zingni tekshir».",
        "kk": "Дайын! Қайта — «🧠 Өзіңді тексер».",
        "de": "Fertig! Nochmal: „🧠 Selbsttest“.",
        "fr": "C’est fait ! Refaire : «🧠 Se tester ».",
        "es": "¡Listo! Repetir: «🧠 Autoevaluación».",
        "tr": "Tamam! Tekrar: «🧠 Kendini test et».",
        "ar": "تم! لإعادة: «🧠 اختبر نفسك».",
        "hi": "हो गया! फिर से: «🧠 खुद को जांचें».",
    },
    "quiz_not_found": {
        "ru": "Тест не найден.",
        "en": "Quiz not found.",
        "uz": "Test topilmadi.",
        "kk": "Тест табылмады.",
        "de": "Quiz nicht gefunden.",
        "fr": "Quiz introuvable.",
        "es": "Test no encontrado.",
        "tr": "Test bulunamadı.",
        "ar": "لم يتم العثور على الاختبار.",
        "hi": "टेस्ट नहीं मिला।",
    },
    "quiz_q_not_found": {
        "ru": "Вопрос не найден.",
        "en": "Question not found.",
        "uz": "Savol topilmadi.",
        "kk": "Сұрақ табылмады.",
        "de": "Frage nicht gefunden.",
        "fr": "Question introuvable.",
        "es": "Pregunta no encontrada.",
        "tr": "Soru bulunamadı.",
        "ar": "لم يتم العثور على السؤال.",
        "hi": "प्रश्न नहीं मिला।",
    },
    "quiz_err": {
        "ru": "Ошибка обработки ответа.",
        "en": "Couldn’t process that.",
        "uz": "Javobni qayta ishlashda xato.",
        "kk": "Жауапты өңдеу қатесі.",
        "de": "Fehler bei der Verarbeitung.",
        "fr": "Erreur de traitement.",
        "es": "Error al procesar.",
        "tr": "İşleme hatası.",
        "ar": "خطأ في المعالجة.",
        "hi": "प्रोसेसिंग त्रुटि।",
    },
    "quiz_correct": {
        "ru": "Верно! ✅",
        "en": "Correct! ✅",
        "uz": "To‘g‘ri! ✅",
        "kk": "Дұрыс! ✅",
        "de": "Richtig! ✅",
        "fr": "Correct ! ✅",
        "es": "¡Correcto! ✅",
        "tr": "Doğru! ✅",
        "ar": "صحيح! ✅",
        "hi": "सही! ✅",
    },
    "quiz_wrong": {
        "ru": "Неверно. ❌ Правильный ответ: {c}",
        "en": "Wrong. ❌ Correct answer: {c}",
        "uz": "Noto‘g‘ri. ❌ To‘g‘ri javob: {c}",
        "kk": "Қате. ❌ Дұрыс жауап: {c}",
        "de": "Falsch. ❌ Richtige Antwort: {c}",
        "fr": "Faux. ❌ Bonne réponse : {c}",
        "es": "Incorrecto. ❌ Respuesta: {c}",
        "tr": "Yanlış. ❌ Doğru: {c}",
        "ar": "خطأ. ❌ الصحيح: {c}",
        "hi": "गलत। ❌ सही: {c}",
    },

    "mode_pick_title": {
        "ru": "Выберите, как бот будет вести себя по умолчанию.",
        "en": "Choose how the bot should behave by default.",
        "uz": "Botning standart rejimini tanlang.",
        "kk": "Боттың әдепкі режимін таңдаңыз.",
        "de": "Wählen Sie den Standardmodus.",
        "fr": "Choisissez le mode par défaut.",
        "es": "Elige el modo predeterminado.",
        "tr": "Varsayılan modu seçin.",
        "ar": "اختر الوضع الافتراضي.",
        "hi": "डिफ़ॉल्ट मोड चुनें।",
    },
    "mode_current": {
        "ru": "Текущий режим: {t}\n{d}",
        "en": "Current mode: {t}\n{d}",
        "uz": "Joriy rejim: {t}\n{d}",
        "kk": "Ағымдағы режим: {t}\n{d}",
        "de": "Aktueller Modus: {t}\n{d}",
        "fr": "Mode actuel : {t}\n{d}",
        "es": "Modo actual: {t}\n{d}",
        "tr": "Mevcut mod: {t}\n{d}",
        "ar": "الوضع الحالي: {t}\n{d}",
        "hi": "वर्तमान मोड: {t}\n{d}",
    },

    "settings_intro": {
        "ru": "Настройки профиля:\n— авто-озвучка\n— режим Учителя\n— сброс контекста\n— тип работы бота",
        "en": "Settings:\n— auto voice\n— Teacher mode\n— reset context\n— bot mode",
        "uz": "Sozlamalar:\n— auto-ovoz\n— O‘qituvchi rejimi\n— kontekstni tozalash\n— bot rejimi",
        "kk": "Баптаулар:\n— авто-дауыс\n— Мұғалім режимі\n— контекстті тазалау\n— бот режимі",
        "de": "Einstellungen:\n— Auto-Audio\n— Lehrer-Modus\n— Kontext zurücksetzen\n— Bot-Modus",
        "fr": "Paramètres :\n— auto-voix\n— mode Prof\n— réinitialiser le contexte\n— mode du bot",
        "es": "Ajustes:\n— voz automática\n— modo Profesor\n— reiniciar contexto\n— modo del bot",
        "tr": "Ayarlar:\n— otomatik ses\n— öğretmen modu\n— bağlam sıfırlama\n— bot modu",
        "ar": "الإعدادات:\n— الصوت التلقائي\n— وضع المعلّم\n— إعادة تعيين السياق\n— وضع البوت",
        "hi": "सेटिंग्स:\n— ऑटो-आवाज़\n— टीचर मोड\n— संदर्भ रीसेट\n— बॉट मोड",
    },
    "settings_pro_hint": {
        "ru": "ℹ️ Учитель, авто-озвучка, PDF и мини-тест — в PRO.",
        "en": "ℹ️ Teacher mode, auto voice, PDF and mini-quiz are PRO features.",
        "uz": "ℹ️ O‘qituvchi, auto-ovoz, PDF va mini-test — PRO’da.",
        "kk": "ℹ️ Мұғалім, авто-дауыс, PDF және мини-тест — PRO-да.",
        "de": "ℹ️ Lehrer, Auto-Audio, PDF und Mini-Quiz sind PRO.",
        "fr": "ℹ️ Prof, auto-voix, PDF et mini-quiz — PRO.",
        "es": "ℹ️ Profesor, voz, PDF y mini-test — PRO.",
        "tr": "ℹ️ Öğretmen, otomatik ses, PDF ve mini test — PRO.",
        "ar": "ℹ️ وضع المعلّم والصوت وPDF والاختبار — PRO.",
        "hi": "ℹ️ टीचर मोड, ऑटो-आवाज़, PDF और मिनी टेस्ट — PRO।",
    },

    "admin_panel": {
        "ru": "Админ-панель:",
        "en": "Admin panel:",
        "uz": "Admin panel:",
        "kk": "Админ панель:",
        "de": "Admin-Panel:",
        "fr": "Panneau admin :",
        "es": "Panel admin:",
        "tr": "Admin paneli:",
        "ar": "لوحة الإدارة:",
        "hi": "एडमिन पैनल:",
    },
    "admin_only": {
        "ru": "⛔ Доступно только админам.",
        "en": "⛔ Admins only.",
        "uz": "⛔ Faqat adminlarga.",
        "kk": "⛔ Тек админдерге.",
        "de": "⛔ Nur für Admins.",
        "fr": "⛔ Réservé aux admins.",
        "es": "⛔ Solo admins.",
        "tr": "⛔ Sadece adminler.",
        "ar": "⛔ للأدمن فقط.",
        "hi": "⛔ केवल एडमिन।",
    },
    "admin_added": {
        "ru": "✅ Вы добавлены как админ. Открываю админ-панель.",
        "en": "✅ You’re an admin now. Opening the admin panel.",
        "uz": "✅ Siz admin bo‘ldingiz. Admin panel ochilmoqda.",
        "kk": "✅ Сіз админ болдыңыз. Панель ашылуда.",
        "de": "✅ Sie sind jetzt Admin. Öffne Panel.",
        "fr": "✅ Vous êtes admin. Ouverture du panneau.",
        "es": "✅ Ahora eres admin. Abriendo panel.",
        "tr": "✅ Admin oldunuz. Panel açılıyor.",
        "ar": "✅ أصبحت أدمن. فتح اللوحة.",
        "hi": "✅ आप एडमिन हैं। पैनल खोल रहा हूँ।",
    },
    "admin_already": {
        "ru": "Вы уже в админ-режиме.",
        "en": "You’re already in admin mode.",
        "uz": "Siz allaqachon admin rejimidasiz.",
        "kk": "Сіз админ режиміндесіз.",
        "de": "Sie sind bereits Admin.",
        "fr": "Vous êtes déjà admin.",
        "es": "Ya estás en modo admin.",
        "tr": "Zaten admin modundasın.",
        "ar": "أنت بالفعل أدمن.",
        "hi": "आप पहले से एडमिन मोड में हैं।",
    },
    "admin_limit": {
        "ru": "Нельзя добавить нового админа — достигнут лимит (2 админа).",
        "en": "Can’t add a new admin — limit reached (2 admins).",
        "uz": "Yangi admin qo‘shib bo‘lmaydi — limit (2 admin).",
        "kk": "Жаңа админ қосылмайды — лимит (2 админ).",
        "de": "Kein neuer Admin — Limit (2).",
        "fr": "Impossible d’ajouter — limite (2 admins).",
        "es": "No se puede añadir — límite (2 admins).",
        "tr": "Eklenemez — limit (2 admin).",
        "ar": "لا يمكن الإضافة — الحد (2 أدمن).",
        "hi": "नया एडमिन नहीं जोड़ सकते — सीमा (2 एडमिन)।",
    },
    "admin_left": {
        "ru": "Вы вышли из админ-режима.",
        "en": "You left admin mode.",
        "uz": "Admin rejimidan chiqdingiz.",
        "kk": "Админ режимінен шықтыңыз.",
        "de": "Admin-Modus verlassen.",
        "fr": "Mode admin quitté.",
        "es": "Saliste del modo admin.",
        "tr": "Admin modundan çıktın.",
        "ar": "تم الخروج من وضع الأدمن.",
        "hi": "एडमिन मोड से बाहर।",
    },
    "admin_not_in": {
        "ru": "Вы не в админ-режиме.",
        "en": "You’re not in admin mode.",
        "uz": "Siz admin rejimida emassiz.",
        "kk": "Сіз админ режимінде емессіз.",
        "de": "Nicht im Admin-Modus.",
        "fr": "Vous n’êtes pas admin.",
        "es": "No estás en modo admin.",
        "tr": "Admin modunda değilsin.",
        "ar": "لست في وضع الأدمن.",
        "hi": "आप एडमिन मोड में नहीं हैं।",
    },

    "bcast_send_text": {
        "ru": "Пришлите текст рассылки (plain/markdown).",
        "en": "Send the broadcast text (plain/markdown).",
        "uz": "Tarqatma matnini yuboring (plain/markdown).",
        "kk": "Тарату мәтінін жіберіңіз (plain/markdown).",
        "de": "Senden Sie den Broadcast-Text (plain/markdown).",
        "fr": "Envoyez le texte (plain/markdown).",
        "es": "Envía el texto (plain/markdown).",
        "tr": "Yayın metnini gönder (plain/markdown).",
        "ar": "أرسل نص البث (plain/markdown).",
        "hi": "ब्रॉडकास्ट टेक्स्ट भेजें (plain/markdown)।",
    },
    "bcast_preview": {
        "ru": "Предпросмотр рассылки:",
        "en": "Broadcast preview:",
        "uz": "Tarqatma ko‘rinishi:",
        "kk": "Тарату алдын ала көрінісі:",
        "de": "Vorschau:",
        "fr": "Aperçu :",
        "es": "Vista previa:",
        "tr": "Önizleme:",
        "ar": "معاينة البث:",
        "hi": "प्रीव्यू:",
    },
    "bcast_send": {
        "ru": "Разослать?",
        "en": "Send it?",
        "uz": "Yuboraymi?",
        "kk": "Жіберейін бе?",
        "de": "Senden?",
        "fr": "Envoyer ?",
        "es": "¿Enviar?",
        "tr": "Gönderilsin mi?",
        "ar": "إرسال؟",
        "hi": "भेजें?",
    },
    "bcast_send_photo": {
        "ru": "Пришлите фото для рассылки.",
        "en": "Send a photo for the broadcast.",
        "uz": "Tarqatma uchun rasm yuboring.",
        "kk": "Тарату үшін фото жіберіңіз.",
        "de": "Senden Sie ein Foto für den Broadcast.",
        "fr": "Envoyez une photo pour la diffusion.",
        "es": "Envía una foto para la difusión.",
        "tr": "Yayın için foto gönder.",
        "ar": "أرسل صورة للبث.",
        "hi": "ब्रॉडकास्ट के लिए फोटो भेजें।",
    },
    "bcast_caption": {
        "ru": "Добавьте подпись к фото (или пришлите «-» чтобы без подписи).",
        "en": "Add a caption (or send “-” for no caption).",
        "uz": "Rasmga izoh yozing (yoki «-» yuboring).",
        "kk": "Фотоға жазу қосыңыз (немесе «-»).",
        "de": "Caption hinzufügen (oder „-“ ohne).",
        "fr": "Ajoutez une légende (ou «-»).",
        "es": "Añade un texto (o “-”).",
        "tr": "Açıklama ekle (ya da “-”).",
        "ar": "أضف وصفًا (أو “-” بدون).",
        "hi": "कैप्शन जोड़ें (या “-” बिना कैप्शन)।",
    },
    "bcast_cancelled": {
        "ru": "Рассылка отменена.",
        "en": "Broadcast cancelled.",
        "uz": "Tarqatma bekor qilindi.",
        "kk": "Тарату тоқтатылды.",
        "de": "Broadcast abgebrochen.",
        "fr": "Diffusion annulée.",
        "es": "Difusión cancelada.",
        "tr": "Yayın iptal edildi.",
        "ar": "تم إلغاء البث.",
        "hi": "ब्रॉडकास्ट रद्द।",
    },
    "bcast_progress": {
        "ru": "Рассылка… {ok}/{total} {bar}",
        "en": "Broadcast… {ok}/{total} {bar}",
        "uz": "Tarqatma… {ok}/{total} {bar}",
        "kk": "Тарату… {ok}/{total} {bar}",
        "de": "Broadcast… {ok}/{total} {bar}",
        "fr": "Diffusion… {ok}/{total} {bar}",
        "es": "Difusión… {ok}/{total} {bar}",
        "tr": "Yayın… {ok}/{total} {bar}",
        "ar": "بث… {ok}/{total} {bar}",
        "hi": "ब्रॉडकास्ट… {ok}/{total} {bar}",
    },
    "bcast_done": {
        "ru": "Готово ✅ Отправлено: {ok}/{total}",
        "en": "Done ✅ Sent: {ok}/{total}",
        "uz": "Tayyor ✅ Yuborildi: {ok}/{total}",
        "kk": "Дайын ✅ Жіберілді: {ok}/{total}",
        "de": "Fertig ✅ Gesendet: {ok}/{total}",
        "fr": "Fait ✅ Envoyé : {ok}/{total}",
        "es": "Listo ✅ Enviado: {ok}/{total}",
        "tr": "Tamam ✅ Gönderildi: {ok}/{total}",
        "ar": "تم ✅ أُرسل: {ok}/{total}",
        "hi": "हो गया ✅ भेजा: {ok}/{total}",
    },

    "need_pro_pdf_quiz_text": {
        "ru": "Оформите PRO, чтобы открыть PDF и мини-тест:",
        "en": "Get PRO to unlock PDF and the mini-quiz:",
        "uz": "PDF va mini-test uchun PRO oling:",
        "kk": "PDF және мини-тест үшін PRO алыңыз:",
        "de": "PRO holen, um PDF & Mini-Quiz zu öffnen:",
        "fr": "Passez en PRO pour PDF + mini-quiz :",
        "es": "Obtén PRO para PDF + mini-test:",
        "tr": "PDF ve mini test için PRO:",
        "ar": "احصل على PRO لفتح PDF والاختبار:",
        "hi": "PDF और मिनी टेस्ट के लिए PRO लें:",
    },

    "photo_history": {
        "ru": "[Фото задачи]",
        "en": "[Task photo]",
        "uz": "[Masala rasmi]",
        "kk": "[Есеп фотосы]",
        "de": "[Aufgabenfoto]",
        "fr": "[Photo de l’exercice]",
        "es": "[Foto del ejercicio]",
        "tr": "[Soru fotoğrafı]",
        "ar": "[صورة المسألة]",
        "hi": "[प्रश्न फोटो]",
    },

    "explain_hint": {
        "ru": "Отправь вопрос/задачу — объясню как учитель: простые шаги, типичные ошибки и мини-проверка.",
        "en": "Send a question/task — I’ll explain like a teacher: steps, common mistakes, mini-check.",
        "uz": "Savol/masala yuboring — o‘qituvchi kabi tushuntiraman: qadamlar, xatolar, mini-tekshiruv.",
        "kk": "Сұрақ/есеп жіберіңіз — мұғалімше түсіндіремін: қадамдар, қателер, мини-тексеру.",
        "de": "Senden Sie eine Aufgabe — ich erkläre wie ein Lehrer: Schritte, typische Fehler, Mini-Check.",
        "fr": "Envoyez un exercice — j’explique comme un prof : étapes, erreurs, mini-vérif.",
        "es": "Envía un ejercicio — explico como profesor: pasos, errores, mini-chequeo.",
        "tr": "Soru gönder — öğretmen gibi anlatırım: adımlar, hatalar, mini kontrol.",
        "ar": "أرسل سؤالًا — أشرح كالمعلّم: خطوات، أخطاء شائعة، فحص سريع.",
        "hi": "प्रश्न भेजें — शिक्षक की तरह समझाऊँगा: स्टेप्स, गलतियाँ, मिनी-चेक।",
    },

    "pro_voice_cmd": {
        "ru": "🎙 Озвучка доступна только в PRO. Обновите план: /plan",
        "en": "🎙 Voice is available in PRO only. Upgrade: /plan",
        "uz": "🎙 Ovoz faqat PRO’da. Tarif: /plan",
        "kk": "🎙 Дауыс тек PRO-да. /plan",
        "de": "🎙 Audio nur in PRO. /plan",
        "fr": "🎙 Voix uniquement en PRO. /plan",
        "es": "🎙 Voz solo en PRO. /plan",
        "tr": "🎙 Ses sadece PRO’da. /plan",
        "ar": "🎙 الصوت فقط في PRO. /plan",
        "hi": "🎙 आवाज़ केवल PRO में। /plan",
    },
    "voice_enabled_cmd": {
        "ru": "🎙 Озвучка ответов: ВКЛ. Буду присылать voice после текста.",
        "en": "🎙 Voice answers: ON. I’ll send a voice after the text.",
        "uz": "🎙 Ovozli javob: ON. Matndan keyin voice yuboraman.",
        "kk": "🎙 Дауыс: ҚОСУЛЫ. Мәтіннен кейін voice жіберемін.",
        "de": "🎙 Audio-Antworten: AN. Voice nach Text.",
        "fr": "🎙 Voix : ON. Je l’enverrai après le texte.",
        "es": "🎙 Voz: ON. Enviaré audio tras el texto.",
        "tr": "🎙 Ses: AÇIK. Metinden sonra voice.",
        "ar": "🎙 الصوت: تشغيل. سأرسل voice بعد النص.",
        "hi": "🎙 आवाज़: ON। टेक्स्ट के बाद voice भेजूँगा।",
    },
    "voice_disabled_cmd": {
        "ru": "🎙 Озвучка ответов: ВЫКЛ. Кнопка «Озвучить» останется под ответами.",
        "en": "🎙 Voice answers: OFF. The “Voice” button will remain under answers.",
        "uz": "🎙 Ovozli javob: OFF. «Ovoz» tugmasi qoladi.",
        "kk": "🎙 Дауыс: ӨШІРУЛІ. «Дауыс» батырмасы қалады.",
        "de": "🎙 Audio: AUS. „Audio“-Button bleibt.",
        "fr": "🎙 Voix : OFF. Le bouton reste disponible.",
        "es": "🎙 Voz: OFF. El botón seguirá disponible.",
        "tr": "🎙 Ses: KAPALI. Buton kalacak.",
        "ar": "🎙 الصوت: إيقاف. زر الصوت سيبقى.",
        "hi": "🎙 आवाज़: OFF। बटन बना रहेगा।",
    },
    "voice_example": {
        "ru": "Пример: /voice aria",
        "en": "Example: /voice aria",
        "uz": "Misol: /voice aria",
        "kk": "Мысал: /voice aria",
        "de": "Beispiel: /voice aria",
        "fr": "Exemple : /voice aria",
        "es": "Ejemplo: /voice aria",
        "tr": "Örnek: /voice aria",
        "ar": "مثال: /voice aria",
        "hi": "उदाहरण: /voice aria",
    },
    "voice_speed_example": {
        "ru": "Пример: /voice_speed 0.9 (диапазон 0.5–1.6)",
        "en": "Example: /voice_speed 0.9 (range 0.5–1.6)",
        "uz": "Misol: /voice_speed 0.9 (0.5–1.6)",
        "kk": "Мысал: /voice_speed 0.9 (0.5–1.6)",
        "de": "Beispiel: /voice_speed 0.9 (0.5–1.6)",
        "fr": "Exemple : /voice_speed 0.9 (0.5–1.6)",
        "es": "Ejemplo: /voice_speed 0.9 (0.5–1.6)",
        "tr": "Örnek: /voice_speed 0.9 (0.5–1.6)",
        "ar": "مثال: /voice_speed 0.9 (0.5–1.6)",
        "hi": "उदाहरण: /voice_speed 0.9 (0.5–1.6)",
    },
    "voice_speed_num": {
        "ru": "Укажи число, например 1.1",
        "en": "Send a number, e.g. 1.1",
        "uz": "Son yuboring, masalan 1.1",
        "kk": "Сан жазыңыз, мысалы 1.1",
        "de": "Zahl angeben, z.B. 1.1",
        "fr": "Donnez un nombre, ex. 1.1",
        "es": "Indica un número, ej. 1.1",
        "tr": "Sayı gir, örn. 1.1",
        "ar": "أدخل رقمًا مثل 1.1",
        "hi": "संख्या लिखें, जैसे 1.1",
    },
    "voice_speed_set": {
        "ru": "🎛 Скорость озвучки: {v}",
        "en": "🎛 Voice speed: {v}",
        "uz": "🎛 Ovoz tezligi: {v}",
        "kk": "🎛 Дауыс жылдамдығы: {v}",
        "de": "🎛 Sprechtempo: {v}",
        "fr": "🎛 Vitesse: {v}",
        "es": "🎛 Velocidad: {v}",
        "tr": "🎛 Hız: {v}",
        "ar": "🎛 السرعة: {v}",
        "hi": "🎛 गति: {v}",
    },
    "voice_set": {
        "ru": "🎙 Голос: {v}",
        "en": "🎙 Voice: {v}",
        "uz": "🎙 Ovoz: {v}",
        "kk": "🎙 Дауыс: {v}",
        "de": "🎙 Stimme: {v}",
        "fr": "🎙 Voix : {v}",
        "es": "🎙 Voz: {v}",
        "tr": "🎙 Ses: {v}",
        "ar": "🎙 الصوت: {v}",
        "hi": "🎙 आवाज़: {v}",
    },

    "no_photo_recognized": {
        "ru": "Не удалось распознать задачу.",
        "en": "Couldn’t read the task.",
        "uz": "Masalani tanib bo‘lmadi.",
        "kk": "Есеп танылмады.",
        "de": "Aufgabe konnte nicht gelesen werden.",
        "fr": "Impossible de lire l’exercice.",
        "es": "No se pudo leer el ejercicio.",
        "tr": "Soru okunamadı.",
        "ar": "تعذّر قراءة المسألة.",
        "hi": "प्रश्न पढ़ा नहीं जा सका।",
    },
    "solve_hint_text": {
        "ru": "Распознай условие и реши задачу. Покажи ключевые шаги, вычисления и итог.",
        "en": "Read the problem and solve it step by step. Show key steps, calculations and final result.",
        "uz": "Shartni o‘qing va masalani bosqichma-bosqich yeching. Qadamlar, hisob-kitob va natija.",
        "kk": "Шартты оқып, қадамдап шығарыңыз. Негізгі қадам, есептеу, қорытынды.",
        "de": "Lies die Aufgabe und löse sie Schritt für Schritt mit Rechenschritten und Ergebnis.",
        "fr": "Lis l’énoncé et résous pas à pas, avec calculs et résultat.",
        "es": "Lee el enunciado y resuelve paso a paso, con cálculos y resultado.",
        "tr": "Soruyu oku ve adım adım çöz, hesaplamalar ve sonuçla.",
        "ar": "اقرأ المسألة وحلّها خطوة بخطوة مع الحسابات والنتيجة.",
        "hi": "प्रश्न पढ़ें और स्टेप-बाय-स्टेप हल करें: गणना और अंतिम उत्तर दें।",
    },

    "input_placeholder": {
        "ru": "Напишите вопрос или пришлите фото…",
        "en": "Type a question or send a photo…",
        "uz": "Savol yozing yoki rasm yuboring…",
        "kk": "Сұрақ жазыңыз немесе фото жіберіңіз…",
        "de": "Frage tippen oder Foto senden…",
        "fr": "Écrivez une question ou envoyez une photo…",
        "es": "Escribe una pregunta o envía una foto…",
        "tr": "Soru yazın veya foto gönderin…",
        "ar": "اكتب سؤالًا أو أرسل صورة…",
        "hi": "प्रश्न लिखें या फोटो भेजें…",
    },

    "greet_plan_free": {
        "ru": "Обновить план — кнопка ниже.",
        "en": "Upgrade plan — button below.",
        "uz": "Tarifni yangilash — pastdagi tugma.",
        "kk": "Жоспарды жаңарту — төмендегі батырма.",
        "de": "Upgrade — Button unten.",
        "fr": "Passer en PRO — bouton ci-dessous.",
        "es": "Mejorar plan — botón abajo.",
        "tr": "Planı yükselt — aşağıdaki buton.",
        "ar": "ترقية الخطة — الزر بالأسفل.",
        "hi": "प्लान अपग्रेड — नीचे बटन।",
    },
    "greet_plan_paid": {
        "ru": "Статус доступа — «🧾 Мои подписки».",
        "en": "Access status — “🧾 My subscriptions”.",
        "uz": "Kirish holati — «🧾 Obunalarim».",
        "kk": "Қолжетімділік — «🧾 Жазылымдарым».",
        "de": "Status — „🧾 Meine Abos“.",
        "fr": "Statut — «🧾 Mes abonnements ».",
        "es": "Estado — «🧾 Mis suscripciones».",
        "tr": "Durum — «🧾 Aboneliklerim».",
        "ar": "الحالة — «🧾 اشتراكاتي».",
        "hi": "स्थिति — «🧾 मेरी सदस्यताएँ»।",
    },

    "greeting": {
        "ru": (
            "👋 Привет! Я — учебный помощник для школы и вузов.\n\n"
            "Что я умею:\n"
            "• Разбирать задачи по шагам (математика, физика и др.)\n"
            "• Пояснять теорию простым языком\n"
            "• Делать конспекты, тесты, шпаргалки, планы\n"
            "• Помогать с кодом и оформлением\n"
            "• Понимать фото/скриншоты задач 📷\n\n"
            "Как начать:\n"
            "— Пришли фото задачи или напиши текстом.\n"
            "— Нужна справка — жми «FAQ / Помощь».\n"
            "— {plan_line}\n"
            "— 🎁 Бонус за друзей: пригласи друзей и получай PRO.\n\n"
            "Текущий режим: {mode_title}\n"
            "Изменить можно в ⚙️ Настройки → 🎛 Тип работы бота."
        ),
        "en": (
            "👋 Hi! I’m a study assistant for school and university.\n\n"
            "What I can do:\n"
            "• Solve problems step by step (math, physics, etc.)\n"
            "• Explain theory in simple words\n"
            "• Make notes, tests, cheat sheets and study plans\n"
            "• Help with code and formatting\n"
            "• Understand photos/screenshots 📷\n\n"
            "How to start:\n"
            "— Send a photo or describe the task in text.\n"
            "— Need help? Tap “FAQ / Help”.\n"
            "— {plan_line}\n"
            "— 🎁 Friends bonus: invite friends and get PRO.\n\n"
            "Current mode: {mode_title}\n"
            "You can change it in ⚙️ Settings → 🎛 Bot mode."
        ),
        "uz": (
            "👋 Salom! Men — maktab va OTM uchun o‘quv yordamchiman.\n\n"
            "Nimalarga yordam beraman:\n"
            "• Masalalarni bosqichma-bosqich yechish\n"
            "• Nazariyani sodda tilda tushuntirish\n"
            "• Konspekt, test, шпаргалка va reja tuzish\n"
            "• Kod va rasmiylashtirishga yordam\n"
            "• Masala foto/skrinlarini tushunish 📷\n\n"
            "Qanday boshlash:\n"
            "— Masalani yozing yoki foto yuboring.\n"
            "— Yordam kerak bo‘lsa — “FAQ / Yordam”.\n"
            "— {plan_line}\n"
            "— 🎁 Do‘stlar bonusi: do‘stlarni taklif qiling va PRO oling.\n\n"
            "Joriy rejim: {mode_title}\n"
            "O‘zgartirish: ⚙️ Sozlamalar → 🎛 Bot rejimi."
        ),
        "kk": (
            "👋 Сәлем! Мен — мектеп пен ЖОО үшін оқу көмекшісімін.\n\n"
            "Не істеймін:\n"
            "• Есептерді қадамдап шығару\n"
            "• Теорияны қарапайым тілмен түсіндіру\n"
            "• Конспект, тест, шпаргалка, жоспар жасау\n"
            "• Код пен рәсімдеуге көмектесу\n"
            "• Фото/скрин есептерін түсіну 📷\n\n"
            "Қалай бастау:\n"
            "— Мәтінмен жазыңыз немесе фото жіберіңіз.\n"
            "— Көмек керек болса — “FAQ / Көмек”.\n"
            "— {plan_line}\n"
            "— 🎁 Дос бонусы: достарды шақырып, PRO алыңыз.\n\n"
            "Ағымдағы режим: {mode_title}\n"
            "Өзгерту: ⚙️ Баптаулар → 🎛 Бот режимі."
        ),
        "de": (
            "👋 Hallo! Ich bin ein Lernassistent für Schule und Uni.\n\n"
            "Was ich kann:\n"
            "• Aufgaben Schritt für Schritt lösen\n"
            "• Theorie einfach erklären\n"
            "• Mitschriften, Tests, Spickzettel, Lernpläne\n"
            "• Hilfe bei Code und Formatierung\n"
            "• Aufgaben aus Fotos/Screenshots verstehen 📷\n\n"
            "Start:\n"
            "— Foto senden oder Aufgabe als Text schreiben.\n"
            "— Hilfe: “FAQ / Hilfe”.\n"
            "— {plan_line}\n"
            "— 🎁 Freunde-Bonus: Freunde einladen und PRO bekommen.\n\n"
            "Aktueller Modus: {mode_title}\n"
            "Ändern: ⚙️ Einstellungen → 🎛 Bot-Modus."
        ),
        "fr": (
            "👋 Salut ! Je suis un assistant d’étude pour l’école et l’université.\n\n"
            "Ce que je peux faire :\n"
            "• Résoudre pas à pas\n"
            "• Expliquer la théorie simplement\n"
            "• Faire des notes, tests, fiches, plans\n"
            "• Aider avec le code et la mise en forme\n"
            "• Comprendre des photos/captures 📷\n\n"
            "Pour commencer :\n"
            "— Envoie une photo ou écris l’énoncé.\n"
            "— Aide : “FAQ / Aide”.\n"
            "— {plan_line}\n"
            "— 🎁 Bonus amis : invite et reçois PRO.\n\n"
            "Mode actuel : {mode_title}\n"
            "Changer : ⚙️ Paramètres → 🎛 Mode du bot."
        ),
        "es": (
            "👋 ¡Hola! Soy un asistente de estudio para escuela y universidad.\n\n"
            "Qué puedo hacer:\n"
            "• Resolver paso a paso\n"
            "• Explicar teoría de forma simple\n"
            "• Crear apuntes, tests, chuletas y planes\n"
            "• Ayudar con código y formato\n"
            "• Entender fotos/capturas 📷\n\n"
            "Cómo empezar:\n"
            "— Envía una foto o escribe el enunciado.\n"
            "— Ayuda: “FAQ / Ayuda”.\n"
            "— {plan_line}\n"
            "— 🎁 Bono por amigos: invita y obtén PRO.\n\n"
            "Modo actual: {mode_title}\n"
            "Cambiar: ⚙️ Ajustes → 🎛 Modo del bot."
        ),
        "tr": (
            "👋 Selam! Okul ve üniversite için bir çalışma asistanıyım.\n\n"
            "Neler yaparım:\n"
            "• Soruları adım adım çözmek\n"
            "• Teoriyi basit anlatmak\n"
            "• Not, test, kopya ve çalışma planı hazırlamak\n"
            "• Kod ve format desteği\n"
            "• Foto/ekran görüntüsünden soru anlamak 📷\n\n"
            "Başlangıç:\n"
            "— Foto gönder veya metinle yaz.\n"
            "— Yardım: “SSS / Yardım”.\n"
            "— {plan_line}\n"
            "— 🎁 Arkadaş бонусu: davet et, PRO kazan.\n\n"
            "Mevcut mod: {mode_title}\n"
            "Değiştir: ⚙️ Ayarlar → 🎛 Bot modu."
        ),
        "ar": (
            "👋 مرحبًا! أنا مساعد دراسي للمدرسة والجامعة.\n\n"
            "ماذا أستطيع:\n"
            "• حل المسائل خطوة بخطوة\n"
            "• شرح النظرية ببساطة\n"
            "• إعداد ملخصات واختبارات وخطط\n"
            "• المساعدة في الكود والتنسيق\n"
            "• فهم الصور ولقطات الشاشة 📷\n\n"
            "كيف تبدأ:\n"
            "— أرسل صورة أو اكتب السؤال.\n"
            "— للمساعدة: “الأسئلة / المساعدة”.\n"
            "— {plan_line}\n"
            "— 🎁 مكافأة الأصدقاء: ادعُ أصدقاءك واحصل على PRO.\n\n"
            "الوضع الحالي: {mode_title}\n"
            "للتغيير: ⚙️ الإعدادات → 🎛 وضع البوت."
        ),
        "hi": (
            "👋 नमस्ते! मैं स्कूल और यूनिवर्सिटी के लिए एक स्टडी असिस्टेंट हूँ।\n\n"
            "मैं क्या कर सकता हूँ:\n"
            "• स्टेप-बाय-स्टेप समाधान\n"
            "• आसान भाषा में थ्योरी\n"
            "• नोट्स, टेस्ट, चीट-शीट, स्टडी प्लान\n"
            "• कोड और फ़ॉर्मैटिंग में मदद\n"
            "• फोटो/स्क्रीनशॉट समझना 📷\n\n"
            "कैसे शुरू करें:\n"
            "— फोटो भेजें या टेक्स्ट में लिखें।\n"
            "— मदद: “FAQ / मदद”.\n"
            "— {plan_line}\n"
            "— 🎁 दोस्तों का बोनस: दोस्तों को बुलाएँ और PRO पाएँ।\n\n"
            "वर्तमान मोड: {mode_title}\n"
            "बदलें: ⚙️ सेटिंग्स → 🎛 बॉट मोड।"
        ),
    },

    "ref_share_caption": {
        "ru": "Помощник для учёбы — моя реф. ссылка:",
        "en": "Study assistant — my referral link:",
        "uz": "O‘qish yordamchisi — mening referal havolam:",
        "kk": "Оқу көмекшісі — менің реф. сілтемем:",
        "de": "Lernassistent — mein Referral-Link:",
        "fr": "Assistant d’étude — mon lien de parrainage :",
        "es": "Asistente de estudio — mi enlace:",
        "tr": "Çalışma asistanı — referans linkim:",
        "ar": "مساعد الدراسة — رابط الإحالة الخاص بي:",
        "hi": "स्टडी असिस्टेंट — मेरा रेफरल लिंक:",
    },
    "ref_card": {
        "ru": (
            "🎁 <b>Бонус за друзей</b>\n\n"
            "Приглашай друзей по персональной ссылке.\n"
            "За каждые <b>{threshold}</b> покупок (LITE/PRO) по твоей ссылке — <b>+1 месяц PRO</b>.\n\n"
            "🔗 <b>Твоя ссылка:</b>\n<code>{link}</code>\n\n"
            "📊 <b>Статистика</b>\n"
            "— Всего приглашено: <b>{total}</b>\n"
            "— Купили подписку: <b>{paid}</b>\n"
            "— Прогресс до подарка: [{meter}] {progress}/{threshold}\n"
            "— До следующего подарка: <b>{left}</b>\n\n"
            "Поделись ссылкой с одногруппниками, в чатах курса или друзьям 👇"
        ),
        "en": (
            "🎁 <b>Friends bonus</b>\n\n"
            "Invite friends with your personal link.\n"
            "For every <b>{threshold}</b> paid subscriptions (LITE/PRO) via your link — <b>+1 month of PRO</b>.\n\n"
            "🔗 <b>Your link:</b>\n<code>{link}</code>\n\n"
            "📊 <b>Stats</b>\n"
            "— Invited: <b>{total}</b>\n"
            "— Paid: <b>{paid}</b>\n"
            "— Progress: [{meter}] {progress}/{threshold}\n"
            "— To next reward: <b>{left}</b>\n\n"
            "Share it with classmates, course chats, or friends 👇"
        ),
        "uz": (
            "🎁 <b>Do‘stlar bonusi</b>\n\n"
            "Do‘stlarni shaxsiy havolangiz orqali taklif qiling.\n"
            "Har <b>{threshold}</b> ta (LITE/PRO) to‘lov uchun — <b>+1 oy PRO</b>.\n\n"
            "🔗 <b>Sizning havolangiz:</b>\n<code>{link}</code>\n\n"
            "📊 <b>Statistika</b>\n"
            "— Taklif qilinganlar: <b>{total}</b>\n"
            "— To‘lov qilganlar: <b>{paid}</b>\n"
            "— Progress: [{meter}] {progress}/{threshold}\n"
            "— Keyingi sovg‘agacha: <b>{left}</b>\n\n"
            "Havolani guruhdoshlar, kurs chatlari yoki do‘stlaringizga ulashing 👇"
        ),
        "kk": (
            "🎁 <b>Дос бонусы</b>\n\n"
            "Достарыңызды жеке сілтеме арқылы шақырыңыз.\n"
            "Әр <b>{threshold}</b> төлем (LITE/PRO) үшін — <b>+1 ай PRO</b>.\n\n"
            "🔗 <b>Сіздің сілтеме:</b>\n<code>{link}</code>\n\n"
            "📊 <b>Статистика</b>\n"
            "— Шақырылғандар: <b>{total}</b>\n"
            "— Төлегендер: <b>{paid}</b>\n"
            "— Прогресс: [{meter}] {progress}/{threshold}\n"
            "— Келесі сыйлыққа дейін: <b>{left}</b>\n\n"
            "Сілтемені топтастарыңызға, курс чаттарына немесе достарыңызға жіберіңіз 👇"
        ),
        "de": (
            "🎁 <b>Freunde-Bonus</b>\n\n"
            "Lade Freunde über deinen persönlichen Link ein.\n"
            "Für jede <b>{threshold}</b> Käufe (LITE/PRO) über deinen Link — <b>+1 Monat PRO</b>.\n\n"
            "🔗 <b>Dein Link:</b>\n<code>{link}</code>\n\n"
            "📊 <b>Stats</b>\n"
            "— Eingeladen: <b>{total}</b>\n"
            "— Bezahlt: <b>{paid}</b>\n"
            "— Fortschritt: [{meter}] {progress}/{threshold}\n"
            "— Bis zur nächsten Belohnung: <b>{left}</b>\n\n"
            "Teile den Link mit Freunden oder in Kurs-Chats 👇"
        ),
        "fr": (
            "🎁 <b>Bonus amis</b>\n\n"
            "Invite via ton lien personnel.\n"
            "Chaque <b>{threshold}</b> achats (LITE/PRO) via ton lien — <b>+1 mois PRO</b>.\n\n"
            "🔗 <b>Ton lien :</b>\n<code>{link}</code>\n\n"
            "📊 <b>Stats</b>\n"
            "— Invités : <b>{total}</b>\n"
            "— Paiements : <b>{paid}</b>\n"
            "— Progression : [{meter}] {progress}/{threshold}\n"
            "— Prochaine récompense : <b>{left}</b>\n\n"
            "Partage le lien avec des amis ou dans des chats de cours 👇"
        ),
        "es": (
            "🎁 <b>Bono por amigos</b>\n\n"
            "Invita con tu enlace personal.\n"
            "Cada <b>{threshold}</b> compras (LITE/PRO) con tu enlace — <b>+1 mes PRO</b>.\n\n"
            "🔗 <b>Tu enlace:</b>\n<code>{link}</code>\n\n"
            "📊 <b>Estadísticas</b>\n"
            "— Invitados: <b>{total}</b>\n"
            "— Pagaron: <b>{paid}</b>\n"
            "— Progreso: [{meter}] {progress}/{threshold}\n"
            "— Para el próximo regalo: <b>{left}</b>\n\n"
            "Comparte el enlace con amigos o en chats del curso 👇"
        ),
        "tr": (
            "🎁 <b>Arkadaş бонусu</b>\n\n"
            "Kişisel bağlantınla arkadaşlarını davet et.\n"
            "Bağlantın üzerinden her <b>{threshold}</b> satın alma (LITE/PRO) için — <b>+1 ay PRO</b>.\n\n"
            "🔗 <b>Bağlantın:</b>\n<code>{link}</code>\n\n"
            "📊 <b>İstatistik</b>\n"
            "— Davet edilen: <b>{total}</b>\n"
            "— Ödeme yapan: <b>{paid}</b>\n"
            "— İlerleme: [{meter}] {progress}/{threshold}\n"
            "— Sonraki ödüle kalan: <b>{left}</b>\n\n"
            "Linki arkadaşlarınla veya kurs sohbetlerinde paylaş 👇"
        ),
        "ar": (
            "🎁 <b>مكافأة الأصدقاء</b>\n\n"
            "ادعُ أصدقاءك عبر رابطك الشخصي.\n"
            "لكل <b>{threshold}</b> عمليات شراء (LITE/PRO) عبر رابطك — <b>+1 شهر PRO</b>.\n\n"
            "🔗 <b>رابطك:</b>\n<code>{link}</code>\n\n"
            "📊 <b>الإحصائيات</b>\n"
            "— المدعوون: <b>{total}</b>\n"
            "— الذين دفعوا: <b>{paid}</b>\n"
            "— التقدم: [{meter}] {progress}/{threshold}\n"
            "— المتبقي للمكافأة التالية: <b>{left}</b>\n\n"
            "شارك الرابط مع زملائك أو في مجموعات الدراسة 👇"
        ),
        "hi": (
            "🎁 <b>दोस्तों का बोनस</b>\n\n"
            "अपने पर्सनल लिंक से दोस्तों को आमंत्रित करें।\n"
            "आपके लिंक से हर <b>{threshold}</b> खरीद (LITE/PRO) पर — <b>+1 महीना PRO</b>।\n\n"
            "🔗 <b>आपका लिंक:</b>\n<code>{link}</code>\n\n"
            "📊 <b>स्टैट्स</b>\n"
            "— आमंत्रित: <b>{total}</b>\n"
            "— भुगतान: <b>{paid}</b>\n"
            "— प्रगति: [{meter}] {progress}/{threshold}\n"
            "— अगले इनाम तक: <b>{left}</b>\n\n"
            "लिंक को दोस्तों या कोर्स चैट में शेयर करें 👇"
        ),
    },

    "subscribed": {
        "ru": "✅ Вы подписаны на рассылки. Отключить: /unsubscribe",
        "en": "✅ Subscribed. Unsubscribe: /unsubscribe",
        "uz": "✅ Tarqatmaga obuna bo‘ldingiz. O‘chirish: /unsubscribe",
        "kk": "✅ Таратуға жазылдыңыз. Өшіру: /unsubscribe",
        "de": "✅ Abonniert. Abmelden: /unsubscribe",
        "fr": "✅ Abonné. Se désabonner : /unsubscribe",
        "es": "✅ Suscrito. Cancelar: /unsubscribe",
        "tr": "✅ Abone oldun. İptal: /unsubscribe",
        "ar": "✅ تم الاشتراك. إلغاء: /unsubscribe",
        "hi": "✅ सब्सक्राइब। बंद करें: /unsubscribe",
    },
    "unsubscribed": {
        "ru": "❌ Вы отписаны от рассылок. Включить снова: /subscribe",
        "en": "❌ Unsubscribed. Subscribe again: /subscribe",
        "uz": "❌ Tarqatmadan chiqdingiz. Qayta: /subscribe",
        "kk": "❌ Таратудан шықтыңыз. Қайта: /subscribe",
        "de": "❌ Abgemeldet. Wieder: /subscribe",
        "fr": "❌ Désabonné. Réactiver : /subscribe",
        "es": "❌ Cancelado. Volver: /subscribe",
        "tr": "❌ Abonelik iptal. Tekrar: /subscribe",
        "ar": "❌ تم إلغاء الاشتراك. إعادة: /subscribe",
        "hi": "❌ अनसब्सक्राइब। फिर से: /subscribe",
    },
    "admin_count_text": {
        "ru": "Подписчиков (в базе): {n}",
        "en": "Subscribers (in DB): {n}",
        "uz": "Obunachilar (bazada): {n}",
        "kk": "Жазылушылар (базада): {n}",
        "de": "Abonnenten (DB): {n}",
        "fr": "Abonnés (BD) : {n}",
        "es": "Suscriptores (BD): {n}",
        "tr": "Abone (DB): {n}",
        "ar": "المشتركون (قاعدة): {n}",
        "hi": "सब्सक्राइबर (DB): {n}",
    },
}

def t(lang: str | None, key: str, **fmt) -> str:
    base = pick_lang(lang, _STRINGS.get(key, {"en": key, "ru": key}))
    if fmt:
        try:
            return base.format(**fmt)
        except Exception:
            return base
    return base
