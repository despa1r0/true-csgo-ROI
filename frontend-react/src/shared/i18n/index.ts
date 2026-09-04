import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import ru from "./locales/ru.json";

export const supportedLanguages = ["en", "ru"] as const;
export type SupportedLanguage = (typeof supportedLanguages)[number];

const savedLanguage = window.localStorage.getItem("trueroi-language");
const browserLanguage = window.navigator.language.toLowerCase().startsWith("ru") ? "ru" : "en";
const initialLanguage: SupportedLanguage = savedLanguage === "en" || savedLanguage === "ru"
  ? savedLanguage
  : browserLanguage;

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ru: { translation: ru },
  },
  lng: initialLanguage,
  fallbackLng: "en",
  supportedLngs: supportedLanguages,
  interpolation: {
    escapeValue: false,
  },
});

function syncDocumentLanguage(language: string) {
  const normalizedLanguage = language.startsWith("ru") ? "ru" : "en";
  document.documentElement.lang = normalizedLanguage;
  window.localStorage.setItem("trueroi-language", normalizedLanguage);
}

syncDocumentLanguage(initialLanguage);
i18n.on("languageChanged", syncDocumentLanguage);

export default i18n;
