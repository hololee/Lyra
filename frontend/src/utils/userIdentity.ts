export const USER_NAME_STORAGE_KEY = 'lyra.user_name';
export const USER_NAME_MAX_LENGTH = 32;

const USER_NAME_PATTERN = /^[a-zA-Z0-9-]+$/;

export type UserNameValidationCode =
  | 'ok'
  | 'empty'
  | 'too_long'
  | 'invalid_format';

export interface UserNameValidationResult {
  code: UserNameValidationCode;
  value: string;
}

export const normalizeUserName = (raw: string | null | undefined): string => {
  return (raw ?? '').trim();
};

export const validateUserName = (raw: string | null | undefined): UserNameValidationResult => {
  const value = normalizeUserName(raw);

  if (!value) {
    return { code: 'empty', value: '' };
  }
  if (value.length > USER_NAME_MAX_LENGTH) {
    return { code: 'too_long', value };
  }
  if (!USER_NAME_PATTERN.test(value)) {
    return { code: 'invalid_format', value };
  }

  return { code: 'ok', value };
};

export const getStoredUserName = (): string => {
  if (typeof window === 'undefined') return '';
  return normalizeUserName(window.localStorage.getItem(USER_NAME_STORAGE_KEY));
};

export const hasStoredUserName = (): boolean => {
  return Boolean(getStoredUserName());
};

export const setStoredUserName = (raw: string): UserNameValidationResult => {
  const result = validateUserName(raw);
  if (result.code !== 'ok') return result;

  if (typeof window !== 'undefined') {
    window.localStorage.setItem(USER_NAME_STORAGE_KEY, result.value);
  }
  return result;
};

export const clearStoredUserName = (): void => {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(USER_NAME_STORAGE_KEY);
};

export const buildPrefixedEnvironmentName = (userName: string, rawName: string): string => {
  const normalizedUser = normalizeUserName(userName);
  const normalizedName = (rawName ?? '').trim();
  const prefix = `${normalizedUser}-`;

  if (!normalizedUser) return normalizedName;
  if (normalizedName.startsWith(prefix)) return normalizedName;
  return `${prefix}${normalizedName}`;
};
