import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import enCommon from './locales/en/common';
import koCommon from './locales/ko/common';

const STORAGE_KEY = 'lyra.language';
const supportedLngs = ['en', 'ko'] as const;
const savedLanguage = (() => {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
})();
const initialLanguage = savedLanguage && supportedLngs.includes(savedLanguage as (typeof supportedLngs)[number])
  ? savedLanguage
  : 'en';

void i18n.use(initReactI18next).init({
  resources: {
    en: { common: enCommon },
    ko: { common: koCommon },
  },
  supportedLngs,
  lng: initialLanguage,
  fallbackLng: 'en',
  ns: ['common'],
  defaultNS: 'common',
  interpolation: {
    escapeValue: false,
  },
});

export default i18n;
